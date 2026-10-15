"""Mise à disposition de l'application PC.

L'application de bureau est un conteneur WebView autour du serveur Orion : elle
ne duplique ni l'ERP ni les données, elle ouvre l'interface dans une fenêtre
native. Son installeur pèse environ 180 Mo — il n'est donc pas versionné, et ne
peut pas voyager avec le code.

Il est donc **déposé sur le serveur**, et cette page le propose. La
conséquence à accepter : tant que personne ne l'a déposé, il n'y a rien à
télécharger, et la page doit le dire clairement plutôt qu'offrir un lien mort.

Une règle de sécurité gouverne tout ce module : **aucun nom de fichier ne
vient jamais de la requête**. Le répertoire est parcouru, et seul un fichier
réellement présent peut être servi. Joindre un nom reçu au chemin du
répertoire -- même « validé » -- rouvre la traversée de répertoire, et le
processus tourne ici en tant qu'utilisateur ayant accès à la base et aux
sauvegardes.
"""

import unicodedata
from pathlib import Path

from django.conf import settings

EXTENSIONS = ('.exe', '.msi', '.zip', '.dmg', '.appimage', '.deb')
"""Ce qui peut raisonnablement être un installeur.

Volontairement restreint : parcourir le répertoire sans filtre proposerait au
téléchargement n'importe quel fichier qui s'y trouverait — un journal, une
sauvegarde déposée là par erreur.
"""


def repertoire():
    """Où l'installeur est attendu.

    Sous MEDIA_ROOT par défaut : c'est le volume persistant de l'appliance
    (/opt/orion/uploads), donc un emplacement qui survit aux mises à jour et
    qui est déjà sauvegardé. Un chemin hors de ce volume serait perdu au
    premier redéploiement.
    """
    chemin = getattr(settings, 'ORION_DESKTOP_DIR', '') or ''
    if chemin:
        return Path(chemin)
    return Path(settings.MEDIA_ROOT) / 'desktop'


def _lisible(octets):
    """Taille en Mo, telle qu'on l'annonce à quelqu'un qui va attendre."""
    if octets >= 1024 ** 3:
        return f'{octets / 1024 ** 3:.1f} Go'
    return f'{octets / 1024 ** 2:.0f} Mo'


def _etiquette(nom):
    """Ce que le fichier installe, d'après son nom.

    Les deux installeurs produits par le projet se distinguent par un seul
    mot, et la différence compte pour qui télécharge : l'un demande les droits
    administrateur, l'autre s'installe pour l'utilisateur courant. Confondre
    les deux fait échouer l'installation sur un poste où l'employé n'est pas
    administrateur — cas courant en entreprise.
    """
    sans_accent = unicodedata.normalize('NFKD', nom).encode(
        'ascii', 'ignore').decode('ascii').lower()
    if 'user' in sans_accent:
        return ('Installation pour mon compte',
                'Ne demande pas les droits administrateur.')
    if 'setup' in sans_accent or 'install' in sans_accent:
        return ('Installation pour tout le poste',
                'Demande les droits administrateur.')
    return ('Application PC', '')


def installeurs_disponibles():
    """Les installeurs présents, du plus récent au plus ancien.

    Le plus récent d'abord : après un nouveau build, c'est celui-là qu'on veut
    proposer, et laisser l'ordre alphabétique décider offrirait l'ancien.
    """
    dossier = repertoire()
    try:
        fichiers = [
            chemin for chemin in dossier.iterdir()
            if chemin.is_file()
            and chemin.suffix.lower() in EXTENSIONS
        ]
    except (OSError, ValueError):
        # Répertoire absent : ce n'est pas une anomalie, simplement rien de
        # déposé. La page le dira.
        return []

    fichiers.sort(key=lambda c: c.stat().st_mtime, reverse=True)

    liste = []
    for chemin in fichiers:
        infos = chemin.stat()
        titre, precision = _etiquette(chemin.name)
        liste.append({
            'nom': chemin.name,
            'titre': titre,
            'precision': precision,
            'taille': _lisible(infos.st_size),
            'octets': infos.st_size,
            'modifie_le': infos.st_mtime,
        })
    return liste


def trouver_installeur(nom_demande):
    """Le chemin de l'installeur nommé, ou None.

    Le nom reçu n'est JAMAIS joint au chemin du répertoire : il est comparé
    aux noms réellement présents. Un « ../../backend/.env » ne correspond donc
    à rien, et aucune normalisation de chemin n'a à être faite correctement
    pour que ce soit vrai — c'est la comparaison qui l'assure, pas une
    vérification qu'on pourrait oublier.
    """
    if not nom_demande:
        return None
    dossier = repertoire()
    for present in installeurs_disponibles():
        if present['nom'] == nom_demande:
            return dossier / present['nom']
    return None
