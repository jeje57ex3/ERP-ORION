"""Le pont vers les actions disque qui demandent root.

Même motif que `apps/system_updates/server_actions.py`, qui appelle
`shutdown` : la commande passée à `sudo` est **exactement** celle que
`deployment/proxmox-appliance/sudoers/orion-stockage` autorise, et un test
compare les deux. S'ils divergent, les boutons cessent de fonctionner sans
que rien ne le signale — c'est pour ça que ce test existe.

**Pourquoi les paramètres passent par l'entrée standard.** sudoers/orion-serveur
explique pourquoi un joker (« commande * ») accorde beaucoup plus qu'on ne
croit. Or le disque à préparer est un paramètre. Le faire voyager en JSON
sur stdin plutôt qu'en argument rend les trois règles sudo exactes, sans un
seul joker, et déplace toute la validation dans le script root — un fichier
que l'utilisateur « orion » peut exécuter et jamais écrire.

**Ce module ne valide presque rien, et c'est voulu.** Il serait tentant de
vérifier ici que le périphérique est bien un disque entier. Ce serait une
fausse sécurité : ce code tourne sous « orion », donc sous le compte même
qu'on cherche à contenir. Un contrôle écrit ici protège contre une erreur
d'interface, pas contre un attaquant qui aurait déjà la main sur
l'application. La validation qui compte est celle du script root.
"""

import json
import os
import subprocess

CHEMIN_DU_SCRIPT = '/usr/local/sbin/orion-stockage'

# Exactement les trois commandes autorisees par sudoers/orion-stockage.
# Un test compare cette liste au contenu du fichier.
COMMANDES_AUTORISEES = ('lister', 'preparer', 'demonter')

# Preparer un disque formate un systeme de fichiers : sur un disque de
# plusieurs teraoctets, mkfs.ext4 prend des minutes. Le script a sa propre
# limite interne ; celle-ci est la limite de patience de l'appelant.
DELAI_PAR_COMMANDE = {
    'lister': 30,
    'preparer': 2400,
    'demonter': 180,
}


class StockagePrivilegieIndisponible(Exception):
    """Le pont n'est pas installé, ou sudo le refuse."""


class ActionPrivilegieeRefusee(Exception):
    """Le script root a refusé l'action, avec sa raison."""


def est_disponible():
    """Vrai si le script est installé et exécutable depuis ce compte.

    Ne teste pas sudo : `sudo -n` échouerait en écrivant dans les
    journaux d'authentification à chaque affichage de la page, ce qui
    noierait les vraies tentatives sous du bruit.
    """
    return os.name == 'posix' and os.access(CHEMIN_DU_SCRIPT, os.X_OK)


def ligne_de_commande(commande):
    """La commande exacte, telle que sudoers doit l'autoriser."""
    if commande not in COMMANDES_AUTORISEES:
        raise ValueError(f'Commande non autorisée : {commande}')
    return ['sudo', '-n', CHEMIN_DU_SCRIPT, commande]


def _appeler(commande, demande=None):
    if os.name != 'posix':
        raise StockagePrivilegieIndisponible(
            'La préparation des disques n\'existe que sur le serveur Linux. '
            'Sur un poste de développement, cet écran reste en lecture.')

    if not os.path.exists(CHEMIN_DU_SCRIPT):
        raise StockagePrivilegieIndisponible(
            f'{CHEMIN_DU_SCRIPT} est absent. Installez-le depuis '
            f'deployment/proxmox-appliance/scripts/orion-stockage :\n'
            f'  install -o root -g orion -m 0750 orion-stockage '
            f'/usr/local/sbin/\n'
            f'puis le fichier sudoers fourni à côté.')

    entree = json.dumps(demande or {}, ensure_ascii=False)

    try:
        acheve = subprocess.run(
            ligne_de_commande(commande),
            input=entree, capture_output=True, text=True,
            timeout=DELAI_PAR_COMMANDE.get(commande, 300), shell=False)
    except subprocess.TimeoutExpired:
        raise ActionPrivilegieeRefusee(
            f'L\'opération « {commande} » n\'a pas répondu dans le délai '
            f'imparti. Le disque est peut-être en cours de formatage : '
            f'vérifiez l\'état des disques avant de recommencer.')
    except OSError as exc:
        raise StockagePrivilegieIndisponible(f'sudo introuvable : {exc}')

    detail = (acheve.stderr or '').strip()
    if detail and ('password' in detail.lower() or 'sudoers' in detail.lower()):
        raise StockagePrivilegieIndisponible(
            'sudo refuse cette commande au compte de service. Installez '
            '/etc/sudoers.d/orion-stockage (fourni dans '
            'deployment/proxmox-appliance/sudoers/), vérifiez-le avec '
            '« visudo -c », puis réessayez.')

    sortie = (acheve.stdout or '').strip()
    if not sortie:
        raise ActionPrivilegieeRefusee(
            f'L\'opération « {commande} » n\'a rien répondu. '
            f'{detail or "Aucun détail disponible."}')

    try:
        resultat = json.loads(sortie)
    except ValueError:
        raise ActionPrivilegieeRefusee(
            f'Réponse illisible de l\'assistant disque : {sortie[:300]}')

    if not resultat.get('ok'):
        raise ActionPrivilegieeRefusee(
            resultat.get('erreur') or 'Refus sans motif.')

    return resultat


# ── Les trois actions ──────────────────────────────────────────────────────

def lister_les_disques():
    """Les disques physiques, avec pour chacun s'il est utilisable et pourquoi."""
    return _appeler('lister')


def preparer_un_disque(peripherique, etiquette, effacer=False,
                       numero_de_serie=''):
    """Partitionne, formate, monte et inscrit dans fstab.

    `numero_de_serie` est celui que l'interface a MONTRÉ à l'utilisateur.
    Le script root le compare au matériel réellement présent et s'arrête
    s'il a changé : c'est ce qui empêche de formater le bon nom de
    périphérique sur le mauvais disque.
    """
    return _appeler('preparer', {
        'peripherique': peripherique,
        'etiquette': etiquette,
        'effacer': bool(effacer),
        'numero_de_serie': numero_de_serie or '',
    })


def demonter(point_de_montage):
    """Démonte un volume préparé par Orion."""
    return _appeler('demonter', {'point_de_montage': point_de_montage})
