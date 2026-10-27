"""Formations internes : le branchement de `apps.internal_training`.

Six modèles, dix-neuf vues, trois points d'API, huit gabarits, une
commande de données d'exemple — et l'application n'était déclarée ni dans
`INSTALLED_APPS`, ni dans les URLs. Aucun test non plus : contrairement à
`orion_ops`, rien ici n'avait jamais été exécuté, d'aucune façon.

**Deux verrous se cumulaient**, et c'est ce qui rend ce branchement
particulier. L'application était absente des réglages ; et ses dix-neuf
vues sont gardées par `require_company_module('internal_training')`, un
code qui était lui aussi absent de `ALL_MODULE_CODES`. La déclarer sans
corriger le code module aurait donné une application chargée dont **toutes
les pages refusent**, ce qui ressemble à un module non souscrit et non à
un défaut.

Ce fichier éprouve donc la chaîne entière : application chargée, module
activable, pages rendues, accès refusé sans le module, et navigation qui y
mène.
"""

import os

import pytest
from django.urls import reverse

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── Fixtures ───────────────────────────────────────────────────────────────

def _entreprise_avec_module(slug='formations-sa', actif=True):
    from apps.core.models import Company
    from apps.private_saas.models import CompanyModule

    entreprise = Company.objects.create(name='Formations SA', slug=slug)
    CompanyModule.objects.update_or_create(
        company=entreprise, module_code='internal_training',
        defaults={'is_enabled': actif})
    return entreprise


def _connecte(client, django_user_model, entreprise, nom='formateur'):
    from apps.accounts.models import UserProfile

    utilisateur = django_user_model.objects.create_user(
        nom, password='x', is_superuser=True, is_staff=True)
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


@pytest.fixture
def decor(client, django_user_model):
    """Une formation complète : cours, chapitre, page, bloc."""
    from apps.internal_training.models import (
        TrainingChapter, TrainingCourse, TrainingPage, TrainingPageBlock)

    entreprise = _entreprise_avec_module()
    utilisateur = _connecte(client, django_user_model, entreprise)

    cours = TrainingCourse.objects.create(
        company=entreprise, title='Sécurité sur chantier',
        created_by=utilisateur)
    chapitre = TrainingChapter.objects.create(
        course=cours, title='Les bases')
    page = TrainingPage.objects.create(
        chapter=chapitre, title='Port du casque')
    bloc = TrainingPageBlock.objects.create(page=page)

    return {
        'entreprise': entreprise, 'utilisateur': utilisateur,
        'cours': cours, 'chapitre': chapitre, 'page': page, 'bloc': bloc,
    }


# ── 1. L'application est chargée et le module activable ───────────────────

def test_l_application_est_enregistree():
    from django.apps import apps

    assert apps.is_installed('apps.internal_training')


def test_le_code_module_est_reconnu():
    """Le second verrou. Sans lui, les dix-neuf vues refusent toutes.

    `require_company_module` lit `CompanyModule`, dont les lignes sont
    créées en bouclant sur `ALL_MODULE_CODES`. Un code absent de cette
    liste ne reçoit jamais de ligne, donc ne s'active jamais — quoi qu'on
    coche dans l'interface.
    """
    from apps.private_saas.models import (
        ALL_MODULE_CODES, MODULE_LABELS, MODULE_NAV_IDS)

    assert 'internal_training' in ALL_MODULE_CODES
    assert MODULE_LABELS.get('internal_training')
    assert MODULE_NAV_IDS.get('internal_training') == ['internal_training']


def test_les_six_modeles_sont_connus():
    from django.apps import apps

    noms = {m.__name__
            for m in apps.get_app_config('internal_training').get_models()}
    attendus = {'TrainingCourse', 'TrainingChapter', 'TrainingPage',
                'TrainingPageBlock', 'TrainingEnrollment',
                'TrainingPageProgress'}
    assert attendus <= noms, 'Modèles absents : ' + ', '.join(
        sorted(attendus - noms))


def test_la_migration_initiale_existe_sur_le_disque():
    """Vérifiée sur le disque : `--no-migrations` vide le chargeur.

    Et ce point mérite d'être dit : une note de projet affirmait que la
    migration de ce module était « appliquée ». Le dossier ne contenait que
    `__init__.py` — elle n'existait pas.
    """
    dossier = os.path.join(RACINE, 'apps', 'internal_training', 'migrations')
    fichiers = [f for f in os.listdir(dossier)
                if f.endswith('.py') and f != '__init__.py']

    assert fichiers, 'Aucune migration : les six tables n existeront jamais.'


# ── 2. Les pages s'affichent ──────────────────────────────────────────────

@pytest.mark.django_db
@pytest.mark.parametrize('nom', ['dashboard', 'course_list', 'course_create'])
def test_les_pages_sans_argument_s_affichent(client, decor, nom):
    reponse = client.get(reverse(f'internal_training:{nom}'))
    assert reponse.status_code == 200, (
        f'internal_training:{nom} rend {reponse.status_code}')


@pytest.mark.django_db
@pytest.mark.parametrize('nom', ['course_detail', 'course_edit'])
def test_les_pages_d_une_formation_s_affichent(client, decor, nom):
    reponse = client.get(reverse(f'internal_training:{nom}',
                                 args=[decor['cours'].pk]))
    assert reponse.status_code == 200, (
        f'internal_training:{nom} rend {reponse.status_code}')


@pytest.mark.django_db
def test_la_creation_d_un_chapitre_s_affiche(client, decor):
    reponse = client.get(reverse('internal_training:chapter_create',
                                 args=[decor['cours'].pk]))
    assert reponse.status_code == 200


