/* Orion ERP — tracer sa signature dans un cadre, et l'enregistrer.
 *
 * Trois décisions méritent une explication, parce qu'elles ne se devinent
 * pas en relisant le code :
 *
 * 1. LA TOILE RESTE TRANSPARENTE. On ne peint aucun fond. Posée sur un
 *    modèle de devis, une signature à fond blanc masquerait ce qui se
 *    trouve dessous — en-tête, cadre, filet.
 *
 * 2. LA TOILE EST PLUS GRANDE QUE CE QU'ON VOIT. Son tampon fait 900x300
 *    quelle que soit la taille à l'écran, et les coordonnées du pointeur y
 *    sont ramenées. Dessiner à la taille CSS donnerait une image de ~300px
 *    de large, qui sort floue à l'impression.
 *
 * 3. pointerdown/move/up, et non mousedown/touchstart. Une seule API pour
 *    la souris, le stylet et le doigt. Avec « touch-action: none » sur la
 *    toile, sans quoi le doigt ferait défiler la page au lieu de tracer.
 */
(function () {
  'use strict';

  var racine = document.getElementById('cadre-signature');
  if (!racine) { return; }

  var toile = document.getElementById('toile-signature');
  var contexte = toile.getContext('2d');
  var boutonEffacer = document.getElementById('signature-effacer');
  var boutonEnregistrer = document.getElementById('signature-enregistrer');
  var etat = document.getElementById('signature-etat');
  var apercu = document.getElementById('signature-apercu');

  var URL_ENREGISTRER = racine.dataset.urlEnregistrer;
  var CSRF = racine.dataset.csrf;

  var entrain = false;
  var traceQuelqueChose = false;

  function preparer() {
    contexte.lineWidth = 5;
    contexte.lineCap = 'round';
    contexte.lineJoin = 'round';
    contexte.strokeStyle = '#111111';
  }
  preparer();

  // ── Du pointeur vers la toile ────────────────────────────────────────────
  // Le tampon de la toile est plus grand que son affichage : sans ce
  // rapport, le trait se dessinerait decale et plus petit que le doigt.
  function position(evenement) {
    var cadre = toile.getBoundingClientRect();
    return {
      x: (evenement.clientX - cadre.left) * (toile.width / cadre.width),
      y: (evenement.clientY - cadre.top) * (toile.height / cadre.height),
    };
  }

  function commencer(evenement) {
    entrain = true;
    traceQuelqueChose = true;
    var p = position(evenement);
    contexte.beginPath();
    contexte.moveTo(p.x, p.y);
    // Un simple appui doit laisser un point, et non rien du tout.
    contexte.lineTo(p.x, p.y);
    contexte.stroke();
    annoncer('', '');
    toile.setPointerCapture(evenement.pointerId);
    evenement.preventDefault();
  }

  function continuer(evenement) {
    if (!entrain) { return; }
    var p = position(evenement);
    contexte.lineTo(p.x, p.y);
    contexte.stroke();
    evenement.preventDefault();
  }

  function finir() {
    entrain = false;
  }

  toile.addEventListener('pointerdown', commencer);
  toile.addEventListener('pointermove', continuer);
  toile.addEventListener('pointerup', finir);
  toile.addEventListener('pointercancel', finir);
  toile.addEventListener('pointerleave', finir);

  // ── Effacer ──────────────────────────────────────────────────────────────
  boutonEffacer.addEventListener('click', function () {
    contexte.clearRect(0, 0, toile.width, toile.height);
    // clearRect remet aussi les reglages du contexte a plat sur certains
    // navigateurs : on les repose.
    preparer();
    traceQuelqueChose = false;
    annoncer('Cadre effacé.', '');
  });

  // ── Enregistrer ──────────────────────────────────────────────────────────
  function annoncer(texte, classe) {
    etat.textContent = texte;
    etat.className = 'signature-etat' + (classe ? ' ' + classe : '');
  }

  boutonEnregistrer.addEventListener('click', function () {
    if (!traceQuelqueChose) {
      // Le serveur refuse aussi une toile vide -- c'est lui qui decide --
      // mais le dire ici evite un aller-retour pour rien.
      annoncer('Tracez votre signature dans le cadre avant d’enregistrer.',
               'erreur');
      return;
    }

    boutonEnregistrer.disabled = true;
    annoncer('Enregistrement…', '');

    var corps = new FormData();
    corps.append('signature', toile.toDataURL('image/png'));

    fetch(URL_ENREGISTRER, {
      method: 'POST',
      headers: { 'X-CSRFToken': CSRF },
      body: corps,
    }).then(function (reponse) {
      return reponse.json().then(function (donnees) {
        return { ok: reponse.ok, donnees: donnees };
      });
    }).then(function (resultat) {
      boutonEnregistrer.disabled = false;
      if (!resultat.ok) {
        annoncer(resultat.donnees.erreur || 'Enregistrement refusé.',
                 'erreur');
        return;
      }
      annoncer(resultat.donnees.message || 'Signature enregistrée.', 'ok');
      if (apercu) {
        // Le parametre casse le cache : l'adresse du fichier ne change pas
        // d'un enregistrement a l'autre, et le navigateur afficherait
        // sinon l'ancienne image.
        apercu.src = resultat.donnees.url + '?t=' + Date.now();
        apercu.closest('.signature-apercu').hidden = false;
      }
    }).catch(function () {
      boutonEnregistrer.disabled = false;
      annoncer('Enregistrement impossible : vérifiez la connexion.',
               'erreur');
    });
  });
})();
