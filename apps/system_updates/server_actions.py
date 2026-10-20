"""Redémarrage et extinction du serveur hôte depuis Orion ERP.

**L'action est PROGRAMMÉE à une minute, jamais immédiate.** `reboot` ou
`shutdown -h now` couperait gunicorn avant que la réponse HTTP de
confirmation ne parte, laissant l'administrateur devant une page qui ne
charge jamais — sans savoir si l'action a été prise en compte. Une minute
suffit à répondre, et `shutdown -c` permet encore d'annuler.

**Ce que ce module ne peut pas faire : ALLUMER le serveur.** Une machine
éteinte ne sert pas de page web, donc ne peut pas recevoir l'ordre de
démarrer. Aucune ligne de code ne contournera cela. L'écran de confirmation
rappelle donc comment rallumer depuis l'extérieur — console Proxmox,
`qm start`, IPMI — avant d'éteindre.

**Les commandes sont exactement celles que sudoers autorise.** Le compte de
service (`orion`) n'est pas administrateur : il reçoit le droit de lancer
ces trois lignes-là, et rien d'autre. La liste vit dans
`deployment/proxmox-appliance/sudoers/orion-serveur`, et un test compare
les deux — si elles divergent, les boutons cessent de fonctionner sans que
rien ne le dise, à l'endroit le moins pratique pour s'en apercevoir.

Pas de `shell=True` ici, et pas d'interpolation : l'argument de délai est
une constante du module, pas une donnée de requête. `sudo -n` interdit
toute attente de mot de passe — sans lui, un sudoers mal installé ferait
patienter la requête jusqu'au délai d'expiration au lieu d'échouer tout de
suite avec un message clair.
"""

import os
import platform
import subprocess

DELAI_MINUTES = 1
"""Fixe, et non paramétrable : sudoers autorise la ligne de commande
EXACTE. Un délai variable demanderait un joker dans la règle sudoers, or un
joker y est précisément ce qui transforme une permission étroite en
permission large. Un paramètre qui ne peut pas varier vaut moins que pas de
paramètre."""

DELAI_COMMANDE = 15

CHEMINS_SHUTDOWN = ('/sbin/shutdown', '/usr/sbin/shutdown')

ARGUMENTS = {
    'reboot': ('-r', f'+{DELAI_MINUTES}'),
    'shutdown': ('-h', f'+{DELAI_MINUTES}'),
    'cancel': ('-c',),
}


class ServerActionError(Exception):
    """Ce qui a empêché l'action, dit dans des termes exploitables."""


def chemin_shutdown():
    """Le chemin de `shutdown` sur cette machine.

    Les deux emplacements existent selon les distributions. Le chemin doit
    être ABSOLU et correspondre à la règle sudoers : `sudo shutdown` tout
    court dépendrait du PATH du processus, que systemd ne garantit pas.
    """
    for chemin in CHEMINS_SHUTDOWN:
        if os.path.exists(chemin):
            return chemin
    return CHEMINS_SHUTDOWN[0]


def ligne_de_commande(action):
    """La commande exacte, telle que sudoers doit l'autoriser."""
    if action not in ARGUMENTS:
        raise ServerActionError(f'Action inconnue : {action}.')
    return ['sudo', '-n', chemin_shutdown(), *ARGUMENTS[action]]


def _require_linux():
    if platform.system() != 'Linux':
        raise ServerActionError(
            "Action serveur disponible uniquement sur l'appliance Linux, "
            "pas sur ce poste de développement."
        )


def _executer(action):
    _require_linux()
    argv = ligne_de_commande(action)
    try:
        resultat = subprocess.run(
            argv, capture_output=True, text=True, timeout=DELAI_COMMANDE,
        )
    except subprocess.TimeoutExpired:
        raise ServerActionError(
            'La commande n’a pas répondu en '
            f'{DELAI_COMMANDE} secondes.')
    except OSError as exc:
        raise ServerActionError(f'Commande introuvable : {exc}')

    if resultat.returncode != 0:
        detail = (resultat.stderr or resultat.stdout or '').strip()
        # Le cas de loin le plus fréquent, et le plus déroutant sans
        # explication : le compte de service n'a pas le droit. On nomme le
        # fichier à installer plutôt que de recopier le message de sudo.
        if 'password' in detail.lower() or 'sudoers' in detail.lower():
            raise ServerActionError(
                'Le compte de service n’a pas le droit d’éteindre ce '
                'serveur. Installez le fichier sudoers '
                '/etc/sudoers.d/orion-serveur (fourni dans '
                'deployment/proxmox-appliance/sudoers/) puis réessayez. '
                f'Détail : {detail}')
        raise ServerActionError(detail or 'Commande shutdown échouée.')

    return {
        'ok': True,
        'returncode': resultat.returncode,
        'stdout': resultat.stdout.strip(),
        'stderr': resultat.stderr.strip(),
        'command': ' '.join(argv),
    }


def schedule_reboot():
    """Programme un redémarrage dans DELAI_MINUTES minute(s)."""
    return _executer('reboot')


def schedule_shutdown():
    """Programme une extinction dans DELAI_MINUTES minute(s).

    Rappel : le serveur ne pourra PAS être rallumé depuis Orion.
    """
    return _executer('shutdown')


def cancel_scheduled_action():
    """Annule le redémarrage ou l'extinction programmé."""
    return _executer('cancel')
