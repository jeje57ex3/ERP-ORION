"""
tests/test_competitor_product.py — Tests des produits concurrents

Lance avec : pytest tests/test_competitor_product.py -v
"""
from django.test import TestCase
from django.contrib.auth.models import User
from decimal import Decimal

from apps.core.models import Company
from apps.competitor_intelligence.models import Competitor, CompetitorSite, CompetitorProduct


class TestCompetitorProductModel(TestCase):

    def setUp(self):
        self.user = User.objects.create_superuser(
            username='admin', password='adminpass', email='admin@test.com'
        )
        self.company = Company.objects.create(
            name='Prod SA', slug='prod-sa', status='active', is_active=True
        )
        self.competitor = Competitor.objects.create(
            company=self.company,
            name='Product Competitor',
            website_url='https://prodcomp.example.com',
            created_by=self.user,
        )
        self.site = CompetitorSite.objects.create(
            competitor=self.competitor,
            site_url='https://prodcomp.example.com',
            site_type='main',
        )

    def _create_product(self, **kwargs):
        defaults = dict(
            company=self.company,
            competitor=self.competitor,
            site=self.site,
            name='Test Product',
            price=Decimal('99.99'),
            currency='EUR',
            availability='in_stock',
        )
        defaults.update(kwargs)
        return CompetitorProduct.objects.create(**defaults)

    def test_create_product(self):
        p = self._create_product()
        self.assertIsNotNone(p.pk)

    def test_product_str(self):
        p = self._create_product(name='Super Widget')
        self.assertIn('Super Widget', str(p))

    def test_price_display_eur(self):
        p = self._create_product(price=Decimal('49.90'), currency='EUR')
        self.assertIn('49', p.price_display)

    def test_price_display_no_price(self):
        p = self._create_product(price=None)
        self.assertIsNotNone(p.price_display)

    def test_has_promotion_true(self):
        p = self._create_product(
            price=Decimal('79.99'),
            old_price=Decimal('99.99'),
            discount_percent=Decimal('20.00'),
        )
        self.assertTrue(p.has_promotion)

    def test_has_promotion_false(self):
        p = self._create_product(price=Decimal('99.99'))
        self.assertFalse(p.has_promotion)

    def test_active_by_default(self):
        p = self._create_product()
        self.assertTrue(p.is_active)

    def test_product_category(self):
        p = self._create_product(category='Electronique')
        self.assertEqual(p.category, 'Electronique')

    def test_active_products_count_on_competitor(self):
        self._create_product(name='P1')
        self._create_product(name='P2')
        self._create_product(name='P3', is_active=False)
        self.assertEqual(self.competitor.active_products_count, 2)


class TestAddProductManually(TestCase):

    def setUp(self):
        self.user = User.objects.create_superuser(
            username='admin2', password='adminpass', email='admin2@test.com'
        )
        self.company = Company.objects.create(
            name='Manual SA', slug='manual-sa', status='active', is_active=True
        )
        self.competitor = Competitor.objects.create(
            company=self.company,
            name='Manual Competitor',
            website_url='https://manual.example.com',
            created_by=self.user,
        )
        self.site = CompetitorSite.objects.create(
            competitor=self.competitor,
            site_url='https://manual.example.com',
            site_type='main',
        )

    def test_add_product_manually_via_service(self):
        from apps.competitor_intelligence.services.product_tracker import add_competitor_product_manually
        p = add_competitor_product_manually(
            company=self.company,
            competitor=self.competitor,
            site=self.site,
            name='Manuel Widget',
            price=Decimal('199.00'),
            currency='EUR',
            created_by=self.user,
        )
        self.assertIsNotNone(p.pk)
        self.assertEqual(p.name, 'Manuel Widget')

    def test_add_product_creates_price_history(self):
        from apps.competitor_intelligence.services.product_tracker import add_competitor_product_manually
        from apps.competitor_intelligence.models import CompetitorPriceHistory
        p = add_competitor_product_manually(
            company=self.company,
            competitor=self.competitor,
            site=self.site,
            name='History Widget',
            price=Decimal('299.00'),
            currency='EUR',
            created_by=self.user,
        )
        history = CompetitorPriceHistory.objects.filter(competitor_product=p)
        self.assertGreaterEqual(history.count(), 1)
