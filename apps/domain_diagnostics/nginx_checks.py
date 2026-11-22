from pathlib import Path

NGINX_DIRS = [
    '/etc/nginx/sites-enabled',
    '/etc/nginx/conf.d',
]


def find_nginx_files_for_domain(domain):
    matches = []
    for folder in NGINX_DIRS:
        path = Path(folder)
        if not path.exists():
            continue
        for file_path in path.glob('*'):
            if not file_path.is_file():
                continue
            try:
                content = file_path.read_text(errors='ignore')
            except Exception:
                continue
            if domain in content:
                matches.append(str(file_path))
    return matches


def check_nginx_server_name(domain):
    files = find_nginx_files_for_domain(domain)
    return {'domain': domain, 'found': bool(files), 'files': files}


# ─── /media/ servi depuis le disque ─────────────────────────────────────────
#
# `apps/core/media_access.py` applique sous /media/ un refus par défaut qui
# tient hors de ce préfixe les bulletins de paie, les relevés bancaires, les
# factures fournisseurs et les photos prises chez des clients.
#
# Un bloc `location /media/ { alias ...; }` dans Nginx sert ces fichiers
# depuis le disque : la requête n'atteint jamais cette politique, et une URL
# devinée suffit, sans compte. Deux des trois gabarits du dépôt portaient ce
# défaut (corrigé le 21/11/2026, voir docs/AUDIT-SECURITE-3.md).
#
# MAIS UNE MISE À JOUR NE RÉÉCRIT PAS /etc/nginx. Corriger les gabarits ne
# corrige donc pas une machine déjà installée — et personne ne pense à aller
# relire un fichier de configuration qu'on n'a pas touché depuis l'install.
# D'où ce contrôle, qui lit la configuration RÉELLEMENT en place et le dit
# dans l'écran de mise à jour.

_DEBUT_BLOC_MEDIA = 'location /media/'
_DIRECTIVES_DE_DISQUE = ('alias', 'root')


def _corps_des_blocs_media(contenu):
    """Le corps de chaque `location /media/ { ... }`, accolades comptées.

    Une recherche par ligne ne suffirait pas : il faut savoir ce qui est
    DANS le bloc, et un `root` posé au niveau du `server` ne compte pas.
    """
    blocs = []
    depart = 0
    while True:
        trouve = contenu.find(_DEBUT_BLOC_MEDIA, depart)
        if trouve == -1:
            return blocs
        ouvrante = contenu.find('{', trouve)
        if ouvrante == -1:
            return blocs
        profondeur = 1
        i = ouvrante + 1
        while i < len(contenu) and profondeur:
            if contenu[i] == '{':
                profondeur += 1
            elif contenu[i] == '}':
                profondeur -= 1
            i += 1
        blocs.append(contenu[ouvrante + 1:i - 1])
        depart = i


def media_servi_depuis_le_disque():
    """Les fichiers de configuration en place qui contournent la politique.

    Rend une liste de dictionnaires `{fichier, directive}`. Vide si tout va
    bien — ou si Nginx n'est pas présent, ce qui est le cas sur un poste de
    développement et dans les tests : **l'absence de Nginx n'est pas un
    défaut**, et la confondre avec un défaut ferait crier ce contrôle sur
    toutes les machines où il n'a rien à dire.
    """
    fautifs = []
    for dossier in NGINX_DIRS:
        chemin = Path(dossier)
        if not chemin.exists():
            continue
        for fichier in sorted(chemin.glob('*')):
            if not fichier.is_file():
                continue
            try:
                contenu = fichier.read_text(errors='ignore')
            except Exception:
                continue
            for bloc in _corps_des_blocs_media(contenu):
                for ligne in bloc.splitlines():
                    nue = ligne.strip()
                    if nue.startswith('#'):
                        continue
                    premier = nue.split(' ')[0].split('\t')[0]
                    if premier in _DIRECTIVES_DE_DISQUE:
                        fautifs.append({'fichier': str(fichier),
                                        'directive': premier})
    return fautifs
