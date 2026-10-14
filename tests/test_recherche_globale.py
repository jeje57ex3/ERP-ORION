"""Recherche globale de l'ERP.

Quatre défauts étaient superposés, et chacun suffisait à tout casser :

1. le gabarit interrogeait « /search/ » en dur, alors que la vue est montée
   sous « /dashboard/search/ » ;
2. la vue rendait TOUJOURS du HTML, même interrogée avec `format=json` ;
3. `_search_btp` importait `apps.btp.models.Project`, qui n'existe pas — le
   modèle s'appelle `BTPProject` — et un `except Exception` trop large avalait
   l'erreur, rendant les chantiers introuvables en silence ;
4. aucun filtre d'entreprise : les entreprises sans base dédiée partagent
   `default`, et la recherche y voyait les données des voisines.
"""

import json

import pytest

pytestmark = pytest.mark.django_db


@pytest.fixture
def entreprise_a(db):
    from apps.core.models import Company
    return Company.objects.create(name='Entreprise A')


@pytest.fixture
def entreprise_b(db):
    from apps.core.models import Company
    return Company.objects.create(name='Entreprise B')


@pytest.fixture
def utilisateur(django_user_model):
    return django_user_model.objects.create_user(
        username='cherchez', email='c@test.fr', password='motdepasse-test',
    )


@pytest.fixture
def super_admin(django_user_model):
    return django_user_model.objects.create_superuser(
        username='patron', email='p@test.fr', password='motdepasse-test',
    )

@pytest.fixture
def connecte_admin(client, super_admin, entreprise_a, monkeypatch):
    """Super administrateur : il voit toutes les pages du menu.

    Un compte ordinaire dont l'entreprise n'a aucun module active ne voit
    que les modules toujours affiches -- et « Disques » releve du Super
    Admin. Le filtrage est donc correct, et ces tests doivent employer un
    compte qui a reellement acces aux pages cherchees.
    """
    client.force_login(super_admin)
    from apps.core import search
    monkeypatch.setattr(search, '_entreprise_active', lambda requete: entreprise_a)
    return client


@pytest.fixture
def connecte(client, utilisateur, entreprise_a, monkeypatch):
    client.force_login(utilisateur)
    from apps.core import search
    monkeypatch.setattr(search, '_entreprise_active', lambda requete: entreprise_a)
    return client


def _client(entreprise, nom, email=''):
    from apps.crm.models import Customer
    return Customer.objects.create(company=entreprise, name=nom, email=email)


# ── L'adresse et le format ──────────────────────────────────────────────────

def test_la_route_est_bien_celle_que_le_gabarit_appelle():
    """Le gabarit appelait « /search/ », qui n'existe pas. Ce test ancre
    l'adresse reelle : il echouera si la route bouge sans le gabarit."""
    from django.urls import reverse

    assert reverse('core:search') == '/dashboard/search/'


def test_le_gabarit_resout_l_adresse_au_lieu_de_la_coder_en_dur():
    from pathlib import Path

    from django.conf import settings

    gabarit = (Path(settings.BASE_DIR) / 'templates' / 'erp_base.html').read_text(encoding='utf-8')
    assert '{% url "core:search" %}' in gabarit
    assert "fetch('/search/" not in gabarit


def test_la_vue_repond_en_json_quand_on_le_demande(connecte):
    """La vue rendait toujours du HTML : response.json() echouait, et le champ
    ne repondait jamais."""
    reponse = connecte.get('/dashboard/search/', {'q': 'rien', 'format': 'json'})
    assert reponse.status_code == 200
    assert 'application/json' in reponse['Content-Type']

    data = json.loads(reponse.content)
    assert 'results' in data
    assert 'count' in data


def test_la_vue_repond_en_json_a_une_requete_ajax(connecte):
    reponse = connecte.get(
        '/dashboard/search/', {'q': 'rien'},
        HTTP_X_REQUESTED_WITH='XMLHttpRequest',
    )
    assert 'application/json' in reponse['Content-Type']


def test_la_page_html_reste_disponible(connecte):
    """La vue sert aussi une page, pour une navigation directe."""
    reponse = connecte.get('/dashboard/search/', {'q': 'rien'})
    assert reponse.status_code == 200
    assert 'text/html' in reponse['Content-Type']


def test_la_recherche_exige_une_connexion(client):
    reponse = client.get('/dashboard/search/', {'q': 'client'})
    assert reponse.status_code == 302


# ── Cloisonnement par entreprise ────────────────────────────────────────────

def test_une_autre_entreprise_est_invisible(connecte, entreprise_a, entreprise_b):
    """Les entreprises sans base dediee partagent « default » : sans filtre
    explicite, la recherche y voyait les clients des voisines."""
    _client(entreprise_a, 'Dupont Maconnerie')
    _client(entreprise_b, 'Dupont Charpente')

    data = json.loads(
        connecte.get('/dashboard/search/', {'q': 'Dupont', 'format': 'json'}).content
    )
    titres = [r['title'] for r in data['results']]
    assert 'Dupont Maconnerie' in titres
    assert 'Dupont Charpente' not in titres


