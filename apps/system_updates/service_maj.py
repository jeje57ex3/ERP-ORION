"""Déclencher la mise à jour système, sans que l'interface en soit le maillon.

**Le bouton ne fait plus le travail : il le DÉCLENCHE.** Le mécanisme
applicatif (`run_system_update`) cumulait quatre dépendances qui le rendaient
indisponible précisément quand il fallait déployer un correctif :

1. sa première instruction est une lecture en base (`get_update_settings`) :
   il ne démarre pas si MySQL est tombé ;
2. il tourne dans un worker gunicorn : un `orion-backend` tué par manque de
   mémoire emporte la mise à jour en cours de route ;
3. il tourne sous l'utilisateur « orion », qui n'est pas administrateur — il
   ne peut donc rafraîchir ni les paquets apt, ni `/etc/sudoers.d/`, ni
   `/usr/local/sbin/orion-stockage`, ni les unités systemd. C'est ainsi que
   l'assistant de préparation des disques est resté absent d'une machine
   pourtant mise à jour plusieurs fois ;
4. il exige que l'interface web réponde.

Ce module confie le travail à `orion-update.service`, lancé par systemd. La
mise à jour survit alors à un redémarrage du backend, à un onglet fermé et à
une session coupée ; elle tourne en root ; et **la même mise à jour se
déclenche sans interface web**, depuis l'hyperviseur :

    qm guest exec <vmid> --timeout 60 -- systemctl start orion-update.service

L'interface devient un confort, plus une dépendance. C'est le point de toute
l'affaire.

**La commande est exactement celle que sudoers autorise.** La liste vit dans
`deployment/proxmox-appliance/sudoers/orion-maj`, et un test compare les
deux : si elles divergent, le bouton cesse de fonctionner sans que rien ne le
signale, à l'endroit le moins pratique pour s'en apercevoir.

**LIRE l'état ne demande aucun droit**, et c'est délibéré : `systemctl
is-active` répond à tout le monde, et l'avancement détaillé est un fichier
JSON écrit par le script. Aucune permission n'est donc accordée pour la
consultation — et l'état reste lisible quand la base est en panne, ce que
`SystemUpdateRun` ne permettait pas.
"""

import json
import os
import platform
import subprocess
from pathlib import Path

UNITE = 'orion-update.service'
"""Fixe, et non paramétrable : sudoers autorise la chaîne EXACTE. Un nom
d'unité variable demanderait un joker dans la règle, or « systemctl * »
donnerait à « orion » le contrôle de tous les services de la machine."""

CHEMIN_DE_L_UNITE = Path('/etc/systemd/system') / UNITE

CHEMINS_SYSTEMCTL = ('/bin/systemctl', '/usr/bin/systemctl')

FICHIER_ETAT = Path('/opt/orion/logs/maj-etat.json')

DELAI_COMMANDE = 15
"""`systemctl start` sur une unité `oneshot` rend la main dès le lancement,
il n'attend pas la fin du travail. Quinze secondes couvrent largement le
démarrage ; au-delà, c'est que sudo ou systemd ne répondent pas."""


class ServiceDeMiseAJourIndisponible(Exception):
    """Ce qui empêche de déclencher, dit dans des termes exploitables."""


def chemin_systemctl():
    """Le chemin de `systemctl` sur cette machine.

    Les deux emplacements existent selon les distributions. Le chemin doit
    être ABSOLU et correspondre à la règle sudoers : `sudo systemctl` tout
    court dépendrait du PATH du processus, que systemd ne garantit pas.
    """
    for chemin in CHEMINS_SYSTEMCTL:
        if os.path.exists(chemin):
            return chemin
    return CHEMINS_SYSTEMCTL[0]


def ligne_de_commande():
    """La commande exacte, telle que sudoers doit l'autoriser."""
    return ['sudo', '-n', chemin_systemctl(), 'start', UNITE]


