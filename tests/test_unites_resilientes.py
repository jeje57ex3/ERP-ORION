# -*- coding: utf-8 -*-
"""Un service doit se relever seul, et une boucle doit s'arrêter.

CE QUI EST ARRIVÉ LE 09/11/2026, et ce qui a coûté l'accès à l'ERP.

`lunea-frontend` affichait « restart counter is at 578 », `siecle-frontend`
177, `orion-celery-beat` 375. Trois services en boucle permanente sur une
appliance où ils ne pouvaient pas démarrer. Par-dessus, `orion-health.timer`
redémarrait toutes les 60 secondes tout service qu'il jugeait en panne — y
compris `cloudflared`, qui a besoin de vingt à trente secondes pour établir
ses quatre connexions QUIC et ne se stabilisait donc jamais.

Il a fallu arrêter cette garde. Et l'arrêter a supprimé le filet : le tunnel
est retombé dans la soirée, et **plus rien ne le relevait**.

Les deux leçons, et ces tests les tiennent.

1. **Une boucle doit être bornée**, et le défaut de systemd ne la borne pas.
   Cinq essais dans une fenêtre de DIX secondes : avec `RestartSec=5`, deux
   essais au plus tombent dans la fenêtre, le seuil n'est jamais atteint, et
   le service se relance indéfiniment. C'est l'arithmétique, et c'est elle
   que le test central vérifie.

2. **Un service critique n'a pas besoin d'un gardien extérieur**, il a besoin
   de savoir se relever. systemd fait cela mieux qu'un script lancé par un
   minuteur, et sans jamais couper un tunnel en pleine poignée de main.
"""

import os
import re

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYSTEMD = os.path.join(RACINE, 'deployment', 'proxmox-appliance', 'systemd')
FRAGMENTS = os.path.join(SYSTEMD, 'dropins')
SCRIPT_MAJ = os.path.join(RACINE, 'deployment', 'proxmox-appliance',
                          'scripts', 'update_orion.sh')
PROVISIONNEMENT = os.path.join(RACINE, 'deployment', 'proxmox-appliance',
                               'provisioning', '03-systemd-units.sh')

# Le défaut de systemd, pour mémoire : 5 essais / 10 s. Il ne borne rien dès
# que RestartSec dépasse 2 secondes.
DEFAUT_SYSTEMD_ESSAIS = 5
DEFAUT_SYSTEMD_FENETRE = 10


def _lire(chemin):
    with open(chemin, encoding='utf-8') as fichier:
        return fichier.read()


def _cles(texte):
    """Les clés d'un fichier d'unité, commentaires écartés.

    Un analyseur maison plutôt que `configparser` : systemd autorise les
    clés répétées et les valeurs sans guillemets, et `configparser`
    réécrirait les deux à sa façon.
    """
    trouvees = {}
    for ligne in texte.splitlines():
        nue = ligne.strip()
        if not nue or nue.startswith('#') or nue.startswith('['):
            continue
        if '=' not in nue:
            continue
        cle, _, valeur = nue.partition('=')
        trouvees[cle.strip()] = valeur.strip()
    return trouvees


def _unites_qui_redemarrent():
    """Les unités qui déclarent une politique de redémarrage.

    Découvertes et non énumérées : une unité ajoutée demain héritera du
    même contrôle sans que personne n'ait à penser à l'inscrire ici.
    """
    retenues = []
    for nom in sorted(os.listdir(SYSTEMD)):
        if not nom.endswith('.service'):
            continue
        texte = _lire(os.path.join(SYSTEMD, nom))
        cles = _cles(texte)
        if cles.get('Restart'):
            retenues.append((nom, cles))
    return retenues


# ─── L'invariant central : la fenêtre doit pouvoir se remplir ──────────────

def test_chaque_unite_qui_redemarre_porte_une_borne():
    unites = _unites_qui_redemarrent()
    assert unites, 'aucune unite avec Restart= : la decouverte est cassee'

    sans_borne = [nom for nom, cles in unites
                  if 'StartLimitIntervalSec' not in cles
                  or 'StartLimitBurst' not in cles]
    assert sans_borne == [], (
        'ces unites s-en remettent au defaut de systemd, qui ne borne '
        'rien : %s' % sans_borne)