def test_sans_entreprise_active_aucun_resultat(client, utilisateur, entreprise_a, monkeypatch):
    """Mieux vaut ne rien montrer que tout montrer."""
    from apps.core import search

    _client(entreprise_a, 'Durand')
    client.force_login(utilisateur)
    monkeypatch.setattr(search, '_entreprise_active', lambda requete: None)

    data = json.loads(
        client.get('/dashboard/search/', {'q': 'Durand', 'format': 'json'}).content
    )
    assert data['results'] == []


def test_chercher_sans_entreprise_ne_renvoie_rien(entreprise_a):
    from apps.core.search import chercher

    _client(entreprise_a, 'Martin')
    assert chercher('Martin', None) == []


# ── Les chantiers, introuvables jusqu'ici ───────────────────────────────────

def test_les_chantiers_sont_trouvables(connecte, entreprise_a):
    """Le defaut le plus durable : l'import visait un modele inexistant, et
    l'exception etait avalee."""
    from apps.btp.models import BTPProject
    from apps.crm.models import Customer

    client_a = Customer.objects.create(company=entreprise_a, name='Client chantier')
    BTPProject.objects.create(
        company=entreprise_a, code='CH-2026-7', name='Toiture mairie',
        customer=client_a,
    )

    data = json.loads(
        connecte.get('/dashboard/search/', {'q': 'Toiture', 'format': 'json'}).content
    )
    chantiers = [r for r in data['results'] if r['type'] == 'chantier']
    assert chantiers, 'aucun chantier trouve'
    assert chantiers[0]['title'] == 'Toiture mairie'
    assert chantiers[0]['subtitle'] == 'CH-2026-7'


def test_un_chantier_est_trouvable_par_son_code(connecte, entreprise_a):
    from apps.btp.models import BTPProject
    from apps.crm.models import Customer

    c = Customer.objects.create(company=entreprise_a, name='Client')
    BTPProject.objects.create(
        company=entreprise_a, code='CH-2026-9', name='Ravalement', customer=c,
    )
    data = json.loads(
        connecte.get('/dashboard/search/', {'q': 'CH-2026-9', 'format': 'json'}).content
    )
    assert any(r['type'] == 'chantier' for r in data['results'])


def test_une_source_en_echec_est_journalisee_et_non_avalee(connecte, caplog):
    """Un except trop large a masque le defaut des chantiers pendant tout ce
    temps. Les echecs laissent desormais une trace."""
    from apps.core import search

    def source_cassee(q, company, user=None):
        raise ValueError('colonne absente')

    original = search.SOURCES
    search.SOURCES = (('source_test', source_cassee),)
    try:
        with caplog.at_level('WARNING'):
            reponse = connecte.get('/dashboard/search/', {'q': 'test', 'format': 'json'})
        assert reponse.status_code == 200
        assert any('source_test' in m for m in caplog.messages)
    finally:
        search.SOURCES = original


def test_un_module_absent_ne_fait_pas_de_bruit(connecte, caplog):
    """Tous les modules ne sont pas installes partout : une absence est
    normale et ne doit pas remplir le journal."""
    from apps.core import search

    def source_absente(q, company, user=None):
        raise ImportError('module non installe')

    original = search.SOURCES
    search.SOURCES = (('source_absente', source_absente),)
    try:
        with caplog.at_level('WARNING'):
            connecte.get('/dashboard/search/', {'q': 'test', 'format': 'json'})
        assert not any('source_absente' in m for m in caplog.messages)
    finally:
        search.SOURCES = original


# ── Seuil de declenchement ──────────────────────────────────────────────────

@pytest.mark.parametrize('requete', ['', 'a'])
def test_une_requete_trop_courte_ne_cherche_pas(connecte, entreprise_a, requete):
    """Une lettre renverrait presque tout le fichier clients."""
    _client(entreprise_a, 'Albert')
    data = json.loads(
        connecte.get('/dashboard/search/', {'q': requete, 'format': 'json'}).content
    )
    assert data['results'] == []


# ── Echappement : la faille stockee ─────────────────────────────────────────

def test_les_valeurs_affichees_sont_echappees():
    """La requete ET les valeurs de la base etaient injectees brutes dans
    innerHTML : un nom de client contenant du HTML s'executait."""
    from pathlib import Path

    from django.conf import settings

    gabarit = (Path(settings.BASE_DIR) / 'templates' / 'erp_base.html').read_text(encoding='utf-8')
    assert 'function echapper' in gabarit
    assert 'echapper(item.title)' in gabarit
    assert 'echapper(item.subtitle)' in gabarit
    assert "+ item.title +" not in gabarit


def test_un_nom_contenant_du_html_est_rendu_tel_quel(connecte, entreprise_a):
    """La vue renvoie la valeur brute en JSON -- c'est au rendu de
    l'echapper. On verifie au moins qu'elle n'est pas alteree en route."""
    _client(entreprise_a, '<img src=x onerror=alert(1)>')
    data = json.loads(
        connecte.get('/dashboard/search/', {'q': 'onerror', 'format': 'json'}).content
    )
    assert data['results'][0]['title'] == '<img src=x onerror=alert(1)>'