def est_disponible():
    """Vrai si l'unité systemd est installée sur cette machine.

    Ne teste pas sudo : `sudo -n` échouerait en écrivant dans les journaux
    d'authentification à chaque affichage de la page, ce qui noierait les
    vraies tentatives sous du bruit. Même raisonnement que
    `stockage_privilegie.est_disponible`.
    """
    return platform.system() == 'Linux' and CHEMIN_DE_L_UNITE.is_file()


def declencher():
    """Lance l'unité et rend la main tout de suite.

    Ne renvoie PAS le résultat de la mise à jour : elle vient de commencer
    et durera plusieurs minutes. L'appelant doit renvoyer l'utilisateur vers
    l'état, pas lui faire attendre une réponse qui n'arrivera pas avant le
    délai d'expiration de gunicorn.
    """
    if platform.system() != 'Linux':
        raise ServiceDeMiseAJourIndisponible(
            'La mise à jour système n\'existe que sur l\'appliance Linux, '
            'pas sur un poste de développement.')

    if not CHEMIN_DE_L_UNITE.is_file():
        raise ServiceDeMiseAJourIndisponible(
            f'{CHEMIN_DE_L_UNITE} est absent : l\'unité systemd n\'est pas '
            f'installée. Elle est livrée par le dépôt dans '
            f'deployment/proxmox-appliance/systemd/, et posée par '
            f'update_orion.sh — qu\'il faut donc lancer une fois en root '
            f'depuis l\'hyperviseur.')

    try:
        acheve = subprocess.run(ligne_de_commande(), capture_output=True,
                                text=True, timeout=DELAI_COMMANDE,
                                shell=False)
    except subprocess.TimeoutExpired:
        raise ServiceDeMiseAJourIndisponible(
            'systemd n\'a pas répondu dans le délai imparti. La mise à jour '
            'a peut-être démarré : vérifiez l\'état avant de réessayer.')
    except OSError as exc:
        raise ServiceDeMiseAJourIndisponible(f'sudo introuvable : {exc}')

    if acheve.returncode != 0:
        detail = (acheve.stderr or acheve.stdout or '').strip()
        if 'password' in detail.lower() or 'sudoers' in detail.lower():
            raise ServiceDeMiseAJourIndisponible(
                'sudo refuse cette commande au compte de service. Installez '
                '/etc/sudoers.d/orion-maj (fourni dans '
                'deployment/proxmox-appliance/sudoers/), vérifiez-le avec '
                '« visudo -c », puis réessayez.')
        raise ServiceDeMiseAJourIndisponible(
            detail or 'systemd a refusé de démarrer l\'unité, sans détail.')

    return True


def _unite_active():
    """« active », « failed », « inactive »… ou None si on ne sait pas.

    `is-active` sort en code non nul quand l'unité n'est pas active : son
    code de retour n'est donc pas un indicateur d'erreur, seule sa sortie
    compte.
    """
    if platform.system() != 'Linux':
        return None
    try:
        acheve = subprocess.run(
            [chemin_systemctl(), 'is-active', UNITE],
            capture_output=True, text=True, timeout=5, shell=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return (acheve.stdout or '').strip() or None


def etat():
    """Où en est la mise à jour, sans toucher à la base.

    Les deux sources sont complémentaires : systemd dit si le travail
    TOURNE, le fichier dit à quelle étape il en était et comment il s'est
    terminé. Un fichier illisible ou absent n'est pas une erreur — il n'y a
    simplement jamais eu de mise à jour par ce chemin.
    """
    donnees = None
    try:
        donnees = json.loads(FICHIER_ETAT.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        donnees = None
    if not isinstance(donnees, dict):
        donnees = None

    actif = _unite_active()
    return {
        'disponible': est_disponible(),
        'unite': UNITE,
        'etat_systemd': actif,
        'en_cours': actif == 'activating',
        'fichier': str(FICHIER_ETAT),
        'derniere_etape': (donnees or {}).get('etape'),
        'dernier_code': (donnees or {}).get('code'),
        'dernier_horodatage': (donnees or {}).get('horodatage'),
        'dernier_mode': (donnees or {}).get('mode'),
    }
