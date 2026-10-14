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


# ── Périmètre de l'utilisateur ──────────────────────────────────────────────
# Le menu est filtré par utilisateur et par entreprise. Un index unique et
# partagé envoyait un utilisateur ordinaire vers des pages Super Admin qu'il
# ne peut pas ouvrir : un guidage qui mène à un refus d'accès est pire qu'un
# silence.

from django.template import Context, Template

from apps.orion_ai.context_processors import orion_ai_context


@pytest.fixture
def entreprise(db):
    from apps.core.models import Company
    return Company.objects.create(name='Entreprise de test')


@pytest.fixture
def super_admin(django_user_model):
    return django_user_model.objects.create_superuser(
        username='chef', email='chef@test.fr', password='x',
    )


@pytest.fixture
def utilisateur_simple(django_user_model):
    return django_user_model.objects.create_user(
        username='simple', email='simple@test.fr', password='x',
    )


def test_le_filtrage_par_utilisateur_est_sollicite(super_admin, monkeypatch):
    """Un super admin voit tout, mais le filtre doit bien être appelé."""
    vus = {}

    def faux_filtre(modules, company, user=None):
        vus['appele'] = True
        vus['user'] = user
        return modules

    monkeypatch.setattr(
        'apps.private_saas.permissions.filter_nav_modules', faux_filtre,
    )
    knowledge.index_pages(user=super_admin)
    assert vus['appele'] is True
    assert vus['user'] is super_admin


def test_un_filtre_restrictif_reduit_les_pages(utilisateur_simple, monkeypatch):
    monkeypatch.setattr(
        'apps.private_saas.permissions.filter_nav_modules',
        lambda modules, company, user=None: [],
    )
    assert knowledge.index_pages(user=utilisateur_simple) == ()


def test_un_filtre_en_panne_ne_prive_pas_du_guidage(utilisateur_simple, monkeypatch):
    """Orion reste un guide si le filtrage échoue : les permissions de la page
    refuseront l'accès de toute façon, alors que ne rien proposer serait une
    régression silencieuse."""
    def filtre_casse(modules, company, user=None):
        raise RuntimeError('indisponible')

    monkeypatch.setattr(
        'apps.private_saas.permissions.filter_nav_modules', filtre_casse,
    )
    assert len(knowledge.index_pages(user=utilisateur_simple)) > 50


def test_sans_utilisateur_l_index_reste_complet():
    """Les appels internes sans contexte utilisateur ne doivent pas se
    retrouver avec un index vide."""
    assert len(knowledge.index_pages()) > 50


def test_les_libelles_ne_sont_pas_figes_dans_une_langue():
    """Les 139 libellés du menu sont des traductions paresseuses : les
    mémoriser figeait la langue du premier appel pour tout le processus."""
    from django.utils import translation

    with translation.override('fr'):
        fr = {p['url_name']: p['libelle'] for p in knowledge.index_pages()}
    with translation.override('en'):
        en = {p['url_name']: p['libelle'] for p in knowledge.index_pages()}

    # Les adresses ne bougent pas (pas d'i18n_patterns dans ce projet).
    assert set(fr) == set(en)
    # Au moins un libellé doit différer, sinon la traduction n'est pas prise
    # en compte du tout.
    assert any(fr[cle] != en[cle] for cle in fr), 'aucun libelle traduit'


# ── Page d'où la question est posée ─────────────────────────────────────────

def test_route_connue_traduite_en_libelle():
    libelle = knowledge.page_depuis_route('core:dashboard')
    assert libelle
    assert '(' in libelle  # « Libellé (Module) »


def test_route_inconnue_ne_rend_rien():
    """Rien n'est inventé : un nom approximatif tromperait le modèle."""
    assert knowledge.page_depuis_route('module:inexistant') == ''
    assert knowledge.page_depuis_route('') == ''


def test_le_contexte_signale_la_page_ouverte():
    contexte = knowledge.contexte_pour_question(
        'comment je fais ça', module_courant='Disques & stockage (Super Admin)',
    )
    assert 'consulte actuellement' in contexte
    assert 'Disques & stockage' in contexte


def test_la_page_ouverte_suffit_a_produire_un_contexte():
    """« Comment je fais ça ? » ne correspond à aucune page, mais savoir d'où
    la question vient reste utile."""
    contexte = knowledge.contexte_pour_question('aide', module_courant='Clients (CRM)')
    assert contexte
    assert 'Clients' in contexte


# ── Icône de la barre du haut ───────────────────────────────────────────────

def _requete(rf, user):
    requete = rf.get('/dashboard/')
    requete.user = user
    return requete


def test_icone_absente_si_l_ia_est_desactivee(rf, super_admin, settings):
    settings.ORION_AI_ENABLED = False
    assert orion_ai_context(_requete(rf, super_admin))['orion_ai_available'] is False


def test_icone_absente_pour_un_visiteur(rf, settings):
    from django.contrib.auth.models import AnonymousUser

    settings.ORION_AI_ENABLED = True
    assert orion_ai_context(_requete(rf, AnonymousUser()))['orion_ai_available'] is False


def test_icone_presente_quand_tout_est_reuni(rf, super_admin, settings, db):
    settings.ORION_AI_ENABLED = True
    contexte = orion_ai_context(_requete(rf, super_admin))
    assert contexte['orion_ai_available'] is True
    assert contexte['orion_ai_name']
    assert 'orion_ai_local_only' in contexte


