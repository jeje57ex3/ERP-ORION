/* Orion ERP — file d'attente des photos prises hors ligne.
 *
 * Un chantier n'a pas toujours de réseau. Sans file d'attente, la photo prise
 * dans un sous-sol était simplement perdue : le formulaire échouait, et
 * l'utilisateur n'avait aucun moyen de la renvoyer plus tard autrement qu'en la
 * reprenant — ce qui suppose d'être encore devant le sujet.
 *
 * Les photos en attente vivent dans IndexedDB, et non dans localStorage : ce
 * dernier ne stocke que du texte, et y encoder des images en base64 ferait
 * dépasser sa limite (~5 Mo) dès la deuxième photo.
 *
 * Deux choix qui comptent :
 *
 *   - Le renvoi porte une CLÉ d'envoi, générée ici et retenue par le serveur.
 *     La file ne peut pas savoir si une coupure est survenue avant ou APRÈS
 *     l'enregistrement : sans cette clé, toute réponse perdue donnerait une
 *     photo en double, précisément dans la situation de réseau instable qui
 *     justifie la file.
 *   - Un refus du serveur (422) RETIRE l'envoi de la file. Le réessayer
 *     indéfiniment ne le ferait pas passer, et bloquerait tout ce qui suit.
 *     Seules les pannes de réseau sont réessayées.
 */
(function () {
  'use strict';

  var BASE = 'orion-photos-hors-ligne';
  var MAGASIN = 'envois';
  var VERSION = 1;

  function ouvrir() {
    return new Promise(function (resoudre, rejeter) {
      if (!window.indexedDB) {
        rejeter(new Error('IndexedDB indisponible'));
        return;
      }
      var requete = window.indexedDB.open(BASE, VERSION);
      requete.onupgradeneeded = function () {
        var base = requete.result;
        if (!base.objectStoreNames.contains(MAGASIN)) {
          base.createObjectStore(MAGASIN, { keyPath: 'cle' });
        }
      };
      requete.onsuccess = function () { resoudre(requete.result); };
      requete.onerror = function () { rejeter(requete.error); };
    });
  }

  function transaction(mode, travail) {
    return ouvrir().then(function (base) {
      return new Promise(function (resoudre, rejeter) {
        var tx = base.transaction(MAGASIN, mode);
        var magasin = tx.objectStore(MAGASIN);
        var resultat = travail(magasin);
        tx.oncomplete = function () { resoudre(resultat && resultat.result); };
        tx.onerror = function () { rejeter(tx.error); };
        tx.onabort = function () { rejeter(tx.error); };
      });
    });
  }

  function cleNouvelle() {
    if (window.crypto && window.crypto.randomUUID) {
      return window.crypto.randomUUID();
    }
    // Repli pour les navigateurs sans randomUUID : l'unicité n'a besoin de
    // tenir que parmi les envois d'un même téléphone.
    return 'e-' + Date.now() + '-' + Math.random().toString(16).slice(2, 10);
  }

  function lireCookie(nom) {
    var morceaux = ('; ' + document.cookie).split('; ' + nom + '=');
    if (morceaux.length < 2) { return ''; }
    return morceaux.pop().split(';').shift();
  }

  var File = {
    /* Met un envoi de côté. `champs` est un objet de valeurs de formulaire,
       `fichiers` une liste de File. */
    deposer: function (champs, fichiers) {
      var envoi = {
        cle: cleNouvelle(),
        champs: champs,
        fichiers: [],
        depose_le: new Date().toISOString(),
      };
      // Les objets File sont des Blob : IndexedDB les stocke tels quels, sans
      // conversion ni perte de qualité.
      for (var i = 0; i < fichiers.length; i += 1) {
        envoi.fichiers.push({
          donnees: fichiers[i],
          nom: fichiers[i].name || ('photo-' + (i + 1) + '.jpg'),
          type: fichiers[i].type || 'image/jpeg',
        });
      }
      return transaction('readwrite', function (magasin) {
        return magasin.put(envoi);
      }).then(function () { return envoi; });
    },

    lister: function () {
      return transaction('readonly', function (magasin) {
        return magasin.getAll();
      }).then(function (envois) { return envois || []; });
    },

    compter: function () {
      return File.lister().then(function (envois) { return envois.length; });
    },

    retirer: function (cle) {
      return transaction('readwrite', function (magasin) {
        return magasin.delete(cle);
      });
    },

    /* Tente de renvoyer tout ce qui attend. Renvoie un compte-rendu. */
    vider: function (url) {
      return File.lister().then(function (envois) {
        var bilan = { envoyes: 0, refuses: 0, restants: 0, messages: [] };

        return envois.reduce(function (chaine, envoi) {
          return chaine.then(function () {
            var corps = new FormData();
            Object.keys(envoi.champs || {}).forEach(function (nom) {
              corps.append(nom, envoi.champs[nom]);
            });
            corps.append('cle_envoi', envoi.cle);
            (envoi.fichiers || []).forEach(function (fichier) {
              corps.append('photos', fichier.donnees, fichier.nom);
            });

            return fetch(url, {
              method: 'POST',
              body: corps,
              credentials: 'same-origin',
              headers: {
                'X-Requested-With': 'XMLHttpRequest',
                // Le jeton est relu MAINTENANT, et non au moment du dépôt :
                // une session renouvelée entre-temps en aurait changé, et
                // l'envoi serait refusé en 403 sans raison visible.
                'X-CSRFToken': lireCookie('csrftoken'),
              },
            }).then(function (reponse) {
              if (reponse.ok) {
                bilan.envoyes += 1;
                return File.retirer(envoi.cle);
              }
              if (reponse.status === 422 || reponse.status === 400) {
                // Refus définitif : le réessayer ne le ferait pas passer, et
                // il bloquerait tous les envois suivants.
                bilan.refuses += 1;
                return reponse.json().catch(function () { return {}; })
                  .then(function (donnees) {
                    (donnees.erreurs || []).forEach(function (m) {
                      bilan.messages.push(m);
                    });
                    return File.retirer(envoi.cle);
                  });
              }
              // 5xx, 403, 502… : panne possiblement passagère, on garde.
              bilan.restants += 1;
            }).catch(function () {
              // Toujours hors ligne : on garde, sans compter d'échec.
              bilan.restants += 1;
            });
          });
        }, Promise.resolve()).then(function () { return bilan; });
      });
    },
  };

  window.OrionFilePhotos = File;
}());
