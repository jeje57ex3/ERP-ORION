"""Connaissance d'Orion ERP tirée du code, pour guider sans rien inventer.

Un petit modèle local invente volontiers des noms de pages, et un guide qui
envoie l'utilisateur sur une page inexistante est pire qu'un guide muet :
l'utilisateur cherche, ne trouve pas, et conclut que le logiciel est en
défaut.

Cette connaissance est donc **extraite du code** et non rédigée :

- les entrées de menu viennent de `NAV_MODULES`, celui que l'interface affiche
  réellement ;
- les adresses viennent du résolveur d'URL, par `reverse()` ;
- la documentation vient des fichiers de `docs/`, versionnés avec le code.

Une page renommée ou supprimée disparaît donc d'elle-même des réponses, sans
qu'il faille y penser. C'est la seule façon de tenir la promesse « guider dans
l'interface » sur un dépôt qui compte 2044 routes.

Le modèle ne sert qu'à formuler : les faits, eux, sortent d'ici.
"""

import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.urls import NoReverseMatch, reverse

LONGUEUR_EXTRAIT = 700
RESULTATS_MAX = 5


# Les ligatures ne sont PAS des lettres accentuées : la décomposition Unicode
# ne les défait pas, et « œ » se retrouvait alors remplacé par une espace.
# « Nœuds HA » devenait « n uds ha », si bien qu'une recherche sur « noeuds »
# ne pouvait pas trouver cette page — qui existe pourtant dans le menu.
LIGATURES = {
    'œ': 'oe',  # œ
    'Œ': 'oe',  # Œ
    'æ': 'ae',  # æ
    'Æ': 'ae',  # Æ
    'ß': 'ss',  # ß
}


def normaliser(texte):
    """Minuscules sans accent ni ligature, pour comparer « Santé » et « sante ».

    Un utilisateur tape rarement les accents dans une recherche, et il serait
    absurde de ne pas trouver « santé système » parce qu'il a écrit « sante
    systeme ».
    """
    texte = (texte or '').lower()
    for ligature, remplacement in LIGATURES.items():
        texte = texte.replace(ligature, remplacement)
    decompose = unicodedata.normalize('NFD', texte)
    sans_accent = ''.join(c for c in decompose if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9]+', ' ', sans_accent).strip()


def mots_utiles(question):
    """Mots porteurs de sens d'une question.

    Les mots vides sont écartés : sans cela, « comment » et « où » pèsent
    autant que « sauvegarde » et toute question ressemble à toute page.
    """
    vides = {
        'le', 'la', 'les', 'un', 'une', 'des', 'du', 'de', 'et', 'ou', 'a',
        'ou est', 'je', 'tu', 'il', 'on', 'nous', 'vous', 'comment', 'pourquoi',
        'quoi', 'que', 'qui', 'quel', 'quelle', 'quels', 'quelles', 'est',
        'sont', 'dans', 'pour', 'sur', 'avec', 'mon', 'ma', 'mes', 'ce',
        'cette', 'ces', 'se', 'ne', 'pas', 'plus', 'faire', 'fait', 'trouve',
        'trouver', 'aller', 'va', 'puis', 'peux', 'peut', 'veux', 'veut',
        'orion', 'erp', 'page', 'bouton', 'menu',
    }
    return [m for m in normaliser(question).split() if len(m) > 2 and m not in vides]


# ─── Pages de l'interface ────────────────────────────────────────────────────