@pytest.mark.django_db
def test_la_modification_d_un_chapitre_s_affiche(client, decor):
    reponse = client.get(reverse('internal_training:chapter_edit',
                                 args=[decor['chapitre'].pk]))
    assert reponse.status_code == 200


@pytest.mark.django_db
def test_la_creation_d_une_page_s_affiche(client, decor):
    reponse = client.get(reverse('internal_training:page_create',
                                 args=[decor['chapitre'].pk]))
    assert reponse.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize('nom', ['page_edit', 'page_editor'])
def test_les_pages_d_edition_s_affichent(client, decor, nom):
    reponse = client.get(reverse(f'internal_training:{nom}',
                                 args=[decor['page'].pk]))
    assert reponse.status_code == 200, (
        f'internal_training:{nom} rend {reponse.status_code}')


@pytest.mark.django_db
def test_la_vue_apprenant_affiche_une_page_publiee(client, decor):
    """La vue apprenant ne sert QUE les pages publiées.

    Mon premier test échouait ici avec un 404, et c'était le code qui
    avait raison : `page_view` filtre sur `status='published'`. Un
    brouillon en cours de rédaction ne doit pas apparaître dans une
    formation suivie par les salariés.
    """
    decor['page'].status = 'published'
    decor['page'].save(update_fields=['status'])

    reponse = client.get(reverse('internal_training:page_view',
                                 args=[decor['page'].pk]))
    assert reponse.status_code == 200


@pytest.mark.django_db
def test_la_vue_apprenant_refuse_un_brouillon(client, decor):
    """L'autre moitié : sans elle, le test précédent ne prouverait rien."""
    assert decor['page'].status != 'published'

    reponse = client.get(reverse('internal_training:page_view',
                                 args=[decor['page'].pk]))
    assert reponse.status_code == 404


# ── 3. Le module commande vraiment l'accès ────────────────────────────────

def _connecte_ordinaire(client, django_user_model, entreprise, nom):
    """Un utilisateur NON superadmin.

    Nécessaire pour éprouver `require_company_module` : son code exempte
    explicitement les superutilisateurs (`decorators.py`, ligne 33), et un
    test mené avec un superadmin ne mesure donc rien de la garde. Mon
    premier essai est tombé dans ce piège et accusait le code à tort.
    """
    from apps.accounts.models import UserProfile

    utilisateur = django_user_model.objects.create_user(nom, password='x')
    profil, _ = UserProfile.objects.get_or_create(user=utilisateur)
    profil.role = 'user'
    profil.save()
    profil.companies.add(entreprise)

    client.force_login(django_user_model.objects.get(pk=utilisateur.pk))
    session = client.session
    session['current_company_id'] = entreprise.pk
    session.save()
    return utilisateur


@pytest.mark.django_db
def test_sans_le_module_les_pages_sont_refusees(client, django_user_model):
    """La garde doit mordre pour un utilisateur ordinaire.

    Une garde qui laisse tout passer est pire qu'absente : elle fait
    croire que le module est souscrit alors qu'il ne l'est pas.
    """
    entreprise = _entreprise_avec_module(slug='sans-module', actif=False)
    _connecte_ordinaire(client, django_user_model, entreprise, 'sans-droit')

    reponse = client.get(reverse('internal_training:dashboard'))
    assert reponse.status_code != 200, (
        'Le module est desactive et la page repond quand meme.')


@pytest.mark.django_db
def test_avec_le_module_un_utilisateur_ordinaire_entre(client,
                                                       django_user_model):
    """Et la garde doit LAISSER PASSER quand le module est actif.

    Sans ce test, le précédent pourrait venir d'une garde qui refuse tout
    le monde — ce qui ne serait pas une sécurité mais une panne, et c'est
    exactement l'état dans lequel ce module se trouvait avant que son code
    rejoigne ALL_MODULE_CODES.
    """
    entreprise = _entreprise_avec_module(slug='avec-module', actif=True)
    _connecte_ordinaire(client, django_user_model, entreprise, 'apprenant')

    reponse = client.get(reverse('internal_training:dashboard'))
    assert reponse.status_code == 200


@pytest.mark.django_db
def test_un_superadmin_passe_outre_le_module(client, django_user_model):
    """Comportement VOULU du décorateur, donc testé comme tel.

    `require_company_module` exempte les superutilisateurs. Sans ce test,
    on ne distinguerait pas « exemption délibérée » de « garde oubliée »,
    et c'est précisément ce qui m'a fait accuser le code à tort.
    """
    entreprise = _entreprise_avec_module(slug='superadmin-module',
                                         actif=False)
    _connecte(client, django_user_model, entreprise, nom='patron-formations')

    reponse = client.get(reverse('internal_training:dashboard'))
    assert reponse.status_code == 200


@pytest.mark.django_db
def test_un_visiteur_anonyme_est_renvoye(client):
    reponse = client.get(reverse('internal_training:dashboard'))
    assert reponse.status_code == 302


# ── 4. On peut y arriver depuis l'interface ───────────────────────────────

def test_la_navigation_mene_aux_formations():
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

    assert 'internal_training:dashboard' in noms(NAV_MODULES)


def test_l_entree_de_navigation_porte_l_identifiant_du_module():
    """Sinon le menu reste visible pour une entreprise sans le module.

    `MODULE_NAV_IDS` relie le code module aux `id` de NAV_MODULES : c'est
    ce lien qui masque le menu quand le module n'est pas souscrit.
    """
    from apps.core.context_processors import NAV_MODULES
    from apps.private_saas.models import MODULE_NAV_IDS

    identifiants = {e.get('id') for e in NAV_MODULES if isinstance(e, dict)}
    for identifiant in MODULE_NAV_IDS['internal_training']:
        assert identifiant in identifiants, (
            f'MODULE_NAV_IDS cite « {identifiant} », absent de NAV_MODULES.')
