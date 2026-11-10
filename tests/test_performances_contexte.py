"""Le coût des processeurs de contexte, et le cache partagé entre workers.

Ce fichier garde deux corrections mesurées :

  1. les processeurs de contexte d'access_control calculaient leurs variables
     pour CHAQUE page, qu'un gabarit les lise ou non. Mesure faite avant
     correction, sur une base migrée : 84 requêtes SQL avant que la vue ne
     démarre pour un salarié au rôle non-admin, contre 4 pour un superuser.
     72 de ces 84 remplissaient « perms_map », que rien ne lit ;

  2. aucun réglage CACHES n'existait, donc Django retombait sur un cache PAR
     PROCESSUS, alors que gunicorn tourne avec trois workers — et que le code
     s'en sert pour des jetons de réinitialisation de mot de passe et des
     limites de débit.
"""
import importlib
from urllib.parse import urlparse

import pytest
from django.db import connection
from django.template import Context, Template
from django.test.utils import CaptureQueriesContext


# ── Montage ──────────────────────────────────────────────────────────────────

MODULES = (
    'dashboard', 'crm', 'sales', 'accounting', 'purchases', 'inventory',
    'btp', 'hr', 'payroll', 'documents', 'support', 'ecommerce',
    'commerce', 'production', 'audio', 'websites', 'reporting', 'settings',
)


@pytest.fixture
def entreprise(db):
    from apps.core.models import Company
    return Company.objects.create(name='Volt SARL', slug='volt-sarl')


@pytest.fixture
def modules(db):
    from apps.access_control.models import ERPModule
    return [
        ERPModule.objects.create(name=code, code=code, order=i)
        for i, code in enumerate(MODULES)
    ]


@pytest.fixture
def salarie(db, entreprise, modules, django_user_model):
    """Un salarié avec un rôle ordinaire : celui qui payait les 84 requêtes.

    Le rôle n'est PAS « admin » : _is_company_admin court-circuite tout pour
    « admin » et « superadmin », ce qui aurait masqué la mesure.
    """
    from apps.access_control.models import Role, UserCompanyAccess

    role = Role.objects.create(
        company=entreprise, name='Chef de chantier', code='chef')
    utilisateur = django_user_model.objects.create_user(
        username='salarie', password='motdepasse-test', email='s@volt.fr')
    UserCompanyAccess.objects.create(
        user=utilisateur, company=entreprise, role=role)
    return utilisateur


@pytest.fixture
def patron(db, django_user_model):
    return django_user_model.objects.create_superuser(
        username='patron', password='motdepasse-test', email='p@volt.fr')


def _requete(utilisateur, entreprise=None):
    from django.test import RequestFactory
    requete = RequestFactory().get('/btp/')
    requete.user = utilisateur
    requete.current_company = entreprise
    return requete


def _compter(fonction):
    """Le nombre de requêtes SQL émises par cet appel."""
    with CaptureQueriesContext(connection) as capture:
        fonction()
    return len(capture.captured_queries)


# ── 1. Le coût disparaît quand personne ne lit la variable ───────────────────

@pytest.mark.django_db
def test_perms_map_ne_coute_rien_si_personne_ne_le_lit(salarie, entreprise):
    """Le cœur de la correction : 72 requêtes devenues 0.

    Ce n'est pas une optimisation hypothétique. « perms_map » n'est lu par
    aucun gabarit, aucune vue, aucun test — vérifié sur tout le dépôt — et il
    coûtait 18 modules × 4 requêtes à chaque page vue par un salarié.
    """
    from apps.access_control.context_processors import current_company_permissions

    assert _compter(
        lambda: current_company_permissions(_requete(salarie, entreprise))
    ) == 0


@pytest.mark.django_db
def test_available_modules_et_sidebar_ne_coutent_rien_sans_lecture(
        salarie, entreprise):
    """Les 8 requêtes mesurées, devenues 0.

    8 était un PLANCHER : le rôle mesuré n'avait aucune permission, donc la
    boucle de get_user_sidebar_items n'a pas tourné une seule fois. Elle fait
    cinq appels par module accessible.
    """
    from apps.access_control.context_processors import available_modules

    assert _compter(
        lambda: available_modules(_requete(salarie, entreprise))
    ) == 0


