"""Tout ce que le code importe doit être DANS LE DÉPÔT.

Trois pannes en une seule journée, toutes de la même cause : j'ai livré du
code qui référence des fichiers absents du dépôt, et j'ai vérifié sur mon
disque — où ils sont présents depuis le début — au lieu de vérifier ce que
le dépôt contient.

  1. `templates/site_builder/*.html` commités, leurs cinq fichiers
     statiques non. Avec le stockage à manifeste de WhiteNoise, les pages
     de l'éditeur visuel répondaient 500.
  2. `apps/ecommerce/urls.py` commité avec `from . import views_siecle`,
     et `views_siecle.py` non versionné. La conf d'URLs ne chargeait plus.
  3. Huit entrées `INSTALLED_APPS` commitées, les sources des huit
     applications non — `apps/orders` n'avait **aucun** de ses huit
     fichiers sur le dépôt. Django ne démarrait pas du tout : gunicorn
     mourait au lancement et nginx rendait **502 Bad Gateway** sur tout
     l'ERP.

`manage.py check` ne peut rien voir : il lit le disque de travail. Les
tests non plus. Seule une comparaison avec `git ls-files` le voit, et
c'est ce que fait ce fichier.

Il n'interdit pas de garder des fichiers hors du dépôt — un brouillon, un
module en cours. Il interdit qu'un fichier **versionné** en dépende.
"""

import os
import re
import subprocess

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _fichiers_suivis():
    """L'ensemble des chemins connus de git, ou None s'il est indisponible.

    L'index et non l'arbre de travail : c'est toute la question. Un fichier
    present sur le disque et absent d'ici n'existera pas sur le serveur.
    """
    try:
        acheve = subprocess.run(['git', 'ls-files'], cwd=RACINE,
                                capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError):
        return None
    if acheve.returncode != 0:
        return None
    return {l.strip().replace('\\', '/') for l in acheve.stdout.splitlines()
            if l.strip()}


def _suivis_ou_saute():
    suivis = _fichiers_suivis()
    if suivis is None:
        pytest.skip('git indisponible : ce test compare au contenu du depot.')
    if len(suivis) < 100:
        pytest.skip('Depot trop petit pour que la comparaison ait un sens.')
    return suivis


def _module_est_suivi(chemin_pointe, suivis):
    """Un module Python est-il dans le depot, en .py ou en paquet ?"""
    base = chemin_pointe.replace('.', '/')
    return f'{base}.py' in suivis or f'{base}/__init__.py' in suivis


# ── 1. INSTALLED_APPS ──────────────────────────────────────────────────────

def test_chaque_application_installee_est_versionnee():
    """LE test de la panne du 502.

    Django lit INSTALLED_APPS au demarrage et importe chaque entree. Une
    seule qui ne resout pas empeche le processus entier de se lancer :
    aucune requete n'aboutit, et nginx ne peut que rendre 502.
    """
    from django.conf import settings

    suivis = _suivis_ou_saute()

    absents = []
    for entree in settings.INSTALLED_APPS:
        if not entree.startswith('apps.'):
            continue
        # « apps.x.apps.XConfig » designe le module « apps.x.apps ».
        morceaux = entree.split('.')
        if morceaux[-1][:1].isupper():
            morceaux = morceaux[:-1]
        module = '.'.join(morceaux)
        if not _module_est_suivi(module, suivis):
            absents.append(f'{entree}  ->  {module.replace(".", "/")}.py')

    assert not absents, (
        'Ces applications sont declarees dans INSTALLED_APPS et leurs '
        'fichiers ne sont PAS dans le depot. Django ne demarrera pas sur '
        'le serveur : 502 sur tout l ERP.\n  ' + '\n  '.join(absents))