def test_la_fenetre_est_assez_large_pour_se_remplir():
    """LE test qui compte. Sans cela, la boucle reste infinie.

    systemd ne renonce que si `StartLimitBurst` démarrages tiennent dans
    `StartLimitIntervalSec`. Entre deux démarrages il s'écoule `RestartSec`.
    Il faut donc :

        RestartSec x StartLimitBurst  <  StartLimitIntervalSec

    Avec le défaut (5 essais / 10 s) et `RestartSec=5`, le produit vaut 25 et
    la fenêtre 10 : elle ne se remplit JAMAIS, et c'est exactement pourquoi
    un compteur a pu atteindre 578.
    """
    defaillantes = []
    for nom, cles in _unites_qui_redemarrent():
        attente = int(cles.get('RestartSec', '0') or 0)
        essais = int(cles['StartLimitBurst'])
        fenetre = int(cles['StartLimitIntervalSec'])
        if attente * essais >= fenetre:
            defaillantes.append(
                '%s : %ss x %d = %ss, fenetre %ss' % (
                    nom, attente, essais, attente * essais, fenetre))

    assert defaillantes == [], (
        'fenetre trop courte pour se remplir, donc boucle infinie : %s'
        % defaillantes)


def test_le_defaut_de_systemd_est_bien_insuffisant():
    """Le test qui justifie tous les autres, par le calcul.

    S'il échouait, c'est que systemd aurait changé de défauts et que nos
    bornes explicites seraient devenues inutiles.
    """
    for nom, cles in _unites_qui_redemarrent():
        attente = int(cles.get('RestartSec', '0') or 0)
        if attente < 2:
            continue
        assert attente * DEFAUT_SYSTEMD_ESSAIS > DEFAUT_SYSTEMD_FENETRE, (
            '%s : le defaut de systemd suffirait, nos bornes sont '
            'superflues' % nom)


def test_les_services_critiques_insistent_plus_longtemps():
    """Un backend doit traverser une base lente ; une boutique, non.

    Les deux boutiques ne servent que des fichiers déjà construits : si
    elles n'y arrivent pas, c'est que le bundle manque, et aucun nombre de
    tentatives ne le fera apparaître. Le backend, lui, attend une base de
    données qui peut mettre une minute à répondre.
    """
    cles = dict(_unites_qui_redemarrent())
    critique = cles['orion-backend.service']
    boutique = cles['siecle-frontend.service']

    assert int(critique['StartLimitBurst']) > int(
        boutique['StartLimitBurst'])
    assert int(critique['StartLimitIntervalSec']) > int(
        boutique['StartLimitIntervalSec'])


# ─── Un dossier de contenu absent ne tue plus un service ───────────────────

@pytest.mark.parametrize('nom,dossier', [
    ('siecle-frontend.service', 'siecle'),
    ('lunea-frontend.service', 'lunea'),
])
def test_un_dossier_absent_ne_tue_plus_la_boutique(nom, dossier):
    """« status=200/CHDIR », 578 fois. Le préfixe « - » l'empêche.

    Un serveur de fichiers statiques doit pouvoir démarrer et répondre 404.
    Refuser de vivre parce qu'un dossier manque transforme un contenu
    absent en boucle de redémarrage permanente.
    """
    cles = _cles(_lire(os.path.join(SYSTEMD, nom)))

    assert cles['WorkingDirectory'] == '-/opt/orion/' + dossier, (
        'sans le prefixe « - », un dossier absent fait mourir le service '
        'sur CHDIR a chaque demarrage')


# ─── Le tunnel se relève seul ──────────────────────────────────────────────