@pytest.mark.django_db
def test_un_salarie_ne_paie_plus_vingt_fois_le_prix_du_patron(
        salarie, patron, entreprise):
    """La mesure d'ensemble, celle qui motivait tout le lot.

    Avant : 84 requêtes pour un salarié, 4 pour un superuser. L'écart venait
    des court-circuits « if user.is_superuser » de services.py, et il explique
    pourquoi le défaut n'avait pas été vu : l'exploitant qui essaie l'ERP est
    superuser, ses salariés ne le sont pas.
    """
    from apps.core.context_processors import (
        erp_context, navigation_context, brand_context)
    from apps.access_control.context_processors import (
        available_modules, current_company_permissions)

    processeurs = (erp_context, navigation_context, brand_context,
                   available_modules, current_company_permissions)

    def total(utilisateur):
        return sum(
            _compter(lambda p=p: p(_requete(utilisateur, entreprise)))
            for p in processeurs
        )

    cout_salarie = total(salarie)
    cout_patron = total(patron)

    # La borne est volontairement lâche : ce qui compte est qu'on ne soit
    # plus à 84, pas de figer un chiffre exact qu'un ajout légitime à
    # erp_context ferait tomber pour rien.
    assert cout_salarie <= 8, (
        f'{cout_salarie} requêtes pour un salarié ; la régression des 84 '
        f'requêtes est de retour (le patron en paie {cout_patron})'
    )
    assert cout_salarie <= cout_patron + 2


# ── 2. Le contrat rendu aux gabarits est intact ──────────────────────────────

@pytest.mark.django_db
def test_perms_map_reste_complet_quand_un_gabarit_le_lit(salarie, entreprise):
    """La paresse ne doit rien retirer : mêmes clés, mêmes valeurs."""
    from apps.access_control.context_processors import (
        current_company_permissions, MODULES_SURVEILLES)

    perms = current_company_permissions(
        _requete(salarie, entreprise))['perms_map']

    assert set(perms.keys()) == set(MODULES_SURVEILLES)
    assert len(perms) == 18
    # Ce rôle n'a aucune permission : tout doit être refusé, et surtout pas
    # autorisé par accident.
    assert all(valeur is False for valeur in perms.values())


@pytest.mark.django_db
def test_perms_map_autorise_ce_que_le_role_autorise(salarie, entreprise, modules):
    """Le chemin qui aboutit. Sans lui, le test précédent pourrait passer
    grâce à un dictionnaire qui refuse tout — une panne, non une règle."""
    from apps.access_control.models import Role, RolePermission, ERPModule
    from apps.access_control.context_processors import current_company_permissions

    role = Role.objects.get(code='chef')
    RolePermission.objects.create(
        role=role, module=ERPModule.objects.get(code='btp'), allowed=True)

    perms = current_company_permissions(
        _requete(salarie, entreprise))['perms_map']
    assert perms['btp'] is True
    assert perms['payroll'] is False


@pytest.mark.django_db
def test_un_gabarit_peut_iterer_et_tester_les_valeurs_paresseuses(
        salarie, entreprise, modules):
    """PREUVE MATÉRIELLE, et non supposition sur ce que Django relaie.

    SimpleLazyObject n'est utile ici que si un gabarit peut faire exactement
    ce que fait templates/notifications/notification_list.html :
    « {% if available_modules %} » puis « {% for mod in available_modules %} ».
    Ces opérations passent par __bool__ et __iter__, qui doivent atteindre
    l'objet enveloppé. On le vérifie en RENDANT un gabarit, pas en lisant la
    source de Django.
    """
    from apps.access_control.models import Role, RolePermission, ERPModule
    from apps.access_control.context_processors import (
        available_modules, current_company_permissions)

    role = Role.objects.get(code='chef')
    RolePermission.objects.create(
        role=role, module=ERPModule.objects.get(code='btp'), allowed=True)

    contexte = {}
    contexte.update(available_modules(_requete(salarie, entreprise)))
    contexte.update(current_company_permissions(_requete(salarie, entreprise)))

    rendu = Template(
        '{% if available_modules %}OUI{% else %}NON{% endif %}'
        '|{% for mod in available_modules %}{{ mod.code }}{% endfor %}'
        '|{{ available_modules|length }}'
        '|{% if perms_map.btp %}BTP{% endif %}'
        '{% if perms_map.payroll %}PAIE{% endif %}'
        '|{% if sidebar_items %}BARRE{% endif %}'
    ).render(Context(contexte))

    assert rendu == 'OUI|btp|1|BTP|BARRE', rendu


