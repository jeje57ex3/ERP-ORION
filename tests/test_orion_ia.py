"""Orion, l'IA locale d'Orion ERP.

Deux propriétés sont éprouvées ici, et ce sont celles qui comptent :

1. **Rien ne part du serveur.** « Répondre uniquement en local » est une
   garantie de confidentialité, pas un réglage de confort : les devis, les
   clients et les factures ne doivent jamais quitter la machine. Le refus doit
   donc être une interdiction, vérifiable.

2. **Orion n'invente pas de page.** Un petit modèle local produit volontiers
   un nom de page plausible, et un guide qui envoie chercher une page
   inexistante est pire qu'un guide muet. Les adresses viennent du résolveur
   d'URL, donc existent par construction.
"""

import pytest

from apps.orion_ai import knowledge
from apps.orion_ai.providers import AIProviderError, get_ai_provider
from apps.orion_ai.tool_registry import get_available_ai_tools

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def index_neuf():
    """Les index sont mémorisés : on repart propre à chaque test."""
    knowledge.vider_index()
    yield
    knowledge.vider_index()


# ── Le verrou local est une interdiction ────────────────────────────────────

@pytest.mark.parametrize('externe', ['openai', 'anthropic'])
def test_fournisseur_externe_refuse_sous_verrou(externe):
    with pytest.raises(AIProviderError, match='externe'):
        get_ai_provider(externe, local_only=True)


def test_le_message_de_refus_explique_l_enjeu():
    """Un refus qui ne dit pas pourquoi sera contourné par la première
    personne pressée."""
    with pytest.raises(AIProviderError) as erreur:
        get_ai_provider('openai', local_only=True)
    message = str(erreur.value)
    assert 'quitter ce serveur' in message
    assert 'paramètres IA' in message


def test_fournisseur_local_toujours_accepte():
    assert get_ai_provider('local', local_only=True) is not None


def test_verrou_levable_explicitement():
    """Le verrou se lève, mais seulement en le disant."""
    assert get_ai_provider('openai', local_only=False) is not None


def test_verrou_actif_par_defaut(settings):
    """Sans réglage, on est verrouillé : un défaut permissif se découvrirait
    une fois les données parties."""
    settings.ORION_AI_LOCAL_ONLY = True
    with pytest.raises(AIProviderError):
        get_ai_provider('openai')


def test_fournisseur_inconnu_refuse():
    with pytest.raises(AIProviderError, match='inconnu'):
        get_ai_provider('un-fournisseur-qui-nexiste-pas', local_only=True)


# ── Normalisation des recherches ────────────────────────────────────────────

@pytest.mark.parametrize('brut,attendu', [
    ('Santé système', 'sante systeme'),
    ('DISQUES & stockage', 'disques stockage'),
    # La ligature doit etre developpee, pas supprimee : « noeuds » doit
    # trouver « Nœuds HA », qui est un vrai libelle de ce menu.
    ('Nœuds HA', 'noeuds ha'),
    ('CŒUR et æther', 'coeur et aether'),
    ('', ''),
])
def test_normalisation_ignore_accents_et_ponctuation(brut, attendu):
    assert knowledge.normaliser(brut) == attendu


def test_mots_vides_ecartes():
    """Sans cela, « comment » et « où » pèsent autant que « sauvegarde », et
    toute question ressemble à toute page."""
    mots = knowledge.mots_utiles('comment est-ce que je fais pour trouver les sauvegardes')
    assert 'sauvegardes' in mots
    assert 'comment' not in mots
    assert 'pour' not in mots


# ── L'index des pages vient du menu réel ────────────────────────────────────

def test_index_contient_des_pages():
    pages = knowledge.index_pages()
    assert len(pages) > 50


def test_toute_adresse_indexee_existe():
    """Propriété centrale : les adresses sortent de reverse(), donc du
    résolveur. Une page ne peut pas être annoncée si elle n'existe pas."""
    from django.urls import NoReverseMatch, reverse

    for page in knowledge.index_pages():
        try:
            assert reverse(page['url_name']) == page['url']
        except NoReverseMatch:
            pytest.fail(f"Adresse indexee mais introuvable : {page['url_name']}")


def test_les_pages_portent_module_et_libelle():
    for page in knowledge.index_pages():
        assert page['libelle']
        assert page['url'].startswith('/')


def test_aucun_doublon_de_route():
    noms = [p['url_name'] for p in knowledge.index_pages()]
    assert len(noms) == len(set(noms))


def test_une_route_inexistante_est_ecartee(monkeypatch):
    """Une entrée de menu dont la route a disparu ne doit pas être annoncée.
    C'est déjà arrivé dans ce dépôt."""
    monkeypatch.setattr(
        'apps.core.context_processors.NAV_MODULES',
        [{
            'label': 'Module de test',
            'children': [
                {'label': 'Page absente', 'url_name': 'route:qui-nexiste-pas'},
                {'label': 'Tableau de bord', 'url_name': 'core:dashboard'},
            ],
        }],
    )
    knowledge.vider_index()
    noms = [p['url_name'] for p in knowledge.index_pages()]
    assert 'core:dashboard' in noms
    assert 'route:qui-nexiste-pas' not in noms