def index_pages(user=None, company=None):
    """Pages du menu visibles PAR CET UTILISATEUR, adresses résolues.

    Deux raisons de ne rien mémoriser ici, et les deux ont été des défauts
    réels de la première version :

    - Le menu est filtré par utilisateur et par entreprise
      (`filter_nav_modules`). Un index unique et partagé envoyait un
      utilisateur ordinaire vers des pages Super Admin qu'il ne peut pas
      ouvrir : un guidage qui mène à un refus d'accès est pire qu'un silence.
    - Les 139 libellés du menu sont des traductions paresseuses. Les résoudre
      une fois pour toutes figeait la langue du premier appel pour tout le
      processus — un utilisateur en espagnol donnait des libellés espagnols
      aux suivants.

    Le coût est négligeable : 129 entrées et autant de `reverse()`, que Django
    résout depuis ses propres caches. Les adresses, elles, ne dépendent ni de
    l'utilisateur ni de la langue — le projet n'utilise pas `i18n_patterns`.

    Import tardif : ce module est chargé par l'enregistrement des outils,
    atteint au démarrage, et `context_processors` touche aux modèles.
    """
    from apps.core.context_processors import NAV_MODULES

    modules_visibles = NAV_MODULES
    if user is not None:
        try:
            from apps.private_saas.permissions import filter_nav_modules
            modules_visibles = filter_nav_modules(NAV_MODULES, company, user=user)
        except Exception:
            # Filtrage indisponible : on retombe sur le menu complet plutôt
            # que de ne rien proposer. Orion reste alors un guide, et les
            # permissions de la page refuseront l'accès de toute façon.
            modules_visibles = NAV_MODULES

    pages = []
    for module in modules_visibles:
        titre_module = str(module.get('label') or module.get('name') or '')

        # Un module porte souvent SA propre adresse en plus de ses enfants :
        # 26 des 27 modules sont dans ce cas. Ne lire que les enfants aurait
        # rendu invisibles 26 pages, dont les tableaux de bord — soit
        # exactement celles vers lesquelles on oriente le plus souvent.
        entrees = []
        if module.get('url_name'):
            entrees.append({'label': titre_module, 'url_name': module['url_name']})
        entrees.extend(module.get('children') or [])

        for entree in entrees:
            nom_url = entree.get('url_name') or ''
            if not nom_url:
                continue
            try:
                adresse = reverse(nom_url)
            except NoReverseMatch:
                # Une entrée de menu dont la route n'existe plus : on l'écarte
                # plutôt que de l'annoncer. C'est déjà arrivé dans ce dépôt.
                continue

            libelle = str(entree.get('label') or '')
            if any(p['url_name'] == nom_url for p in pages):
                continue

            pages.append({
                'module': titre_module,
                'libelle': libelle,
                'url': adresse,
                'url_name': nom_url,
                'recherche': normaliser(f'{titre_module} {libelle} {nom_url}'),
            })
    return tuple(pages)


def chercher_pages(question, limite=RESULTATS_MAX, user=None, company=None):
    """Pages correspondant à la question, les mieux notées d'abord."""
    mots = mots_utiles(question)
    if not mots:
        return []

    notes = []
    for page in index_pages(user=user, company=company):
        note = sum(1 for mot in mots if mot in page['recherche'])
        # Le libellé pèse double : « Disques » dans le nom de la page est un
        # signal plus fort que le même mot dans celui du module.
        note += sum(1 for mot in mots if mot in normaliser(page['libelle']))
        if note:
            notes.append((note, page))

    notes.sort(key=lambda couple: (-couple[0], couple[1]['libelle']))
    return [page for _, page in notes[:limite]]


def lister_modules(user=None, company=None):
    """Modules de navigation et nombre de pages de chacun."""
    par_module = {}
    for page in index_pages(user=user, company=company):
        par_module.setdefault(page['module'], []).append(page['libelle'])
    return [
        {'module': nom, 'pages': sorted(pages), 'nombre': len(pages)}
        for nom, pages in sorted(par_module.items())
    ]


# ─── Documentation ───────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def index_documentation():
    """Sections des fichiers de `docs/`, découpées par titre.

    Découper par titre plutôt que par taille fixe : une section répond à une
    question, un fragment de 500 caractères coupé au milieu d'un tableau ne
    répond à rien.
    """
    racine = Path(getattr(settings, 'BASE_DIR', '.'))
    sections = []

    for chemin in sorted((racine / 'docs').glob('*.md')) if (racine / 'docs').is_dir() else []:
        try:
            contenu = chemin.read_text(encoding='utf-8')
        except OSError:
            continue

        titre_courant = chemin.stem
        corps = []
        for ligne in contenu.splitlines():
            if ligne.startswith('#'):
                if corps:
                    sections.append(_section(chemin.name, titre_courant, corps))
                titre_courant = ligne.lstrip('#').strip()
                corps = []
            else:
                corps.append(ligne)
        if corps:
            sections.append(_section(chemin.name, titre_courant, corps))

    return tuple(s for s in sections if s['texte'])


