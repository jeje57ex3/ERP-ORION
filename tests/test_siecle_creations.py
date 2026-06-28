import pytest
from decimal import Decimal
from apps.siecle_creations.models import Creation, CreationOrder
from apps.siecle_creations import services

pytestmark = pytest.mark.django_db


@pytest.fixture
def company(db):
    from apps.core.models import Company
    return Company.objects.create(name='Test BTP', slug='test-btp', is_active=True)


@pytest.fixture
def customer(company):
    from apps.crm.models import Customer
    return Customer.objects.create(company=company, name='Jean Dupont', email='jean@example.com')


@pytest.fixture
def creation(company):
    return services.create_creation(
        company, 'SC-001', 'Montre Élégance', 'montre',
        price_ht=Decimal('800.00'), price_ttc=Decimal('960.00'), stock_qty=5,
    )


# ── Model tests ───────────────────────────────────────────────────────────────

def test_creation_str(creation):
    assert 'SC-001' in str(creation)
    assert 'Montre Élégance' in str(creation)


def test_creation_default_status(creation):
    assert creation.status == 'draft'


def test_creation_brand_key_default(creation):
    assert creation.brand_key == 'siecle'


def test_creation_stock(creation):
    assert creation.stock_qty == 5


# ── Service tests ─────────────────────────────────────────────────────────────

def test_create_creation(company):
    c = services.create_creation(
        company, 'SC-002', 'Bracelet Or', 'bijou',
        price_ht=Decimal('300.00'), price_ttc=Decimal('360.00'), stock_qty=10,
    )
    assert c.pk is not None
    assert c.company == company
    assert c.category == 'bijou'


def test_publish_creation(creation):
    services.publish_creation(creation)
    creation.refresh_from_db()
    assert creation.status == 'published'
    assert creation.published_at is not None


def test_publish_already_published_noop(creation):
    services.publish_creation(creation)
    from django.utils import timezone
    first_published = creation.published_at
    services.publish_creation(creation)
    creation.refresh_from_db()
    assert creation.status == 'published'


def test_archive_creation(creation):
    services.publish_creation(creation)
    services.archive_creation(creation)
    creation.refresh_from_db()
    assert creation.status == 'archived'


def test_update_stock_add(creation):
    services.update_stock(creation, 3)
    creation.refresh_from_db()
    assert creation.stock_qty == 8


def test_update_stock_subtract(creation):
    services.update_stock(creation, -2)
    creation.refresh_from_db()
    assert creation.stock_qty == 3


def test_create_order(company, creation, customer):
    order = services.create_order(
        company, creation, customer, quantity=2,
    )
    assert order.pk is not None
    assert order.total_price == Decimal('1920.00')
    creation.refresh_from_db()
    assert creation.stock_qty == 3


def test_create_order_updates_stock(company, creation, customer):
    initial_stock = creation.stock_qty
    services.create_order(company, creation, customer, quantity=1)
    creation.refresh_from_db()
    assert creation.stock_qty == initial_stock - 1


def test_get_catalog_all(company, creation):
    results = services.get_catalog(company, category=None, status=None, brand_key='siecle')
    assert creation in results


def test_get_catalog_filter_status(company, creation):
    published = services.get_catalog(company, category=None, status='published', brand_key='siecle')
    assert creation not in published
    services.publish_creation(creation)
    published2 = services.get_catalog(company, category=None, status='published', brand_key='siecle')
    assert creation in published2


def test_get_catalog_filter_category(company, creation):
    results = services.get_catalog(company, category='bijou', status=None, brand_key='siecle')
    assert creation not in results
    results_montre = services.get_catalog(company, category='montre', status=None, brand_key='siecle')
    assert creation in results_montre


def test_get_creation_stats_empty(company):
    stats = services.get_creation_stats(company)
    assert stats['total_creations'] == 0
    assert stats['revenue'] == 0


def test_get_creation_stats_with_data(company, creation, customer):
    services.create_order(company, creation, customer, quantity=1)
    stats = services.get_creation_stats(company)
    assert stats['total_creations'] == 1
    assert stats['total_orders'] == 1
    assert stats['revenue'] == 960.0


def test_creation_order_str(company, creation, customer):
    order = services.create_order(company, creation, customer, quantity=1)
    assert str(order.pk) in str(order)


def test_limited_edition(company):
    c = services.create_creation(
        company, 'SC-LTD-01', 'Montre Edition Limitée', 'edition_limitee',
        price_ht=Decimal('5000.00'), price_ttc=Decimal('6000.00'), stock_qty=10,
        is_limited_edition=True, limited_qty=10,
    )
    assert c.is_limited_edition is True
    assert c.limited_qty == 10