def _fragment_cloudflared():
    dossier = os.path.join(FRAGMENTS, 'cloudflared.service.d')
    assert os.path.isdir(dossier), (
        'le fragment de cloudflared a disparu : sans lui, un tunnel tombe '
        'reste tombe, et personne ne peut intervenir puisque l-acces passe '
        'par lui')
    fichiers = [f for f in sorted(os.listdir(dossier)) if f.endswith('.conf')]
    assert fichiers, 'aucun .conf dans %s' % dossier
    return _lire(os.path.join(dossier, fichiers[0]))


def test_le_tunnel_repart_meme_apres_un_arret_propre():
    """`Restart=always`, et non `on-failure`.

    L'edge Cloudflare ferme parfois la session de son côté, et cloudflared
    sort alors avec un code NUL. `on-failure` le laisserait arrêté, sans
    aucune erreur pour l'expliquer — et l'ERP serait injoignable sans que
    rien n'ait l'air cassé.
    """
    cles = _cles(_fragment_cloudflared())

    assert cles['Restart'] == 'always'


def test_le_tunnel_ne_redemarre_pas_trop_vite():
    """Redémarrer en boucle serrée épuise la borne avant le retour du réseau.

    C'est le piège exact dans lequel `orion-health.timer` l'enfermait :
    relancé toutes les 60 secondes, il n'avait jamais les vingt à trente
    secondes nécessaires pour établir ses quatre connexions QUIC.
    """
    cles = _cles(_fragment_cloudflared())

    assert int(cles['RestartSec']) >= 10, (
        'un tunnel a besoin de 20 a 30 s pour etablir ses connexions'
    )
    attente = int(cles['RestartSec'])
    essais = int(cles['StartLimitBurst'])
    fenetre = int(cles['StartLimitIntervalSec'])
    assert attente * essais < fenetre
    # Et il doit insister plusieurs minutes : une coupure d-acces Internet
    # ne doit pas le faire renoncer definitivement.
    assert attente * essais >= 180, (
        'le tunnel renonce trop vite pour traverser une coupure reseau')


def test_le_fragment_ne_remplace_pas_l_unite_de_cloudflared():
    """Un fragment COMPLÈTE, il ne se substitue pas.

    cloudflared.service est installé par cloudflared lui-même. Redéfinir
    son `ExecStart` ici figerait des options de ligne de commande que sa
    prochaine mise à jour changerait peut-être, et le tunnel ne
    démarrerait plus du tout.
    """
    texte = _fragment_cloudflared()
    cles = _cles(texte)

    assert 'ExecStart' not in cles, (
        'le fragment ne doit pas redefinir la commande de cloudflared')
    assert '[Install]' not in texte, (
        'l-activation au demarrage appartient a cloudflared, pas a nous')


# ─── Les fragments arrivent vraiment sur la machine ────────────────────────

def test_la_mise_a_jour_pose_les_fragments():
    """Un fragment que rien n'installe ne protège de rien.

    C'est le défaut constaté sur les règles sudoers et sur l'assistant
    disque : livrés dans le dépôt, jamais posés sur une machine déjà
    installée, donc le bouton correspondant ne faisait rien.
    """
    texte = _lire(SCRIPT_MAJ)

    assert 'dropins' in texte
    assert '/etc/systemd/system/$(basename "$dossier")' in texte
    assert 'daemon-reload' in texte


def test_le_provisionnement_les_pose_aussi():
    """Machine neuve et machine mise à jour doivent finir identiques.

    Sinon un correctif ne vaut que pour l'une des deux, et on s'en aperçoit
    des mois plus tard sur celle qu'on avait oubliée.
    """
    texte = _lire(PROVISIONNEMENT)

    assert 'dropins' in texte
    assert 'daemon-reload' in texte


def test_les_deux_scripts_posent_les_fragments_au_meme_endroit():
    """L'invariant qui empêche les deux chemins de divergar."""
    maj = _lire(SCRIPT_MAJ)
    prov = _lire(PROVISIONNEMENT)

    motif = re.compile(r'/etc/systemd/system/\$\(basename "\$dossier"\)')
    assert motif.search(maj), 'chemin de pose introuvable dans update_orion.sh'
    assert motif.search(prov), 'chemin de pose introuvable dans le provisioning'
