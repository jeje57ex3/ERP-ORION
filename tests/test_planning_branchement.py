"""Planning et temps dédiés : le branchement de `apps.work_planning`.

Sept modèles, trente-six routes, vingt-deux gabarits, un ordonnanceur
automatique, une bibliothèque de filtres de gabarit — et l'application
n'était déclarée ni dans `INSTALLED_APPS`, ni dans les URLs, sans aucun
test.

C'est le plus gros ensemble de vues que le code module manquant rendait
inaccessibles : **vingt-huit**, gardées par
`require_company_module('work_planning')`, code absent de
`ALL_MODULE_CODES` jusqu'à sa réconciliation.

Les pages qui demandent un objet sont testées avec un objet réel, et non
sautées : c'est précisément dans le rendu d'un gabarit avec des données
que se trouvent les défauts d'une application jamais exécutée — un filtre
de gabarit mal nommé, une variable de contexte oubliée, un `{% url %}`
vers une route inexistante.
"""

import os
from datetime import date, time, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PAGES_SIMPLES = [
    'dashboard',
    'weekly_planning',
    'mission_list',
    'mission_create',
    'employee_list',
    'employee_create',
    'all_employee_constraints',
    'time_block_create',
    'customer_request_list',
    'customer_request_create',
]

API = [
    'api_weekly_data',
    'api_missions',
    'api_tasks',
    'api_customer_requests',
    'api_employee_constraints',
]


def _entreprise_avec_module(slug='planning-sa', actif=True):
    from apps.core.models import Company
    from apps.private_saas.models import CompanyModule

    entreprise = Company.objects.create(name='Planning SA', slug=slug)
    CompanyModule.objects.update_or_create(
        company=entreprise, module_code='work_planning',
        defaults={'is_enabled': actif})
    return entreprise


def _connecte(client, django_user_model, entreprise, nom='chef-planning',
              superadmin=True):
    from apps.accounts.models import UserProfile

    utilisateur = django_user_model.objects.create_user(
        nom, password='x', is_superuser=superadmin, is_staff=superadmin)
    profil, _ = UserProfile.objects.get_or_create(user=utilisateur)
    profil.role = 'superadmin' if superadmin else 'user'
    profil.save()
    profil.companies.add(entreprise)

    client.force_login(django_user_model.objects.get(pk=utilisateur.pk))
    session = client.session
    session['current_company_id'] = entreprise.pk
    session.save()
    return utilisateur


@pytest.fixture
def decor(client, django_user_model):
    """Une mission, une tâche, un salarié, une contrainte, une demande."""
    from apps.work_planning.models import (
        CustomerRequest, EmployeeAvailabilityConstraint, EmployeeProfile,
        WorkMission, WorkTask)

    entreprise = _entreprise_avec_module()
    utilisateur = _connecte(client, django_user_model, entreprise)

    salarie = EmployeeProfile.objects.create(
        company=entreprise, user=utilisateur)
    # « name » et non « title » : les deux modeles de mission et de tache
    # emploient name, et CustomerRequest title. Verifie par introspection
    # du modele, apres que mon premier essai ait invente le mauvais champ.
    mission = WorkMission.objects.create(
        company=entreprise, name='Rénovation plateau 2')
    tache = WorkTask.objects.create(mission=mission, name='Démolition')
    debut = timezone.now() + timedelta(days=1)
    contrainte = EmployeeAvailabilityConstraint.objects.create(
        company=entreprise, employee=salarie, title='Formation obligatoire',
        starts_at=debut, ends_at=debut + timedelta(hours=3),
        start_time=time(9, 0), end_time=time(12, 0))
    demande = CustomerRequest.objects.create(
        company=entreprise, title='Devis pour une véranda')

    return {
        'entreprise': entreprise, 'utilisateur': utilisateur,
        'salarie': salarie, 'mission': mission, 'tache': tache,
        'contrainte': contrainte, 'demande': demande,
    }


# ── 1. L'application est chargée ───────────────────────────────────────────

def test_l_application_est_enregistree():
    from django.apps import apps

    assert apps.is_installed('apps.work_planning')


def test_les_sept_modeles_sont_connus():
    from django.apps import apps

    noms = {m.__name__
            for m in apps.get_app_config('work_planning').get_models()}
    attendus = {'EmployeeProfile', 'EmployeeAvailabilityConstraint',
                'WorkMission', 'CustomerRequest', 'WorkTask',
                'DedicatedTimeBlock', 'PlanningConflict'}
    assert attendus <= noms, 'Modèles absents : ' + ', '.join(
        sorted(attendus - noms))


def test_le_code_module_est_reconnu():
    from apps.private_saas.models import (
        ALL_MODULE_CODES, MODULE_LABELS, MODULE_NAV_IDS)

    assert 'work_planning' in ALL_MODULE_CODES
    assert MODULE_LABELS.get('work_planning')
    assert MODULE_NAV_IDS.get('work_planning') == ['work_planning']


def test_la_migration_initiale_existe_sur_le_disque():
    dossier = os.path.join(RACINE, 'apps', 'work_planning', 'migrations')
    fichiers = [f for f in os.listdir(dossier)
                if f.endswith('.py') and f != '__init__.py']
    assert fichiers, 'Aucune migration : les sept tables n existeront jamais.'