@pytest.mark.django_db
def test_un_visiteur_anonyme_recoit_toujours_des_listes_vides(entreprise):
    """Contrat inchangé pour les pages publiques, et zéro requête."""
    from django.contrib.auth.models import AnonymousUser
    from apps.access_control.context_processors import (
        available_modules, current_company_permissions)

    requete = _requete(AnonymousUser(), entreprise)

    assert _compter(lambda: available_modules(requete)) == 0
    assert _compter(lambda: current_company_permissions(requete)) == 0
    assert available_modules(requete) == {
        'available_modules': [], 'sidebar_items': []}
    assert current_company_permissions(requete) == {'perms_map': {}}


@pytest.mark.django_db
def test_sans_entreprise_courante_rien_n_est_calcule(salarie):
    """Un salarié connecté avant que CompanyMiddleware n'ait résolu
    l'entreprise : les variables existent, vides."""
    from apps.access_control.context_processors import (
        available_modules, current_company_permissions)

    requete = _requete(salarie, None)
    assert available_modules(requete)['sidebar_items'] == []
    assert current_company_permissions(requete)['perms_map'] == {}


# ── 3. Le cache est partagé entre les workers ────────────────────────────────

def test_un_cache_est_configure():
    """Sans réglage CACHES, Django retombe silencieusement sur LocMemCache."""
    from django.conf import settings
    assert settings.CACHES, 'aucun cache configuré'
    assert 'default' in settings.CACHES


def test_le_cache_fonctionne_vraiment():
    """Le backend configuré doit savoir écrire et relire.

    Trivial en apparence, et c'est le minimum qu'un jeton de réinitialisation
    de mot de passe exige du cache.
    """
    from django.core.cache import cache
    cache.set('orion-test-sonde', {'valeur': 42}, 60)
    assert cache.get('orion-test-sonde') == {'valeur': 42}
    cache.delete('orion-test-sonde')
    assert cache.get('orion-test-sonde') is None


def test_la_production_ne_garde_pas_un_cache_par_processus():
    """LocMemCache en production est le défaut qu'on corrige.

    Trois workers gunicorn, trois caches invisibles l'un à l'autre. Le jeton
    de réinitialisation de mot de passe des boutiques
    (apps/ecommerce/auth_views.py) n'existe QUE dans le cache : écrit par un
    worker, relu par un autre, il manquait deux fois sur trois — et tout
    redémarrage d'orion-backend annulait les liens en attente.
    """
    production = importlib.import_module('erp_btp.settings.production')
    backend = production.CACHES['default']['BACKEND']

    assert 'locmem' not in backend.lower(), (
        f'production utilise {backend} : un cache par processus'
    )
    assert 'dummy' not in backend.lower()
    assert backend == 'django.core.cache.backends.redis.RedisCache'


def test_le_cache_de_production_n_ecrase_pas_la_file_de_celery():
    """Base Redis 1 pour le cache, 0 pour Celery.

    Sur la même base, un vidage de cache — opération anodine — effacerait des
    tâches en attente.
    """
    production = importlib.import_module('erp_btp.settings.production')

    base_cache = urlparse(production.CACHES['default']['LOCATION']).path
    base_celery = urlparse(production.CELERY_BROKER_URL).path

    assert base_cache != base_celery, (
        f'cache et file Celery partagent la base Redis {base_cache}'
    )
    assert base_cache == '/1'
    assert base_celery == '/0'


# ── 4. Le commentaire du script ne contredit plus le comportement ────────────

def test_le_script_ia_dit_qui_gagne_sur_le_keep_alive():
    """Le commentaire affirmait que le modèle était libéré après 5 minutes.

    C'est faux pour l'usage réel : l'ERP envoie « keep_alive » dans chaque
    requête, et la valeur de la requête l'emporte sur la variable
    d'environnement. Un commentaire qui décrit l'inverse du comportement
    envoie chercher une panne là où il n'y en a pas.
    """
    from pathlib import Path
    source = Path(
        'deployment/proxmox-appliance/scripts/orion-ai.sh'
    ).read_text(encoding='utf-8')

    assert 'OLLAMA_KEEP_ALIVE=5m' in source
    fragment = source.split('OLLAMA_KEEP_ALIVE=5m')[0][-1600:]

    assert 'emporte sur cette variable' in fragment, \
        'le commentaire ne dit pas que la valeur de la requête gagne'
    assert 'orion-ai.sh test' in fragment and 'orion-ai.sh bench' in fragment, \
        'le commentaire ne nomme pas les deux commandes réellement concernées'
