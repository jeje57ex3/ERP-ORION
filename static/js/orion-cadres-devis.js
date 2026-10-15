/* Orion ERP — éditeur de cadres sur un modèle de devis.
 *
 * On pose un cadre là où la valeur doit s'écrire, on le déplace, on le
 * redimensionne. La conversion vers les coordonnées du PDF est faite ici,
 * une fois pour toutes.
 *
 * Pourquoi cette conversion mérite un commentaire : l'écran compte en pixels
 * depuis le HAUT du document, le format PDF compte en points depuis le BAS de
 * la page. Les deux axes verticaux sont donc inversés, et c'est l'erreur la
 * plus facile à commettre -- un cadre posé en haut se retrouverait imprimé en
 * bas. D'où une seule paire de fonctions pour traduire, utilisée partout.
 *
 *   points = pixels / echelle
 *   y_pdf  = hauteur_page - (y_ecran + hauteur_cadre) / echelle
 */
(function () {
  'use strict';

  var racine = document.getElementById('editeur-cadres');
  if (!racine) { return; }

  var ECHELLE = parseFloat(racine.dataset.echelle) || 2;
  var URL_ENREGISTRER = racine.dataset.urlEnregistrer;
  var URL_IMAGE = racine.dataset.urlImage;
  var CSRF = racine.dataset.csrf;
  var PAGES = JSON.parse(racine.dataset.pages || '[]');
  var VALEURS = JSON.parse(racine.dataset.valeurs || '[]');

  var cadres = JSON.parse(racine.dataset.cadres || '[]');
  var pageCourante = 1;
  var selection = null;
  var modifie = false;

  var zone = document.getElementById('zone-page');
  var image = document.getElementById('image-page');
  var listePages = document.getElementById('choix-page');
  var palette = document.getElementById('palette-valeurs');
  var inspecteur = document.getElementById('inspecteur');
  var etat = document.getElementById('etat-enregistrement');

  function pageActuelle() {
    return PAGES.find(function (p) { return p.numero === pageCourante; })
      || { largeur: 595, hauteur: 842 };
  }

  // ── Conversions ──────────────────────────────────────────────────────────
  function versPdf(cadre, gauchePx, hautPx, largeurPx, hauteurPx) {
    var page = pageActuelle();
    cadre.x = gauchePx / ECHELLE;
    cadre.largeur = largeurPx / ECHELLE;
    cadre.hauteur = hauteurPx / ECHELLE;
    // L'axe vertical s'inverse : le bas du cadre, compté depuis le bas.
    cadre.y = page.hauteur - (hautPx + hauteurPx) / ECHELLE;
  }

  function versEcran(cadre) {
    var page = pageActuelle();
    return {
      gauche: cadre.x * ECHELLE,
      haut: (page.hauteur - cadre.y - cadre.hauteur) * ECHELLE,
      largeur: cadre.largeur * ECHELLE,
      hauteur: cadre.hauteur * ECHELLE,
    };
  }

  // ── Rendu ────────────────────────────────────────────────────────────────
  function libelleDe(cle) {
    var trouve = VALEURS.find(function (v) { return v.cle === cle; });
    return trouve ? trouve.libelle : cle;
  }

  function dessiner() {
    zone.querySelectorAll('.cadre').forEach(function (n) { n.remove(); });

    cadres.forEach(function (cadre, index) {
      if (cadre.page !== pageCourante) { return; }
      var pos = versEcran(cadre);

      var element = document.createElement('div');
      element.className = 'cadre' + (cadre === selection ? ' actif' : '');
      element.style.left = pos.gauche + 'px';
      element.style.top = pos.haut + 'px';
      element.style.width = pos.largeur + 'px';
      element.style.height = pos.hauteur + 'px';
      element.dataset.index = index;

      var etiquette = document.createElement('span');
      etiquette.className = 'cadre-libelle';
      etiquette.textContent = libelleDe(cadre.cle);
      element.appendChild(etiquette);

      var poignee = document.createElement('span');
      poignee.className = 'cadre-poignee';
      poignee.title = 'Redimensionner';
      element.appendChild(poignee);

      zone.appendChild(element);
    });

    rendreInspecteur();
  }

  function rendreInspecteur() {
    if (!selection) {
      inspecteur.innerHTML =
        '<p class="aide">Cliquez une valeur à gauche pour poser un cadre, '
        + 'puis déplacez-le. Sélectionnez un cadre pour régler sa taille de '
        + 'texte.</p>';
      return;
    }
    var page = pageActuelle();
    inspecteur.innerHTML = ''
      + '<div class="inspecteur-titre">' + libelleDe(selection.cle) + '</div>'
      + '<label>Taille du texte (pt)'
      + '  <input type="number" id="i-taille" min="5" max="72" value="'
      + selection.taille + '"></label>'
      + '<label><input type="checkbox" id="i-gras"'
      + (selection.gras ? ' checked' : '') + '> Gras</label>'
      + '<label>Alignement'
      + '  <select id="i-align">'
      + '    <option value="left">À gauche</option>'
      + '    <option value="center">Centré</option>'
      + '    <option value="right">À droite</option>'
      + '  </select></label>'
      + '<label>Texte avant'
      + '  <input type="text" id="i-prefixe" maxlength="40" value="'
      + (selection.prefixe || '').replace(/"/g, '&quot;') + '"></label>'
      + '<label>Texte après'
      + '  <input type="text" id="i-suffixe" maxlength="40" value="'
      + (selection.suffixe || '').replace(/"/g, '&quot;') + '"></label>'
      + '<p class="aide">Position : x=' + selection.x.toFixed(1)
      + ' y=' + selection.y.toFixed(1) + ' pt, cadre '
      + selection.largeur.toFixed(0) + '×' + selection.hauteur.toFixed(0)
      + ' pt (page ' + page.largeur.toFixed(0) + '×'
      + page.hauteur.toFixed(0) + ')</p>'
      + '<button type="button" class="orion-btn sm danger" id="i-retirer">'
      + 'Retirer ce cadre</button>';

    document.getElementById('i-align').value = selection.alignement || 'left';

    document.getElementById('i-taille').addEventListener('input', function () {
      selection.taille = parseInt(this.value, 10) || 10;
      marquerModifie();
    });
    document.getElementById('i-gras').addEventListener('change', function () {
      selection.gras = this.checked;
      marquerModifie();
    });
    document.getElementById('i-align').addEventListener('change', function () {
      selection.alignement = this.value;
      marquerModifie();
    });
    ['prefixe', 'suffixe'].forEach(function (nom) {
      document.getElementById('i-' + nom)
        .addEventListener('input', function () {
          selection[nom] = this.value;
          marquerModifie();
        });
    });
    document.getElementById('i-retirer').addEventListener('click', function () {
      cadres = cadres.filter(function (c) { return c !== selection; });
      selection = null;
      marquerModifie();
      dessiner();
    });
  }

  function marquerModifie() {
    modifie = true;
    etat.textContent = 'Modifications non enregistrées';
    etat.className = 'etat en-attente';
  }

  // ── Poser un cadre ───────────────────────────────────────────────────────
  palette.addEventListener('click', function (evenement) {
    var bouton = evenement.target.closest('[data-cle]');
    if (!bouton) { return; }

    // Pose au centre de la page visible : le cadre est aussitot visible et
    // deplacable. Le poser a (0,0) l'enverrait dans un coin, souvent hors du
    // champ de vision apres defilement.
    var page = pageActuelle();
    var cadre = {
      cle: bouton.dataset.cle,
      page: pageCourante,
      largeur: 160,
      hauteur: 16,
      taille: 10,
      gras: false,
      alignement: 'left',
      prefixe: '',
      suffixe: '',
      x: (page.largeur - 160) / 2,
      y: page.hauteur / 2,
    };
    cadres.push(cadre);
    selection = cadre;
    marquerModifie();
    dessiner();
  });

  // ── Déplacer et redimensionner ───────────────────────────────────────────
  var geste = null;

  zone.addEventListener('pointerdown', function (evenement) {
    var element = evenement.target.closest('.cadre');
    if (!element) { selection = null; dessiner(); return; }

    var index = parseInt(element.dataset.index, 10);
    selection = cadres[index];
    dessiner();

    // Le nœud a été recréé par dessiner() : on reprend celui qui porte
    // l'index, sinon le déplacement suit un élément retiré du document.
    element = zone.querySelector('.cadre[data-index="' + index + '"]');
    if (!element) { return; }

    var rect = element.getBoundingClientRect();
    var zoneRect = zone.getBoundingClientRect();
    geste = {
      cadre: selection,
      element: element,
      redimensionne: evenement.target.classList.contains('cadre-poignee'),
      departX: evenement.clientX,
      departY: evenement.clientY,
      gauche: rect.left - zoneRect.left,
      haut: rect.top - zoneRect.top,
      largeur: rect.width,
      hauteur: rect.height,
    };
    element.setPointerCapture(evenement.pointerId);
    evenement.preventDefault();
  });

  zone.addEventListener('pointermove', function (evenement) {
    if (!geste) { return; }
    var dx = evenement.clientX - geste.departX;
    var dy = evenement.clientY - geste.departY;

    var gauche = geste.gauche;
    var haut = geste.haut;
    var largeur = geste.largeur;
    var hauteur = geste.hauteur;

    if (geste.redimensionne) {
      largeur = Math.max(20, geste.largeur + dx);
      hauteur = Math.max(10, geste.hauteur + dy);
    } else {
      gauche = geste.gauche + dx;
      haut = geste.haut + dy;
    }

    // Borné à la page : un cadre glissé dehors ne s'imprimerait pas, et rien
    // ne le dirait -- la valeur manquerait simplement sur le devis.
    gauche = Math.max(0, Math.min(gauche, image.width - largeur));
    haut = Math.max(0, Math.min(haut, image.height - hauteur));

    geste.element.style.left = gauche + 'px';
    geste.element.style.top = haut + 'px';
    geste.element.style.width = largeur + 'px';
    geste.element.style.height = hauteur + 'px';

    versPdf(geste.cadre, gauche, haut, largeur, hauteur);
  });

  function terminerGeste() {
    if (!geste) { return; }
    geste = null;
    marquerModifie();
    dessiner();
  }
  zone.addEventListener('pointerup', terminerGeste);
  zone.addEventListener('pointercancel', terminerGeste);

  // Déplacement fin au clavier : viser au pixel à la souris est pénible, et
  // un devis se cale souvent à deux ou trois points près.
  document.addEventListener('keydown', function (evenement) {
    if (!selection) { return; }
    var pas = evenement.shiftKey ? 10 : 1;
    var bouge = true;
    switch (evenement.key) {
      case 'ArrowLeft':  selection.x -= pas; break;
      case 'ArrowRight': selection.x += pas; break;
      case 'ArrowUp':    selection.y += pas; break;   // vers le haut = y PDF croissant
      case 'ArrowDown':  selection.y -= pas; break;
      case 'Delete':
        cadres = cadres.filter(function (c) { return c !== selection; });
        selection = null;
        break;
      default: bouge = false;
    }
    if (bouge) {
      evenement.preventDefault();
      marquerModifie();
      dessiner();
    }
  });

  // ── Pages ────────────────────────────────────────────────────────────────
  if (listePages) {
    listePages.addEventListener('change', function () {
      pageCourante = parseInt(this.value, 10) || 1;
      selection = null;
      image.src = URL_IMAGE.replace('__PAGE__', pageCourante);
      dessiner();
    });
  }

  // ── Enregistrer ──────────────────────────────────────────────────────────
  document.getElementById('bouton-enregistrer')
    .addEventListener('click', function () {
      var bouton = this;
      bouton.disabled = true;
      etat.textContent = 'Enregistrement…';
      etat.className = 'etat';

      fetch(URL_ENREGISTRER, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': CSRF,
        },
        body: JSON.stringify({ cadres: cadres }),
      }).then(function (reponse) {
        return reponse.json().then(function (donnees) {
          return { ok: reponse.ok, donnees: donnees };
        });
      }).then(function (resultat) {
        if (resultat.ok) {
          modifie = false;
          etat.textContent = resultat.donnees.enregistres
            + ' cadre(s) enregistré(s).';
          etat.className = 'etat ok';
        } else {
          etat.textContent = resultat.donnees.erreur || 'Échec.';
          etat.className = 'etat erreur';
        }
      }).catch(function () {
        etat.textContent = 'Erreur réseau : rien n’a été enregistré.';
        etat.className = 'etat erreur';
      }).finally(function () {
        bouton.disabled = false;
      });
    });

  // Quitter en laissant des cadres non enregistres fait perdre tout le
  // placement -- c'est long a refaire, et rien ne previendrait.
  window.addEventListener('beforeunload', function (evenement) {
    if (!modifie) { return; }
    evenement.preventDefault();
    evenement.returnValue = '';
  });

  image.addEventListener('load', dessiner);
  if (image.complete) { dessiner(); }
}());