def test_la_bibliotheque_de_filtres_se_charge():
    """Un filtre de gabarit ne leve qu'au RENDU de la page qui l'emploie.

    Le module en fournit une : si elle ne se charge pas, chaque gabarit qui
    fait `{% load work_planning_extras %}` repond 500, et aucun test de
    modele ne le verrait.
    """
    from django.template import Engine

    moteur = Engine.get_default()
    bibliotheques = moteur.template_libraries
    assert 'work_planning_extras' in bibliotheques, (
        'La bibliotheque de filtres n est pas decouverte : les gabarits qui '
        'la chargent leveront au rendu.')


# ── 2. Les pages s'affichent ──────────────────────────────────────────────

@pytest.mark.django_db
@pytest.mark.parametrize('nom', PAGES_SIMPLES)
def test_les_pages_sans_argument_s_affichent(client, decor, nom):
    reponse = client.get(reverse(f'work_planning:{nom}'))
    assert reponse.status_code == 200, (
        f'work_planning:{nom} rend {reponse.status_code}')


@pytest.mark.django_db
@pytest.mark.parametrize('nom', ['mission_detail', 'mission_edit'])
def test_les_pages_d_une_mission_s_affichent(client, decor, nom):
    reponse = client.get(reverse(f'work_planning:{nom}',
                                 args=[decor['mission'].pk]))
    assert reponse.status_code == 200, (
        f'work_planning:{nom} rend {reponse.status_code}')


@pytest.mark.django_db
def test_la_creation_d_une_tache_s_affiche(client, decor):
    reponse = client.get(reverse('work_planning:task_create',
                                 args=[decor['mission'].pk]))
    assert reponse.status_code == 200


@pytest.mark.django_db
def test_la_modification_d_une_tache_s_affiche(client, decor):
    reponse = client.get(reverse('work_planning:task_edit',
                                 args=[decor['tache'].pk]))
    assert reponse.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize('nom', ['employee_edit', 'employee_constraints',
                                 'employee_constraint_create'])
def test_les_pages_d_un_salarie_s_affichent(client, decor, nom):
    reponse = client.get(reverse(f'work_planning:{nom}',
                                 args=[decor['salarie'].pk]))
    assert reponse.status_code == 200, (
        f'work_planning:{nom} rend {reponse.status_code}')


@pytest.mark.django_db
def test_la_modification_d_une_contrainte_s_affiche(client, decor):
    reponse = client.get(reverse('work_planning:employee_constraint_edit',
                                 args=[decor['contrainte'].pk]))
    assert reponse.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize('nom', ['customer_request_detail',
                                 'customer_request_edit'])
def test_les_pages_d_une_demande_s_affichent(client, decor, nom):
    reponse = client.get(reverse(f'work_planning:{nom}',
                                 args=[decor['demande'].pk]))
    assert reponse.status_code == 200, (
        f'work_planning:{nom} rend {reponse.status_code}')


@pytest.mark.django_db
@pytest.mark.parametrize('nom', API)
def test_chaque_api_repond_du_json(client, decor, nom):
    reponse = client.get(reverse(f'work_planning:{nom}'))
    assert reponse.status_code == 200, (
        f'work_planning:{nom} rend {reponse.status_code}')
    assert reponse['Content-Type'].startswith('application/json')


# ── 3. Le module commande l'accès ─────────────────────────────────────────

@pytest.mark.django_db
def test_sans_le_module_les_pages_sont_refusees(client, django_user_model):
    """Mesure avec un utilisateur ORDINAIRE.

    `require_company_module` exempte les superutilisateurs : un test mene
    avec un superadmin ne dirait rien de la garde.
    """
    entreprise = _entreprise_avec_module(slug='planning-sans', actif=False)
    _connecte(client, django_user_model, entreprise, nom='sans-planning',
              superadmin=False)

    reponse = client.get(reverse('work_planning:dashboard'))
    assert reponse.status_code != 200


@pytest.mark.django_db
def test_avec_le_module_un_utilisateur_ordinaire_entre(client,
                                                       django_user_model):
    """Et la garde doit laisser passer : sinon c'est une panne, non une garde."""
    entreprise = _entreprise_avec_module(slug='planning-avec', actif=True)
    _connecte(client, django_user_model, entreprise, nom='avec-planning',
              superadmin=False)

    reponse = client.get(reverse('work_planning:dashboard'))
    assert reponse.status_code == 200


@pytest.mark.django_db
def test_un_visiteur_anonyme_est_renvoye(client):
    reponse = client.get(reverse('work_planning:dashboard'))
    assert reponse.status_code == 302


# ── 4. On y arrive depuis l'interface ─────────────────────────────────────

def test_la_navigation_mene_au_planning():
    from apps.core.context_processors import NAV_MODULES

    def noms(entrees):
        rendu = set()
        for e in entrees:
            if not isinstance(e, dict):
                continue
            if e.get('url_name'):
                rendu.add(e['url_name'])
            rendu |= noms(e.get('children') or [])
        return rendu

    cibles = noms(NAV_MODULES)
    assert 'work_planning:dashboard' in cibles
    assert 'work_planning:weekly_planning' in cibles