def _section(fichier, titre, lignes):
    texte = '\n'.join(lignes).strip()
    return {
        'fichier': fichier,
        'titre': titre,
        'texte': texte,
        'recherche': normaliser(f'{fichier} {titre} {texte}'),
    }


def chercher_documentation(question, limite=3):
    mots = mots_utiles(question)
    if not mots:
        return []

    notes = []
    for section in index_documentation():
        note = sum(section['recherche'].count(mot) for mot in mots)
        note += 3 * sum(1 for mot in mots if mot in normaliser(section['titre']))
        if note:
            notes.append((note, section))

    notes.sort(key=lambda couple: -couple[0])
    return [
        {
            'fichier': s['fichier'],
            'titre': s['titre'],
            'extrait': s['texte'][:LONGUEUR_EXTRAIT],
            'tronque': len(s['texte']) > LONGUEUR_EXTRAIT,
        }
        for _, s in notes[:limite]
    ]


def vider_index():
    """Oublie l'index documentaire. Utile aux tests et après une mise à jour.

    L'index des pages n'est plus mémorisé : il dépend de l'utilisateur et de
    la langue.
    """
    index_documentation.cache_clear()


# ─── Ancrage des réponses ────────────────────────────────────────────────────

def contexte_pour_question(question, user=None, company=None, module_courant=''):
    """Faits vérifiés à donner au modèle avant qu'il réponde.

    C'est la pièce qui tient la promesse « guider dans l'interface ». Un petit
    modèle local, laissé seul, invente des noms de pages plausibles — et un
    guide qui envoie chercher une page inexistante est pire qu'un guide muet.

    Les adresses de ce bloc sortent de `reverse()`, donc du résolveur d'URL
    lui-même : elles existent par construction. Le modèle n'a plus qu'à
    formuler, et le prompt lui interdit d'ajouter des pages qui n'y figurent
    pas.
    """
    pages = chercher_pages(question, user=user, company=company)
    docs = chercher_documentation(question)

    if not pages and not docs and not module_courant:
        return ''

    morceaux = ['FAITS VÉRIFIÉS SUR CETTE INSTALLATION', '']

    # D'où la question est posée. « Comment je fais ça ? » n'a de sens que
    # rapporté à la page ouverte, et sans cette ligne le modèle demande des
    # précisions que l'interface connaissait déjà.
    if module_courant:
        morceaux.append(f"L'utilisateur consulte actuellement : {module_courant}")
        morceaux.append('')

    if pages:
        morceaux.append('Pages existantes du menu, avec leur adresse réelle :')
        for page in pages:
            morceaux.append(f"- « {page['libelle']} » dans « {page['module']} » → {page['url']}")
        morceaux.append('')

    if docs:
        morceaux.append('Extraits de la documentation de cette version :')
        for doc in docs:
            suite = ' […]' if doc['tronque'] else ''
            morceaux.append(f"--- {doc['fichier']} · {doc['titre']} ---")
            morceaux.append(doc['extrait'] + suite)
            morceaux.append('')

    return '\n'.join(morceaux).strip()


def page_depuis_route(view_name, user=None, company=None):
    """Libelle de page correspondant a un nom de route, ou ''.

    L'icone de la barre du haut transmet le nom de route de la page ouverte
    (ex. « crm:customer_list »). Un nom de route n'a aucun sens pour
    l'utilisateur, ni d'ailleurs pour un modele de langue : il est traduit ici
    en libelle de menu, celui-la meme qui s'affiche a l'ecran.

    Rien n'est inventé : si la route n'est pas une entree de menu, on rend une
    chaine vide plutot qu'un nom approximatif.
    """
    if not view_name:
        return ''
    for page in index_pages(user=user, company=company):
        if page['url_name'] == view_name:
            return f"{page['libelle']} ({page['module']})"
    return ''
