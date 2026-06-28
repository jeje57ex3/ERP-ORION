"""
tests/conftest.py — Fixtures partagées pour tous les tests Orion ERP
"""
import pytest
from django.contrib.auth.models import User
from apps.core.models import Company, CompanySettings


@pytest.fixture
def company(db):
    """Entreprise de test avec paramètres complets."""
    co = Company.objects.create(
        name='Test Company SA',
        slug='test-company-sa',
        status='active',
        is_active=True,
        invoice_prefix='FAC',
        quote_prefix='DEV',
        order_prefix='CMD',
    )
    CompanySettings.objects.create(
        company=co,
        next_invoice_number=1,
        next_quote_number=1,
        next_order_number=1,
        next_journal_entry_number=1,
    )
    return co


@pytest.fixture
def company_b(db):
    """Deuxième entreprise pour tests d'isolation."""
    co = Company.objects.create(
        name='Other Company SARL',
        slug='other-company-sarl',
        status='active',
        is_active=True,
    )
    CompanySettings.objects.create(company=co)
    return co


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser(
        username='admin', password='adminpass123', email='admin@test.com'
    )


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(
        username='staff', password='staffpass123', email='staff@test.com'
    )


@pytest.fixture
def client_logged_in(client, staff_user):
    client.force_login(staff_user)
    return client


@pytest.fixture
def superuser_client(client, superuser):
    client.force_login(superuser)
    return client
