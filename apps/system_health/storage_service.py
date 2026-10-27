"""Sur quel disque chaque categorie de fichiers se trouve, et comment l'y mettre.

**Ce que ce module n'est pas.** Il ne detecte pas les disques : cela existe
deja et fonctionne. `services.get_disk_partitions_usage()` enumere tous les
volumes montes via `psutil.disk_partitions()`, `get_disk_allocations()` lit
`lsblk` pour les partitions non montees et l'espace non alloue, et la page
/orion-admin/sante-systeme/disques/ les affiche. Un disque ajoute a la
machine y apparait des qu'il est monte. `volumes()` ci-dessous DELEGUE a
cette fonction : deux enumerations concurrentes finiraient par divergar,
comme ont diverge `apps/core/menu.py` et `NAV_MODULES`.

**Ce qui manquait vraiment**, et que ce module apporte :

1. La repartition des donnees (`get_storage_breakdown`) donnait le chemin et
   la taille de chaque emplacement, mais **pas le volume qui le porte** ni
   l'espace libre de ce volume. Impossible de lire « les medias sont sur
   /mnt/donnees, 450 Go libres » -- donc impossible de decider quoi deplacer.
2. Les emplacements n'etaient pas parametrables. `MEDIA_ROOT` et
   `STATIC_ROOT` etaient ecrits « BASE_DIR / 'media' », codes en dur : la
   seule facon de poser les medias ailleurs etait un lien symbolique pose a
   la main en SSH, ce que fait l'appliance ($ORION_HOME/uploads <-
   backend/media). Ils passent desormais par `config()`.
3. Rien ne disait COMMENT deplacer une categorie sans se tromper.

**Ce module ne modifie rien.** Il mesure, et il redige les commandes que
l'administrateur executera lui-meme. Deplacer des fichiers que gunicorn
sert, remonter un disque et redemarrer un service demande root, prend le
temps d'un `rsync`, et laisse -- si cela s'interrompt au mauvais moment --
des medias a moitie copies. Cette decision reste a l'humain devant la
console.
"""

import os
from pathlib import Path

# Au-delà, on arrête de compter et on annonce « au moins ». Marcher dans un
# dossier de médias de plusieurs centaines de milliers de fichiers bloquerait
# l'affichage de la page plusieurs secondes.
LIMITE_FICHIERS_COMPTES = 20000


def _octets_en_go(octets):
    return round((octets or 0) / 1e9, 2)


def volumes():
    """Les systèmes de fichiers réels, avec leur occupation.

    Délègue à `services.get_disk_partitions_usage()`, qui fait déjà ce
    travail et dont la liste d'exclusions (`_EXCLUDED_FSTYPES`) est celle
    que la page des disques utilise. Dupliquer l'énumération aurait
    garanti qu'un jour les deux ne disent plus la même chose.

    Les clés sont renommées en français pour ce module, mais les valeurs
    sont celles de la fonction d'origine — un seul endroit mesure.
    """
    from .services import get_disk_partitions_usage

    return [
        {
            'point_de_montage': p['mountpoint'],
            'peripherique': p['device'],
            'systeme_de_fichiers': p['fstype'],
            'total_go': p['total_gb'],
            'utilise_go': p['used_gb'],
            'libre_go': p['free_gb'],
            'pourcentage': p['percent'],
            'statut': p['status'],
        }
        for p in get_disk_partitions_usage()
    ]


def volume_du_chemin(chemin, liste=None):
    """Le volume qui porte ce chemin : le point de montage le plus long.

    Le plus long et non le premier : `/` est un préfixe de tout, donc une
    comparaison naïve attribuerait `/mnt/donnees/media` à la racine — et
    la page annoncerait l'espace libre du mauvais disque.
    """
    if liste is None:
        liste = volumes()
    if not liste:
        return None

    # `normpath` et NON `resolve()` : cette fonction fait de l'arithmetique
    # de chemins, pas de la resolution de liens. `emplacements()` resout
    # deja les liens symboliques avant d'appeler ici -- resoudre une
    # seconde fois melangeait les conventions (sous Windows, `resolve()`
    # reecrit « /mnt/donnees » en « C:\mnt\donnees », et la comparaison
    # avec un point de montage POSIX levait ValueError, donc rendait None).
    cible = os.path.normpath(str(chemin))

    meilleur = None
    for volume in liste:
        # Le point de montage passe par le MEME normpath que la cible. Les
        # normaliser d'un seul cote faisait echouer la comparaison la ou
        # les deux conventions se croisent : normpath('/mnt/donnees/x')
        # rend des antislashs sous Windows, et « \mnt\donnees » n'est pas
        # egal a « /mnt/donnees ».
        point = os.path.normpath(volume['point_de_montage'])
        # `os.path.commonpath` plutôt qu'un startswith : « /mnt/donnees2 »
        # commence par « /mnt/donnees » sans être dessous.
        try:
            if os.path.commonpath([cible, point]) != point:
                continue
        except ValueError:
            # Lecteurs différents sous Windows (C: et D:) : pas comparables.
            continue
        if meilleur is None or len(point) > meilleur[1]:
            meilleur = (volume, len(point))
    return meilleur[0] if meilleur else None


