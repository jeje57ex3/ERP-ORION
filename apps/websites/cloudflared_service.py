"""Pilotage du tunnel Cloudflare depuis l'interface Orion ERP.

POURQUOI CE MODULE EXISTE

Le tunnel se lançait jusqu'ici à la main, par une ligne de commande passée
depuis l'hôte Proxmox :

    qm guest exec 100 -- cloudflared tunnel run <uuid>

Deux défauts, et le second est le pire. D'abord `qm guest exec` ATTEND la
fin de la commande, alors que `cloudflared tunnel run` ne se termine
jamais : l'appel bloque, dépasse son délai, et le tunnel meurt avec lui.
Ensuite un processus lancé ainsi ne survit ni à un redémarrage ni à un
plantage — il faut être devant un terminal pour le relancer, et savoir
qu'il faut le faire.

L'appliance installe pourtant déjà `cloudflared.service`. Ce module ne fait
donc rien d'autre que PILOTER CE SERVICE, pour que l'écran Cloudflare
suffise.

CE QUE SUDOERS AUTORISE, ET RIEN D'AUTRE

Le compte de service (`orion`) n'est pas administrateur. Il reçoit le droit
de lancer exactement les lignes listées dans
`deployment/proxmox-appliance/sudoers/orion-cloudflared`, et un test compare
les deux listes : si elles divergent, les boutons cessent de fonctionner
sans que rien ne le signale.

AUCUN JOKER. Une règle du genre « systemctl * cloudflared » paraîtrait
équivalente et ne l'est pas : sudo compare la commande à ce motif, et un
joker accepte beaucoup plus que ce qu'on croit avoir accordé.

Pas de `shell=True`, et aucune interpolation : le nom du service est une
constante du module, jamais une donnée de requête.

LIRE L'ÉTAT NE DEMANDE AUCUN DROIT

`systemctl is-active` et `is-enabled` répondent à un utilisateur ordinaire.
L'écran peut donc afficher la situation même si le fichier sudoers n'a
jamais été installé — et c'est justement là qu'il faut pouvoir le dire.
"""

import os
import platform
import subprocess

SERVICE = 'cloudflared'

DELAI_COMMANDE = 20

CHEMINS_SYSTEMCTL = ('/usr/bin/systemctl', '/bin/systemctl')

# Les verbes autorisés, et leur libellé pour l'interface. L'ordre est celui
# des boutons.
ACTIONS = {
    'demarrer':   ('start',   'Démarrer le tunnel'),
    'arreter':    ('stop',    'Arrêter le tunnel'),
    'redemarrer': ('restart', 'Redémarrer le tunnel'),
    'activer':    ('enable',  'Démarrer automatiquement au boot'),
    'desactiver': ('disable', 'Ne plus démarrer au boot'),
}


class CloudflaredError(Exception):
    """Ce qui a empêché l'action, dit dans des termes exploitables."""


def chemin_systemctl():
    """Le chemin de `systemctl` sur cette machine.

    Le chemin doit être ABSOLU et correspondre à la règle sudoers :
    `sudo systemctl` tout court dépendrait du PATH du processus, que systemd
    ne garantit pas.
    """
    for chemin in CHEMINS_SYSTEMCTL:
        if os.path.exists(chemin):
            return chemin
    return CHEMINS_SYSTEMCTL[0]


def ligne_de_commande(action):
    """La commande exacte, telle que sudoers doit l'autoriser."""
    if action not in ACTIONS:
        raise CloudflaredError(f'Action inconnue : {action}.')
    verbe = ACTIONS[action][0]
    return ['sudo', '-n', chemin_systemctl(), verbe, SERVICE]


def _require_linux():
    if platform.system() != 'Linux':
        raise CloudflaredError(
            "Le tunnel Cloudflare se pilote depuis l'appliance Linux, pas "
            "depuis ce poste de développement."
        )


def _lire(argv):
    """Une lecture d'état. Ne lève jamais : un écran de diagnostic qui
    tombe parce que le diagnostic a échoué ne sert à rien."""
    try:
        resultat = subprocess.run(
            argv, capture_output=True, text=True, timeout=DELAI_COMMANDE)
    except (OSError, subprocess.SubprocessError):
        return ''
    # « is-active » rend 3 quand le service est arrêté : le code de retour
    # ne distingue pas l'échec de la lecture de l'état « inactif ». C'est la
    # SORTIE qu'il faut lire, pas le code.
    return (resultat.stdout or resultat.stderr or '').strip()


def etat():
    """L'état du service, sans aucun droit particulier.

    Rend un dictionnaire plutôt qu'un booléen : « arrêté » et « pas
    installé » appellent des gestes très différents, et les confondre
    enverrait chercher une panne là où il n'y a qu'un paquet absent.
    """
    if platform.system() != 'Linux':
        return {'disponible': False, 'actif': False, 'au_demarrage': False,
                'installe': False, 'detail': 'Poste de développement.'}

    systemctl = chemin_systemctl()
    if not os.path.exists(systemctl):
        return {'disponible': False, 'actif': False, 'au_demarrage': False,
                'installe': False, 'detail': 'systemctl introuvable.'}

    actif = _lire([systemctl, 'is-active', SERVICE])
    demarrage = _lire([systemctl, 'is-enabled', SERVICE])

    # « unknown » / « not-found » : l'unité n'existe pas. Le tunnel n'a
    # jamais été installé sur cette machine.
    installe = 'not-found' not in demarrage and actif != 'unknown'

    return {
        'disponible': True,
        'installe': installe,
        'actif': actif == 'active',
        'au_demarrage': demarrage == 'enabled',
        'etat_brut': actif,
        'demarrage_brut': demarrage,
        'detail': '' if installe else (
            "L'unité cloudflared.service n'existe pas sur cette machine. "
            "Installez le tunnel avec « cloudflared service install <token> »."
        ),
    }


def executer(action):
    """Lance une des actions autorisées sur le service."""
    _require_linux()
    argv = ligne_de_commande(action)

    try:
        resultat = subprocess.run(
            argv, capture_output=True, text=True, timeout=DELAI_COMMANDE)
    except subprocess.TimeoutExpired:
        raise CloudflaredError(
            f'La commande n’a pas répondu en {DELAI_COMMANDE} secondes.')
    except OSError as exc:
        raise CloudflaredError(f'Commande introuvable : {exc}')

    if resultat.returncode != 0:
        detail = (resultat.stderr or resultat.stdout or '').strip()
        # Le cas de loin le plus fréquent, et le plus déroutant sans
        # explication : le compte de service n'a pas le droit. On nomme le
        # fichier à installer plutôt que de recopier le message de sudo.
        if 'password' in detail.lower() or 'sudoers' in detail.lower():
            raise CloudflaredError(
                'Le compte de service n’a pas le droit de piloter le tunnel. '
                'Installez le fichier sudoers /etc/sudoers.d/orion-cloudflared '
                '(fourni dans deployment/proxmox-appliance/sudoers/) puis '
                f'réessayez. Détail : {detail}')
        raise CloudflaredError(detail or f'systemctl {action} a échoué.')

    return {
        'ok': True,
        'returncode': resultat.returncode,
        'stdout': resultat.stdout.strip(),
        'stderr': resultat.stderr.strip(),
        'command': ' '.join(argv),
    }
