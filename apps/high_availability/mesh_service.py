"""Pilotage du réseau privé depuis l'interface web.

Séparé de `mesh.py`, qui reste purement calculatoire et donc éprouvable sans
WireGuard ni privilège. Ici vivent les effets de bord : lecture de l'état réel
et appels au script d'exploitation.

Le compte applicatif `orion` disposant de sudo sans mot de passe (posé par le
cloud-init), l'interface peut lancer `orion-mesh.sh`. Les paramètres ne sont
JAMAIS concaténés dans une ligne de commande : ils sont passés en arguments
séparés, ce qui écarte toute injection — une clé publique collée depuis un
presse-papier est une saisie extérieure comme une autre.
"""

import os
import subprocess

from django.conf import settings

from apps.high_availability.mesh import (
    MeshConfigError,
    config_locale,
    pairs_attendus,
    parse_wg_dump,
)

SCRIPT_DEPLOYE = '/opt/orion/scripts/orion-mesh.sh'
IFACE = 'orion0'
CLE_PUBLIQUE = f'/etc/wireguard/{IFACE}.pub'
DELAI_SECONDES = 120


def _chemin_script():
    """Premier chemin existant : la copie déployée, puis celle du dépôt.

    La page et le script viennent du MÊME dépôt mais arrivent par deux chemins
    différents : le code applicatif par `git pull`, les scripts par la mise à
    jour qui les recopie dans /opt/orion/scripts. Un `git pull` seul laisse
    donc une page toute neuve qui pilote un script absent — constaté en
    production, tous les boutons répondant « command not found », message qui
    ne désigne évidemment pas la cause.

    Le repli sur la copie du dépôt supprime la classe d'erreur : le script est
    forcément là, puisqu'il est livré par le même commit que la page qui
    l'appelle.
    """
    depot = os.path.join(
        str(settings.BASE_DIR), 'deployment', 'proxmox-appliance', 'scripts',
        'orion-mesh.sh',
    )
    for chemin in (SCRIPT_DEPLOYE, depot):
        if os.path.exists(chemin):
            return chemin
    return ''


def _prefixe_sudo():
    """sudo seulement si nécessaire : root n'en a pas besoin, et l'exiger
    ferait échouer les exécutions en ligne de commande."""
    if os.name == 'posix' and hasattr(os, 'geteuid') and os.geteuid() == 0:
        return []
    return ['sudo', '-n']


def _executer(*arguments, delai=DELAI_SECONDES):
    """Lance orion-mesh.sh et retourne (succès, sortie lisible)."""
    chemin = _chemin_script()
    if not chemin:
        return False, (
            "Le script du réseau privé est introuvable, ni dans "
            f'{SCRIPT_DEPLOYE} ni dans le dépôt. Ce serveur ne semble pas être '
            'une appliance Orion.'
        )

    # Lancé PAR bash, et non exécuté directement : ni le bit exécutable ni la
    # forme du shebang n'entrent alors en jeu. Les deux ont déjà cassé ce
    # genre d'appel — un fichier versionné sans bit d'exécution, un shebang
    # terminé par un retour chariot — avec à chaque fois un message qui
    # désignait tout sauf la cause.
    commande = _prefixe_sudo() + ['bash', chemin, *arguments]
    try:
        proc = subprocess.run(
            commande, capture_output=True, text=True, timeout=delai,
        )
    except FileNotFoundError:
        return False, (
            "Ni bash ni sudo n'ont pu être lancés sur ce serveur."
        )
    except subprocess.TimeoutExpired:
        return False, f'Le script a dépassé {delai} s.'

    sortie = ((proc.stdout or '') + (proc.stderr or '')).strip()
    return proc.returncode == 0, sortie or '(aucune sortie)'


def cle_publique_locale():
    """Clé publique WireGuard de ce serveur, à communiquer aux autres."""
    try:
        with open(CLE_PUBLIQUE, 'r', encoding='utf-8') as fichier:
            return fichier.read().strip()
    except OSError:
        return ''


def etat_interface():
    """État réel de l'interface, ou une raison claire de son absence."""
    commande = _prefixe_sudo() + ['wg', 'show', IFACE, 'dump']
    try:
        proc = subprocess.run(commande, capture_output=True, text=True, timeout=15)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {
            'active': False,
            'raison': "WireGuard n'est pas installé sur ce serveur.",
            'interface': {}, 'pairs': [],
        }

    if proc.returncode != 0:
        return {
            'active': False,
            'raison': (
                f"L'interface {IFACE} n'est pas active. Initialisez le réseau "
                'privé, puis activez-le.'
            ),
            'interface': {}, 'pairs': [],
        }

    donnees = parse_wg_dump(proc.stdout)
    return {'active': True, 'raison': '', **donnees}


def tableau_des_pairs(settings_obj=None):
    """Croise les pairs ATTENDUS de la grappe avec ceux que WireGuard déclare.

    C'est le seul tableau qui dise la vérité : un pair attendu mais absent de
    la configuration n'a jamais été déclaré, et un pair déclaré dont la
    poignée de main vaut 0 n'a jamais répondu. Les deux situations se
    ressemblent de loin et n'ont ni la même cause ni le même remède.
    """
    etat = etat_interface()
    par_adresse = {}
    for pair in etat['pairs']:
        for reseau_autorise in (pair['allowed_ips'] or '').split(','):
            adresse = reseau_autorise.strip().split('/')[0]
            if adresse:
                par_adresse[adresse] = pair

    lignes = []
    try:
        attendus = pairs_attendus(settings_obj)
    except MeshConfigError:
        attendus = []

    for attendu in attendus:
        declare = par_adresse.get(attendu['adresse'])
        if declare is None:
            etiquette, detail = 'absent', 'Jamais déclaré sur ce serveur.'
        elif declare['a_repondu']:
            etiquette, detail = 'ok', f"Poignée de main établie, {declare['endpoint'] or 'sans endpoint'}."
        else:
            etiquette, detail = 'muet', (
                "Déclaré, mais n'a jamais répondu. Vérifiez son endpoint, le "
                'port UDP au pare-feu des deux côtés, et que ce serveur est '
                'bien déclaré chez lui aussi.'
            )

        lignes.append({**attendu, 'etat': etiquette, 'detail': detail, 'wg': declare})

    return {'etat': etat, 'lignes': lignes}


def contexte_local(settings_obj=None):
    """Identité privée de ce serveur, pour affichage."""
    try:
        cfg = config_locale(settings_obj)
        erreur = ''
    except MeshConfigError as exc:
        cfg, erreur = {}, str(exc)

    return {
        'config': cfg,
        'erreur': erreur,
        'cle_publique': cle_publique_locale(),
        'node_id': getattr(settings, 'ORION_NODE_ID', ''),
    }


# ─── Actions ────────────────────────────────────────────────────────────────

def initialiser():
    return _executer('init')


def poser_hosts():
    return _executer('hosts')


def activer():
    return _executer('up')


def ajouter_pair(rang, cle_publique, endpoint=''):
    arguments = ['add-peer', str(int(rang)), cle_publique.strip()]
    if endpoint.strip():
        arguments.append(endpoint.strip())
    return _executer(*arguments)


def cle_media():
    return _executer('media-key')


def accepter_cle_media(rang, cle_publique):
    return _executer('trust', str(int(rang)), cle_publique.strip())