def taille_du_dossier(chemin, limite=LIMITE_FICHIERS_COMPTES):
    """Taille d'un dossier, bornée en nombre de fichiers parcourus.

    Rend `(octets, complet)`. `complet` à False signifie « au moins » :
    la page doit le dire plutôt que d'afficher un chiffre faux.

    Ne suit pas les liens symboliques de répertoires, pour ne pas compter
    deux fois `backend/media` et `$ORION_HOME/uploads`, qui sont le même
    dossier sur l'appliance.
    """
    total = 0
    comptes = 0
    chemin = str(chemin)
    if not os.path.isdir(chemin):
        return 0, True

    for racine, dossiers, fichiers in os.walk(chemin, followlinks=False):
        for nom in fichiers:
            try:
                total += os.lstat(os.path.join(racine, nom)).st_size
            except OSError:
                continue
            comptes += 1
            if comptes >= limite:
                return total, False
    return total, True


# ─── Les catégories de fichiers de l'ERP ────────────────────────────────────
#
# Trois catégories seulement, et c'est un choix : les données MySQL
# (`$ORION_HOME/docker/mysql`) n'y sont PAS. Les déplacer demande d'arrêter
# le conteneur, et c'est l'endroit où une erreur coûte le plus cher ;
# ce n'est pas une case à cocher dans une page web.

CATEGORIES = [
    {
        'cle': 'medias',
        'nom': 'Médias et documents',
        'reglage': 'MEDIA_ROOT',
        'variable_env': 'MEDIA_ROOT',
        'contenu': 'Photos, PDF, documents RH privés, images de '
                   "l'éditeur visuel, installeurs mobiles.",
        'purge': 'Jamais purgé — grossit indéfiniment.',
        'deplacable': True,
    },
    {
        'cle': 'sauvegardes',
        'nom': 'Sauvegardes',
        'reglage': 'BACKUP_DIR',
        'variable_env': 'BACKUP_DIR',
        'contenu': 'Archives de l\'ERP, celles qu\'on télécharge.',
        'purge': 'Selon ORION_BACKUP_RETENTION_DAYS.',
        'deplacable': True,
        'note': 'Les poser sur un autre disque que les données est un '
                'vrai gain : un disque qui meurt n\'emporte pas les deux.',
    },
    {
        'cle': 'journaux',
        'nom': 'Journaux',
        'reglage': 'LOG_DIR',
        'variable_env': 'LOG_DIR',
        'contenu': 'Journaux Django, gunicorn et Celery.',
        'purge': 'Rotation 10 Mo x 10 par fichier — donc borné.',
        'deplacable': True,
    },
    {
        'cle': 'statiques',
        'nom': 'Fichiers statiques',
        'reglage': 'STATIC_ROOT',
        'variable_env': 'STATIC_ROOT',
        'contenu': 'CSS, JS et images du thème, produits par collectstatic.',
        'purge': 'Réécrit à chaque mise à jour.',
        'deplacable': False,
        'note': 'Techniquement déplaçable, mais sans intérêt : réécrit à '
                'chaque déploiement et de taille stable.',
    },
]


def emplacements(mesurer_tailles=True):
    """Où chaque catégorie de fichiers se trouve réellement, et sur quel disque.

    Resout les liens symboliques : sur l'appliance, `backend/media` est un
    lien vers `$ORION_HOME/uploads`. Afficher le chemin configuré sans le
    chemin réel laisserait croire que les médias sont sous le dossier de
    l'application, et ferait regarder le mauvais disque.
    """
    from django.conf import settings

    liste = volumes()
    resultat = []

    for categorie in CATEGORIES:
        configure = getattr(settings, categorie['reglage'], None)
        if configure is None:
            continue
        configure = Path(str(configure))
        try:
            reel = configure.resolve()
        except (OSError, ValueError):
            reel = configure

        octets, complet = (taille_du_dossier(reel) if mesurer_tailles
                           else (None, True))

        resultat.append({
            **categorie,
            'chemin_configure': str(configure),
            'chemin_reel': str(reel),
            'est_un_lien': configure.is_symlink(),
            'existe': configure.exists(),
            'taille_octets': octets,
            'taille_go': _octets_en_go(octets) if octets is not None else None,
            'taille_complete': complet,
            'volume': volume_du_chemin(reel, liste),
        })

    return resultat


