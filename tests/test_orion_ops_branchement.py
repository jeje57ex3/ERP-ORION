"""Observabilité et fiabilité : le branchement de `apps.orion_ops`.

L'application existait sur le disque, complète — quatorze modèles, sept
services, quatre tâches Celery, vingt vues, quinze gabarits et trois
fichiers de tests — mais **absente de `INSTALLED_APPS` et des URLs**.

Ses 38 tests étaient les seuls échecs de la suite du projet, et ils
échouaient tous sur la même ligne :

    RuntimeError: Model class apps.orion_ops.models.ServiceComponent
    doesn't declare an explicit app_label and isn't in an application in
    INSTALLED_APPS.

Autrement dit, ils n'avaient **jamais** pu s'exécuter. Les faire passer ne
prouve donc presque rien : ils testent des services, pas le branchement.

Ce fichier teste ce qu'ils ne pouvaient pas tester — que les pages
existent, s'affichent, et sont atteignables depuis l'interface. C'est là
que se logent les défauts d'une application jamais exécutée : un gabarit
manquant, un nom d'URL faux dans un menu, une migration absente. Le module
de l'éditeur visuel en cachait trois du même genre.
"""

import os

import pytest
from django.urls import reverse

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Les routes sans argument, celles qu'un simple affichage doit rendre.
# Enumerees a la main ICI pour que l'ajout d'une page sans test se voie :
# un test qui lirait urlpatterns couvrirait automatiquement les nouvelles
# routes, et ne signalerait donc jamais rien.
PAGES = [
    'dashboard',
    'slo_list',
    'dependency_map',
    'data_quality',
    'deployment_list',
    'deployment_create',
    'restore_test_list',
    'capacity',
    'failed_tasks_list',
    'alert_rules_list',
    'bcp_list',
    'bcp_create',
    'failure_tests_list',
    'failure_test_create',
]

API = ['slo_api', 'dependency_api', 'extended_scores_api']


@pytest.fixture
def super_admin(client, django_user_model):
    """Les vues d'Ops sont reservees aux superutilisateurs actifs."""
    from apps.accounts.models import UserProfile
    from apps.core.models import Company

    entreprise = Company.objects.create(name='Orion SAS', slug='orion-ops')
    utilisateur = django_user_model.objects.create_user(
        'ops-root', password='x', is_superuser=True, is_staff=True)
    profil, _ = UserProfile.objects.get_or_create(user=utilisateur)
    profil.role = 'superadmin'
    profil.save()
    profil.companies.add(entreprise)

    utilisateur = django_user_model.objects.get(pk=utilisateur.pk)
    client.force_login(utilisateur)
    session = client.session
    session['current_company_id'] = entreprise.pk
    session.save()
    return utilisateur


# ── 1. L'application est bien chargée ──────────────────────────────────────

def test_l_application_est_enregistree():
    """Le défaut d'origine, en une ligne.

    Sans cette entrée, les modèles ne peuvent même pas se définir : la
    classe lève à l'import, et tout ce qui touche à l'application échoue.
    """
    from django.apps import apps

    assert apps.is_installed('apps.orion_ops')


def test_les_quatorze_modeles_sont_connus_du_registre():
    from django.apps import apps

    noms = {m.__name__ for m in apps.get_app_config('orion_ops').get_models()}
    attendus = {
        'ServiceComponent', 'ComponentDependency', 'SLOTarget', 'SLOBreach',
        'Deployment', 'RestoreTest', 'DataQualityAnomaly', 'AlertRule',
        'BusinessMetricReading', 'HealthScoreRecord', 'FailedTask',
        'CapacityTrend', 'BCPScenario', 'FailureTest',
    }
    assert attendus <= noms, 'Modèles absents : ' + ', '.join(
        sorted(attendus - noms))


def test_la_migration_initiale_existe_sur_le_disque():
    """Vérifiée sur le DISQUE et non via MigrationLoader.

    La suite tourne avec `--no-migrations`, qui vide
    `MigrationLoader.disk_migrations` pour toutes les applications : un
    test qui l'interrogerait passerait pour une mauvaise raison. Défaut
    déjà rencontré sur le module de double authentification.
    """
    dossier = os.path.join(RACINE, 'apps', 'orion_ops', 'migrations')
    fichiers = [f for f in os.listdir(dossier)
                if f.endswith('.py') and f != '__init__.py']

    assert fichiers, (
        'Aucune migration : les quatorze tables ne seront jamais creees sur '
        'le serveur, et chaque page repondra avec une erreur de table '
        'manquante.')


def test_la_migration_couvre_les_quatorze_modeles():
    dossier = os.path.join(RACINE, 'apps', 'orion_ops', 'migrations')
    contenu = ''
    for nom in sorted(os.listdir(dossier)):
        if nom.endswith('.py') and nom != '__init__.py':
            with open(os.path.join(dossier, nom), encoding='utf-8') as f:
                contenu += f.read()

    for modele in ('ServiceComponent', 'SLOTarget', 'AlertRule', 'FailedTask',
                   'BCPScenario', 'FailureTest', 'CapacityTrend'):
        assert modele in contenu, f'{modele} absent des migrations.'