def test_chaque_application_installee_a_son_paquet_complet():
    """Le module de configuration ne suffit pas.

    Une application dont seul `apps.py` serait versionne se chargerait,
    puis echouerait des qu'on touche a ses modeles, ses vues ou ses
    gabarits. C'est l'etat exact dans lequel j'avais laisse six des huit
    applications : un seul fichier sur le depot.
    """
    from django.apps import apps as registre

    suivis = _suivis_ou_saute()

    incomplets = []
    for config in registre.get_app_configs():
        if not config.name.startswith('apps.'):
            continue
        prefixe = config.name.replace('.', '/') + '/'
        au_depot = len([f for f in suivis if f.startswith(prefixe)])
        sur_disque = 0
        for dossier, sous, fichiers in os.walk(
                os.path.join(RACINE, *config.name.split('.'))):
            sous[:] = [s for s in sous if s != '__pycache__']
            sur_disque += len([f for f in fichiers if f.endswith('.py')])

        # Un ecart de plus de la moitie signale une application dont
        # l'essentiel manque, et non un simple brouillon laisse de cote.
        if sur_disque and au_depot * 2 < sur_disque:
            incomplets.append(
                f'{config.name} : {au_depot} fichier(s) au depot pour '
                f'{sur_disque} sur le disque')

    assert not incomplets, (
        'Ces applications sont chargees et l essentiel de leurs fichiers '
        'manque au depot :\n  ' + '\n  '.join(incomplets))


# ── 2. Les include() d'URL ────────────────────────────────────────────────

def test_chaque_conf_d_url_incluse_est_versionnee():
    """Une conf d'URL absente casse la resolution de TOUTES les adresses.

    Le resolveur charge l'arbre entier a la premiere requete : un include
    qui ne resout pas met le site entier a terre, pas seulement sa branche.
    """
    suivis = _suivis_ou_saute()

    chemin = os.path.join(RACINE, 'erp_btp', 'urls.py')
    with open(chemin, encoding='utf-8') as fichier:
        contenu = fichier.read()

    absents = []
    for module in re.findall(r"include\(\s*['\"](apps\.[a-z_.]+)['\"]",
                             contenu):
        if not _module_est_suivi(module, suivis):
            absents.append(module)

    assert not absents, (
        'Ces confs d URL sont incluses et absentes du depot :\n  '
        + '\n  '.join(absents))


# ── 3. Les imports nommés, d'où qu'ils viennent ──────────────────────────

def _imports_exigeants(source):
    """Les modules du projet qu'un fichier exige VRAIMENT à l'import.

    Analyse syntaxique et non expression régulière, pour une raison
    précise : un import place dans un `try / except ImportError` est
    DELIBEREMENT tolerant. C'est le cas de
    `apps/orion_website/views.py`, qui tente
    `from apps.mobile_app.models import MobileRelease` et retombe sur None
    -- le module n'existe pas, et la page s'affiche quand meme en annoncant
    « bientot disponible ». Le signaler serait un faux positif, et ce
    fichier en avait un.

    Rend des couples (module_pointe, est_relatif).
    """
    import ast

    try:
        arbre = ast.parse(source)
    except SyntaxError:
        return []

    toleres = set()
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.Try):
            continue
        tolerant = any(
            gestionnaire.type is None
            or (isinstance(gestionnaire.type, ast.Name)
                and gestionnaire.type.id in ('ImportError',
                                             'ModuleNotFoundError',
                                             'Exception'))
            or (isinstance(gestionnaire.type, ast.Tuple)
                and any(isinstance(e, ast.Name)
                        and e.id in ('ImportError', 'ModuleNotFoundError',
                                     'Exception')
                        for e in gestionnaire.type.elts))
            for gestionnaire in noeud.handlers)
        if not tolerant:
            continue
        for interne in ast.walk(noeud):
            if isinstance(interne, (ast.Import, ast.ImportFrom)):
                toleres.add(id(interne))

    exiges = []
    for noeud in ast.walk(arbre):
        if id(noeud) in toleres:
            continue
        if isinstance(noeud, ast.Import):
            for alias in noeud.names:
                if alias.name.startswith('apps.'):
                    exiges.append((alias.name, False))
        elif isinstance(noeud, ast.ImportFrom):
            if noeud.level == 1 and noeud.module:
                exiges.append((noeud.module, True))
            elif noeud.level == 0 and (noeud.module or '').startswith('apps.'):
                exiges.append((noeud.module, False))
    return exiges