def volume_le_plus_rempli(liste=None):
    """Le volume le plus occupé, celui sur lequel une alerte doit porter.

    C'est la lacune que les capteurs avaient : ils ne regardaient que `/`,
    donc un `/mnt/donnees` à 99 % ne déclenchait rien.
    """
    liste = liste if liste is not None else volumes()
    if not liste:
        return None
    return max(liste, key=lambda v: v['pourcentage'])


def commandes_de_migration(cle_categorie, point_de_montage):
    """Les commandes exactes pour déplacer une catégorie sur un autre disque.

    Rédigées et non exécutées. L'ERP tourne sous un compte sans privilèges,
    le `rsync` d'un dossier de médias prend le temps qu'il prend, et une
    interruption au mauvais moment laisse les fichiers à moitié copiés.
    L'administrateur les lit, les comprend et les lance.

    L'ordre compte et il est volontaire : copier d'abord (l'ERP continue de
    servir l'ancien emplacement), basculer le réglage ensuite, ne supprimer
    l'ancien dossier qu'après vérification — jamais dans la même commande.
    """
    categorie = next((c for c in CATEGORIES if c['cle'] == cle_categorie), None)
    if categorie is None:
        raise ValueError(f'Catégorie inconnue : {cle_categorie}')

    courant = next(
        (e for e in emplacements(mesurer_tailles=False)
         if e['cle'] == cle_categorie), None)
    source = courant['chemin_reel'] if courant else '<chemin actuel>'

    point = point_de_montage.rstrip('/') or '/'
    destination = f"{point}/orion/{cle_categorie}"

    etapes = [
        {
            'titre': 'Vérifier que le disque est monté au démarrage',
            'commentaire':
                "Sans ligne dans /etc/fstab, le disque n'est plus monté "
                "après un redémarrage : l'ERP écrirait alors dans un dossier "
                "vide du disque système, sans rien signaler.",
            'commandes': [
                f'findmnt -n {point} || echo "ATTENTION : {point} n\'est pas monté"',
                f'grep -q " {point} " /etc/fstab && echo "fstab : OK" '
                f'|| echo "ATTENTION : absent de /etc/fstab"',
            ],
        },
        {
            'titre': 'Créer la destination',
            'commentaire': "Le propriétaire doit être le compte qui fait "
                           "tourner l'ERP, sinon il ne pourra pas y écrire.",
            'commandes': [
                f'sudo mkdir -p {destination}',
                f'sudo chown -R orion:orion {destination}',
            ],
        },
        {
            'titre': 'Copier les fichiers',
            'commentaire':
                "Copie et non déplacement : l'ERP continue de servir "
                "l'ancien emplacement pendant toute la durée du transfert. "
                "Relancer la même commande reprend là où elle s'est "
                "arrêtée, et le second passage confirme que rien ne manque.",
            'commandes': [
                f'sudo rsync -aH --info=progress2 {source}/ {destination}/',
                f'sudo rsync -aHn --delete {source}/ {destination}/ '
                f'| tail -5   # second passage : doit ne rien lister',
            ],
        },
        {
            'titre': 'Basculer le réglage',
            'commentaire':
                f"L'ERP lit {categorie['variable_env']} dans "
                f"/opt/orion/backend/.env. Un chemin absolu y remplace le "
                f"dossier de l'application.",
            'commandes': [
                "sudo cp /opt/orion/backend/.env /opt/orion/backend/.env.avant-disque",
                f'sudo sed -i \'s#^{categorie["variable_env"]}=.*#'
                f'{categorie["variable_env"]}="{destination}/"#\' '
                f'/opt/orion/backend/.env',
                f'grep {categorie["variable_env"]} /opt/orion/backend/.env',
            ],
        },
        {
            'titre': 'Redémarrer et vérifier',
            'commentaire':
                "Le réglage est lu au démarrage du processus : sans "
                "redémarrage, l'ERP continue d'écrire à l'ancien endroit.",
            'commandes': [
                'sudo systemctl restart orion-backend orion-celery',
                '/opt/orion/scripts/orion-disk.sh status | head -30',
            ],
        },
        {
            'titre': "Supprimer l'ancien dossier — plus tard",
            'commentaire':
                "À ne faire qu'après avoir vérifié dans l'ERP que les "
                "fichiers sont bien lus depuis le nouveau disque. Gardez "
                "l'ancien dossier quelques jours : c'est votre filet.",
            'commandes': [f'# sudo rm -rf {source}'],
        },
    ]

    if cle_categorie == 'medias':
        etapes[3]['commentaire'] += (
            " Sur l'appliance, backend/media est un LIEN vers "
            "$ORION_HOME/uploads : le réglage absolu prend le dessus, "
            "mais pensez à retirer le lien devenu inutile."
        )

    return {
        'categorie': categorie,
        'source': source,
        'destination': destination,
        'etapes': etapes,
    }