# ── 2. Les pages s'affichent ───────────────────────────────────────────────

@pytest.mark.django_db
@pytest.mark.parametrize('nom', PAGES)
def test_chaque_page_s_affiche(client, super_admin, nom):
    """LE test qui trouve les trous d'une application jamais executee.

    Un gabarit manquant, une variable de contexte absente, un `{% url %}`
    vers un nom inexistant : rien de tout cela ne se voit tant que la vue
    n'a pas ete rendue une seule fois.
    """
    reponse = client.get(reverse(f'orion_ops:{nom}'))
    assert reponse.status_code == 200, (
        f'orion_ops:{nom} rend {reponse.status_code}')


@pytest.mark.django_db
@pytest.mark.parametrize('nom', API)
def test_chaque_api_repond_du_json(client, super_admin, nom):
    reponse = client.get(reverse(f'orion_ops:{nom}'))
    assert reponse.status_code == 200
    assert reponse['Content-Type'].startswith('application/json')


# ── 3. L'accès est réservé ────────────────────────────────────────────────

@pytest.mark.django_db
def test_un_visiteur_anonyme_n_entre_pas(client):
    reponse = client.get(reverse('orion_ops:dashboard'))
    assert reponse.status_code == 302


@pytest.mark.django_db
def test_un_utilisateur_ordinaire_n_entre_pas(client, django_user_model):
    """Ces pages exposent l'etat technique de toute l'installation.

    Composants, dependances, deploiements, taches echouees : rien de tout
    cela ne regarde un utilisateur d'entreprise.
    """
    from apps.accounts.models import UserProfile
    from apps.core.models import Company

    entreprise = Company.objects.create(name='Autre SA', slug='ops-autre')
    utilisateur = django_user_model.objects.create_user('simple', password='x')
    profil, _ = UserProfile.objects.get_or_create(user=utilisateur)
    profil.companies.add(entreprise)
    client.force_login(django_user_model.objects.get(pk=utilisateur.pk))

    reponse = client.get(reverse('orion_ops:dashboard'))
    assert reponse.status_code in (302, 403)


# ── 4. On peut y arriver depuis l'interface ───────────────────────────────

def test_la_navigation_mene_aux_pages_d_ops():
    """Une page sans entree de menu n'existe que pour qui connait son URL.

    C'est exactement ce qui est arrive a apps.system_health, dont le
    tableau de bord des disques etait introuvable depuis l'interface.
    """
    from apps.core.context_processors import NAV_MODULES

    def noms_d_url(entrees):
        rendu = set()
        for entree in entrees:
            if not isinstance(entree, dict):
                continue
            if entree.get('url_name'):
                rendu.add(entree['url_name'])
            rendu |= noms_d_url(entree.get('children') or [])
        return rendu

    cibles = noms_d_url(NAV_MODULES)
    assert 'orion_ops:dashboard' in cibles, (
        'Aucune entree de navigation ne mene au tableau de bord Ops.')


def test_chaque_entree_de_navigation_se_resout():
    """Un nom d'URL faux dans un menu leve au RENDU, pas au demarrage.

    La page qui porte le menu repond alors 500 -- et c'est toute
    l'interface, puisque le menu est dans le gabarit de base.
    """
    from django.urls import NoReverseMatch, reverse as resoudre

    from apps.core.context_processors import NAV_MODULES

    def noms_d_url(entrees):
        rendu = set()
        for entree in entrees:
            if not isinstance(entree, dict):
                continue
            if entree.get('url_name'):
                rendu.add(entree['url_name'])
            rendu |= noms_d_url(entree.get('children') or [])
        return rendu

    casses = []
    for nom in sorted(noms_d_url(NAV_MODULES)):
        if not nom.startswith('orion_ops:'):
            continue
        try:
            resoudre(nom)
        except NoReverseMatch as exc:
            casses.append(f'{nom} : {exc}')

    assert not casses, '\n  '.join(casses)


# ── 5. Les tâches de fond ─────────────────────────────────────────────────

def test_les_taches_sont_enregistrees_sous_un_nom_stable():
    """Un nom de tache change casse les messages deja en file.

    Et surtout : sans application enregistree, l'autodecouverte de Celery
    ne les voyait pas du tout.
    """
    from apps.orion_ops import tasks

    attendues = ('collect_business_metrics', 'compute_extended_scores',
                 'refresh_slo_status', 'run_data_quality_checks')
    for nom in attendues:
        fonction = getattr(tasks, nom, None)
        assert fonction is not None, f'Tache absente : {nom}'
        assert fonction.name == f'orion_ops.{nom}', (
            f'{nom} porte le nom « {fonction.name} » et non '
            f'« orion_ops.{nom} ».')