# ── Entree vers Orion ───────────────────────────────────────────────────────

def test_l_entree_orion_est_conditionnee_a_sa_disponibilite():
    """Un raccourci qui mene a « assistant desactive » est une promesse non
    tenue a chaque recherche."""
    from pathlib import Path

    from django.conf import settings

    gabarit = (Path(settings.BASE_DIR) / 'templates' / 'erp_base.html').read_text(encoding='utf-8')
    assert 'orion_ai_available' in gabarit
    assert 'function enteteOrion' in gabarit
    assert 'bi-stars' in gabarit


def test_orion_est_propose_meme_sans_resultat():
    """C'est precisement quand la recherche ne trouve rien qu'une question en
    langage naturel sert."""
    from pathlib import Path

    from django.conf import settings

    gabarit = (Path(settings.BASE_DIR) / 'templates' / 'erp_base.html').read_text(encoding='utf-8')
    bloc_vide = gabarit[gabarit.index('Aucun résultat pour') - 400:gabarit.index('Aucun résultat pour')]
    assert 'enteteOrion' in bloc_vide


def test_orion_pre_remplit_la_question_sans_l_envoyer(client, django_user_model, settings):
    """Pre-remplie, pas envoyee : l'utilisateur relit et complete avant
    d'engager une reponse."""
    from pathlib import Path

    gabarit = (Path(settings.BASE_DIR) / 'apps' / 'orion_ai' / 'templates'
               / 'orion_ai' / 'dashboard.html').read_text(encoding='utf-8')
    assert 'QUESTION_INITIALE' in gabarit
    assert 'champ.value = QUESTION_INITIALE' in gabarit
    # Aucun envoi automatique.
    assert 'sendMessage()' not in gabarit.split('QUESTION_INITIALE')[-1][:400]


# ── Les pages de l'interface, et pas seulement les données métier ───────────
# La recherche ne couvrait que clients, devis, factures, chantiers, produits.
# Chercher « disques » ou « paramètres IA » ne renvoyait donc rien, alors que
# ce sont des demandes au moins aussi fréquentes que la recherche d'un client.

def test_une_page_de_l_interface_est_trouvable(connecte_admin):
    data = json.loads(
        connecte_admin.get('/dashboard/search/', {'q': 'disques', 'format': 'json'}).content
    )
    pages = [r for r in data['results'] if r['type'] == 'page']
    assert pages, 'aucune page trouvee'
    assert pages[0]['url'].startswith('/')
    assert pages[0]['subtitle']  # le module dont elle depend


def test_les_pages_viennent_en_tete(connecte_admin, entreprise_a):
    """Quand on cherche « disques », on veut la page — pas un client dont le
    nom contiendrait ces lettres."""
    _client(entreprise_a, 'Disques Dupont')
    data = json.loads(
        connecte_admin.get('/dashboard/search/', {'q': 'disques', 'format': 'json'}).content
    )
    types = [r['type'] for r in data['results']]
    assert types[0] == 'page'
    assert 'client' in types, 'le client doit rester trouvable'


def test_toute_page_proposee_a_une_adresse_reelle(connecte_admin):
    """Les adresses viennent du résolveur d'URL : une page proposée existe."""
    from apps.orion_ai.knowledge import index_pages

    connues = {p['url'] for p in index_pages()}
    data = json.loads(
        connecte_admin.get('/dashboard/search/', {'q': 'parametres', 'format': 'json'}).content
    )
    for resultat in data['results']:
        if resultat['type'] == 'page':
            assert resultat['url'] in connues


def test_une_page_hors_permissions_n_est_pas_proposee(client, utilisateur, monkeypatch):
    """Proposer une page que l'utilisateur ne peut pas ouvrir est pire qu'un
    silence : il la cherche, et se voit refuser l'accès."""
    client.force_login(utilisateur)
    monkeypatch.setattr(
        'apps.private_saas.permissions.filter_nav_modules',
        lambda modules, company, user=None: [],
    )
    data = json.loads(
        client.get('/dashboard/search/', {'q': 'disques', 'format': 'json'}).content
    )
    assert [r for r in data['results'] if r['type'] == 'page'] == []


def test_les_pages_restent_trouvables_sans_entreprise_active(client, utilisateur, monkeypatch):
    """Sans entreprise résolue, les données métier sont hors de portée — mais
    priver l'utilisateur des pages rendrait la recherche entièrement
    inutile."""
    from apps.core import search

    client.force_login(utilisateur)
    monkeypatch.setattr(search, '_entreprise_active', lambda requete: None)

    data = json.loads(
        client.get('/dashboard/search/', {'q': 'disques', 'format': 'json'}).content
    )
    assert any(r['type'] == 'page' for r in data['results'])
    assert all(r['type'] == 'page' for r in data['results'])
