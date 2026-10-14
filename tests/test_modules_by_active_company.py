"""
Tests : affichage modules uniquement par entreprise sélectionnée.

Couvre :
- get_enabled_company_modules retourne set() sans entreprise
- company_has_module retourne False sans entreprise
- filter_nav_modules masque les modules entreprise sans company
- filter_nav_modules conserve les modules système (dashboard, settings)
- company_has_module retourne True/False selon is_enabled
- les modules sont isolés entre entreprises
"""
import pytest

from apps.private_saas.module_access import (
    company_has_module,
    disable_company_module,
    enable_company_module,
    get_enabled_company_modules,
)
from apps.private_saas.permissions import filter_nav_modules

SAMPLE_NAV = [
    {'id': 'dashboard',   'label': 'Dashboard'},
    {'id': 'settings',    'label': 'Paramètres'},
    {'id': 'ecommerce',   'label': 'E-commerce'},
    {'id': 'crm',         'label': 'CRM'},
    {'id': 'private_saas', 'label': 'Super Admin', 'super_admin_only': True},
]


# ─── Tests sans entreprise ─────────────────────────────────────────────────────

def test_no_company_enabled_modules_is_empty():
    assert get_enabled_company_modules(None) == set()


def test_no_company_has_module_returns_false():
    assert company_has_module(None, 'ecommerce') is False
    assert company_has_module(None, 'dashboard') is False
    assert company_has_module(None, 'orion_ai') is False


def test_no_company_nav_shows_only_always_visible():
    """Sans entreprise, uniquement dashboard + settings sont visibles."""
    visible_ids = {m['id'] for m in filter_nav_modules(SAMPLE_NAV, company=None)}
    assert 'dashboard' in visible_ids
    assert 'settings' in visible_ids
    # modules entreprise masqués
    assert 'ecommerce' not in visible_ids
    assert 'crm' not in visible_ids
    # super admin masqué aussi (pas superuser)
    assert 'private_saas' not in visible_ids


def test_no_company_superuser_sees_system_and_superadmin():
    """Super admin sans entreprise voit dashboard + settings + private_saas."""
    class FakeUser:
        is_superuser = True

    visible_ids = {m['id'] for m in filter_nav_modules(SAMPLE_NAV, company=None, user=FakeUser())}
    assert 'dashboard' in visible_ids
    assert 'settings' in visible_ids
    assert 'private_saas' in visible_ids
    # modules entreprise masqués même pour super admin sans company
    assert 'ecommerce' not in visible_ids
    assert 'crm' not in visible_ids


# ─── Tests avec entreprise ────────────────────────────────────────────────────

@pytest.mark.django_db
def test_company_module_enable_disable(company, staff_user):
    from apps.private_saas.services import seed_company_modules
    seed_company_modules(company, company_type='generic')

    # Par défaut 'orion_ai' peut être désactivé selon le type
    disable_company_module(company, 'ecommerce')
    assert company_has_module(company, 'ecommerce') is False

    enable_company_module(company, 'ecommerce', user=staff_user)
    assert company_has_module(company, 'ecommerce') is True

    disable_company_module(company, 'ecommerce')
    assert company_has_module(company, 'ecommerce') is False


@pytest.mark.django_db
# conftest.py nomme la seconde entreprise « company_b » : c'est le
# vocabulaire du depot, et en introduire un second par fixture aliasee
# ferait coexister deux noms pour la meme chose.
def test_modules_are_isolated_between_companies(company, company_b):
    from apps.private_saas.services import seed_company_modules
    seed_company_modules(company, company_type='generic')
    seed_company_modules(company_b, company_type='generic')

    enable_company_module(company, 'beauty_profiles')
    disable_company_module(company_b, 'beauty_profiles')

    assert company_has_module(company, 'beauty_profiles') is True
    assert company_has_module(company_b, 'beauty_profiles') is False


@pytest.mark.django_db
def test_get_enabled_modules_returns_only_enabled(company):
    from apps.private_saas.services import seed_company_modules
    seed_company_modules(company, company_type='generic')

    disable_company_module(company, 'ecommerce')
    modules = get_enabled_company_modules(company)

    assert 'ecommerce' not in modules
    # modules génériques activés par défaut
    assert 'dashboard' in modules
    assert 'crm' in modules