def test_le_processeur_ne_casse_jamais_les_pages(rf, super_admin, settings, monkeypatch):
    """Un processeur de contexte qui lève rend l'ERP ENTIÈREMENT inutilisable,
    pour un bouton. Il doit donc échouer en silence."""
    settings.ORION_AI_ENABLED = True
    monkeypatch.setattr(
        'apps.orion_ai.permissions.can_use_ai',
        lambda user: (_ for _ in ()).throw(RuntimeError('base non migree')),
    )
    assert orion_ai_context(_requete(rf, super_admin))['orion_ai_available'] is False


def test_le_libelle_injecte_dans_le_script_est_echappe():
    """Le libellé vient d'un paramètre d'URL, donc d'une saisie extérieure.
    Sans échappement, un guillemet casserait le script — ou y injecterait du
    code."""
    rendu = Template('const M = "{{ module_courant|escapejs }}";').render(
        Context({'module_courant': 'Page "x" (Mod)'}),
    )
    assert '\\u0022' in rendu
    assert 'const M = "Page \\u0022x\\u0022 (Mod)";' == rendu


# ── Messages du moteur local ────────────────────────────────────────────────
# L'utilisateur a reçu « 404 Client Error: Not Found for url:
# http://localhost:11434/api/chat ». Ce message ne dit ni ce qui manque ni
# quoi faire. Or un 404 d'Ollama ne signifie PAS que le point d'entrée est
# absent : il signifie que le MODÈLE demandé n'est pas téléchargé.

import requests as _requests

from apps.orion_ai.providers import LocalAIProvider


class _Reponse:
    def __init__(self, status_code=200, donnees=None, texte=''):
        self.status_code = status_code
        self._donnees = donnees
        self.text = texte

    def json(self):
        if self._donnees is None:
            raise ValueError('pas du JSON')
        return self._donnees


def _brancher(monkeypatch, reponse):
    def faux_post(url, **kwargs):
        if isinstance(reponse, Exception):
            raise reponse
        return reponse

    monkeypatch.setattr(
        'apps.orion_ai.providers.http_requests.post', faux_post,
    )


def _interroger():
    return LocalAIProvider().generate(
        messages=[{'role': 'user', 'content': 'bonjour'}],
        model='qwen2.5:3b-instruct',
    )


def test_un_modele_absent_est_nomme_avec_la_commande(monkeypatch):
    """Le cas réellement rencontré : Ollama tourne, le modèle manque."""
    _brancher(monkeypatch, _Reponse(404, {'error': 'model not found'}))

    with pytest.raises(AIProviderError) as erreur:
        _interroger()

    message = str(erreur.value)
    assert 'qwen2.5:3b-instruct' in message
    assert "n'est pas téléchargé" in message
    assert 'orion-ai.sh pull' in message
    # Et surtout, plus de jargon HTTP brut.
    assert '404 Client Error' not in message


def test_un_moteur_injoignable_renvoie_vers_le_diagnostic(monkeypatch):
    _brancher(monkeypatch, _requests.exceptions.ConnectionError('refused'))

    with pytest.raises(AIProviderError) as erreur:
        _interroger()

    message = str(erreur.value)
    assert 'ne répond pas' in message
    assert 'orion-ai.sh status' in message


def test_un_delai_depasse_evoque_la_memoire(monkeypatch):
    """Sur une petite VM, c'est la cause la plus fréquente."""
    _brancher(monkeypatch, _requests.exceptions.Timeout('trop long'))

    with pytest.raises(AIProviderError) as erreur:
        _interroger()

    assert 'mémoire' in str(erreur.value)


def test_une_autre_erreur_http_reprend_le_detail_du_moteur(monkeypatch):
    _brancher(monkeypatch, _Reponse(500, {'error': 'out of memory'}))

    with pytest.raises(AIProviderError) as erreur:
        _interroger()

    message = str(erreur.value)
    assert '500' in message
    assert 'out of memory' in message


def test_une_reponse_non_json_est_dite_clairement(monkeypatch):
    """Cas d'un autre service écoutant sur ce port."""
    _brancher(monkeypatch, _Reponse(200, donnees=None, texte='<html>'))

    with pytest.raises(AIProviderError) as erreur:
        _interroger()

    assert 'Ollama' in str(erreur.value)


def test_une_reponse_valide_est_rendue(monkeypatch):
    _brancher(monkeypatch, _Reponse(200, {
        'message': {'content': 'Bonjour.'},
        'prompt_eval_count': 12,
        'eval_count': 4,
    }))

    resultat = _interroger()
    assert resultat['content'] == 'Bonjour.'
    assert resultat['provider'] == 'local'
    assert resultat['token_input'] == 12
    assert resultat['token_output'] == 4


def test_le_script_verifie_le_telechargement():
    """Un pull interrompu laissait Ollama debout sans le modèle, et l'ERP
    répondait un 404 que rien n'expliquait."""
    from pathlib import Path

    from django.conf import settings

    script = (Path(settings.BASE_DIR) / 'deployment' / 'proxmox-appliance'
              / 'scripts' / 'orion-ai.sh').read_text(encoding='utf-8')
    assert 'if ! ollama pull' in script
    assert 'api/tags' in script
    assert 'orion-ai.sh pull' in script