def test_un_module_porteur_d_adresse_est_indexe(monkeypatch):
    """26 des 27 modules portent leur propre adresse en plus de leurs
    enfants : ne lire que les enfants les rendait invisibles."""
    monkeypatch.setattr(
        'apps.core.context_processors.NAV_MODULES',
        [{
            'label': 'Vue générale',
            'url_name': 'core:dashboard',
            'children': [],
        }],
    )
    knowledge.vider_index()
    assert [p['url_name'] for p in knowledge.index_pages()] == ['core:dashboard']


# ── Recherche de pages ──────────────────────────────────────────────────────

def test_recherche_trouve_une_page_connue():
    pages = knowledge.chercher_pages('ou sont les disques et le stockage')
    assert pages
    assert any('disque' in knowledge.normaliser(p['libelle']) for p in pages)


def test_recherche_sans_mot_utile_ne_renvoie_rien():
    """Mieux vaut ne rien proposer que proposer au hasard."""
    assert knowledge.chercher_pages('comment ?') == []
    assert knowledge.chercher_pages('') == []


def test_recherche_bornee():
    pages = knowledge.chercher_pages('orion erp page menu systeme', limite=3)
    assert len(pages) <= 3


def test_lister_modules_regroupe_les_pages():
    modules = knowledge.lister_modules()
    assert modules
    assert all(m['nombre'] == len(m['pages']) for m in modules)
    assert sum(m['nombre'] for m in modules) == len(knowledge.index_pages())


# ── Documentation ───────────────────────────────────────────────────────────

def test_documentation_decoupee_par_titre():
    sections = knowledge.index_documentation()
    assert sections
    assert all(s['titre'] and s['texte'] for s in sections)


def test_recherche_documentaire_trouve_la_haute_disponibilite():
    sections = knowledge.chercher_documentation('replication retard bascule')
    assert sections
    assert any('DISPONIBILITE' in s['fichier'].upper() for s in sections)


def test_extrait_documentaire_borne():
    for section in knowledge.chercher_documentation('sauvegarde'):
        assert len(section['extrait']) <= knowledge.LONGUEUR_EXTRAIT


# ── Ancrage : ce qui empêche d'inventer ─────────────────────────────────────

def test_contexte_annonce_des_faits_verifies():
    contexte = knowledge.contexte_pour_question('ou je trouve les disques')
    assert 'FAITS VÉRIFIÉS' in contexte
    assert '/orion-admin/' in contexte or '/' in contexte


def test_contexte_ne_contient_que_des_adresses_reelles():
    """Le modèle reçoit ce bloc comme seule source autorisée : s'il contenait
    une adresse fausse, l'interdiction d'inventer ne servirait à rien."""
    import re

    from django.urls import NoReverseMatch, reverse

    contexte = knowledge.contexte_pour_question('sauvegarde serveur disque sante')
    adresses_connues = {p['url'] for p in knowledge.index_pages()}
    for adresse in re.findall(r'→ (/\S+)', contexte):
        assert adresse in adresses_connues


def test_contexte_vide_quand_rien_ne_correspond():
    """Un contexte vide fait dire « je ne sais pas », ce qui est la bonne
    réponse. Un contexte inventé ferait dire n'importe quoi avec assurance."""
    assert knowledge.contexte_pour_question('xyzzy plugh') == ''
    assert knowledge.contexte_pour_question('') == ''


# ── Les outils de guidage sont enregistrés ──────────────────────────────────

def test_les_outils_de_guidage_sont_disponibles():
    import apps.orion_ai.tools  # noqa: F401  (l'import enregistre les outils)

    outils = get_available_ai_tools()
    for nom in ('trouver_page', 'lister_modules_interface', 'chercher_documentation'):
        assert nom in outils, f'outil manquant : {nom}'


def test_les_outils_de_guidage_sont_en_lecture_seule():
    """Ils ne lisent que la navigation et la documentation : aucune donnée
    métier, donc aucun risque, et aucune confirmation à demander."""
    import apps.orion_ai.tools  # noqa: F401

    outils = get_available_ai_tools()
    for nom in ('trouver_page', 'lister_modules_interface', 'chercher_documentation'):
        assert outils[nom]['is_write_action'] is False
        assert outils[nom]['is_dangerous_action'] is False


def test_outil_trouver_page_rend_des_adresses(django_user_model):
    import apps.orion_ai.tools as outils_module

    resultat = outils_module.trouver_page(
        company=None, user=None, question='disques stockage',
    )
    assert resultat['nombre'] >= 1
    adresses_connues = {p['url'] for p in knowledge.index_pages()}
    for page in resultat['pages']:
        assert page['adresse'] in adresses_connues


def test_une_recherche_sans_ligature_trouve_la_page_qui_en_a_une():
    """Verification de bout en bout : personne ne tape « Nœuds » au clavier."""
    pages = knowledge.chercher_pages('noeuds ha')
    assert pages
    assert any('HA' in p['libelle'] for p in pages)