def test_chaque_module_importe_par_du_code_versionne_est_versionne():
    """Le test de la panne de `views_siecle`.

    `apps/ecommerce/urls.py` etait versionne et faisait
    `from . import views_siecle` ; le module non. Sur le serveur :
    ModuleNotFoundError au chargement de la conf d'URL.

    On ne lit que les fichiers VERSIONNES : un brouillon hors depot peut
    importer ce qu'il veut, il ne partira pas. Ce qui compte est qu'aucun
    fichier livre ne dependra d'un fichier qui ne l'est pas.
    """
    suivis = _suivis_ou_saute()

    manquants = {}
    for suivi in sorted(suivis):
        if not suivi.endswith('.py'):
            continue
        if suivi.startswith('tests/'):
            # Les tests ne partent pas sur le serveur : leurs imports ne
            # peuvent pas l'empecher de demarrer. Ils sont couverts par le
            # fait qu'ils tournent.
            continue
        chemin = os.path.join(RACINE, suivi)
        try:
            with open(chemin, encoding='utf-8', errors='replace') as fichier:
                contenu = fichier.read()
        except OSError:
            continue

        paquet = os.path.dirname(suivi)

        for module, est_relatif in _imports_exigeants(contenu):
            if est_relatif:
                if not paquet:
                    continue
                pointe = f'{paquet}/{module}'.replace('/', '.')
                candidats = [pointe]
            else:
                # « from apps.x.models import Y » : c'est apps.x.models qui
                # doit exister, pas apps.x.models.Y.
                candidats = [module]
                if '.' in module:
                    candidats.append(module.rsplit('.', 1)[0])
            if not any(_module_est_suivi(c, suivis) for c in candidats):
                manquants.setdefault(candidats[0], set()).add(suivi)

    details = []
    for module in sorted(manquants):
        par = sorted(manquants[module])
        autres = f' +{len(par) - 1}' if len(par) > 1 else ''
        details.append(f'{module}   <- {par[0]}{autres}')

    assert not manquants, (
        'Ces modules sont importes par du code VERSIONNE et ne sont pas '
        'dans le depot. Sur le serveur, l import echouera :\n  '
        + '\n  '.join(details))


# ── 4. Les fichiers statiques et les gabarits ────────────────────────────

def test_chaque_gabarit_etendu_ou_inclus_est_versionne():
    """Un `{% extends %}` vers un gabarit absent leve au rendu.

    La page repond alors 500, et si c'est un gabarit de base, c'est toute
    l'interface.
    """
    suivis = _suivis_ou_saute()

    # « ignore missing » n'est pas capture, et c'est voulu : ce drapeau dit
    # a Django de passer outre si le gabarit est absent. Un include qui le
    # porte ne peut pas lever, donc le signaler serait un faux positif --
    # ce fichier en avait un, sur
    # continuous_improvement/cycle_detail.html.
    motif = re.compile(
        r'\{%\s*(?:extends|include)\s+[\'"]([^\'"]+\.html)[\'"]'
        r'(?![^%]*ignore missing)')

    # Les emplacements ou Django cherche un gabarit, dans l'ordre.
    racines = ['templates/']
    for nom in sorted(os.listdir(os.path.join(RACINE, 'apps'))):
        if os.path.isdir(os.path.join(RACINE, 'apps', nom, 'templates')):
            racines.append(f'apps/{nom}/templates/')

    manquants = {}
    for suivi in sorted(suivis):
        if not suivi.endswith('.html'):
            continue
        chemin = os.path.join(RACINE, suivi)
        try:
            with open(chemin, encoding='utf-8', errors='replace') as fichier:
                contenu = fichier.read()
        except OSError:
            continue
        for reference in motif.findall(contenu):
            if '{' in reference:
                continue
            if any(f'{racine}{reference}' in suivis for racine in racines):
                continue
            manquants.setdefault(reference, set()).add(suivi)

    details = [f'{r}   <- {sorted(f)[0]}' for r, f in sorted(manquants.items())]

    assert not manquants, (
        'Ces gabarits sont etendus ou inclus par un gabarit VERSIONNE et '
        'ne sont pas dans le depot :\n  ' + '\n  '.join(details))
