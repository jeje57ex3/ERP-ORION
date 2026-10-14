"""
tests/test_price_history.py — Tests du suivi de prix

Lance avec : pytest tests/test_price_history.py -v
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal

from apps.core.models import Company
from apps.competitor_intelligence.models import (
    Competitor, CompetitorSite, CompetitorProduct, CompetitorPriceHistory,
)


class TestPriceHistoryModel(TestCase):

    def setUp(self):
        self.user = User.objects.create_superuser(
            username='admin', password='adminpass', email='admin@test.com'
        )
        self.company = Company.objects.create(
            name='Price SA', slug='price-sa', status='active', is_active=True
        )
        self.competitor = Competitor.objects.create(
            company=self.company,
            name='Price Competitor',
            website_url='https://price.example.com',
            created_by=self.user,
        )
        self.site = CompetitorSite.objects.create(
            competitor=self.competitor,
            site_url='https://price.example.com',
            site_type='main',
        )
        self.product = CompetitorProduct.objects.create(
            company=self.company,
            competitor=self.competitor,
            site=self.site,
            name='Price Widget',
            price=Decimal('100.00'),
            currency='EUR',
        )

    def _add_history(self, price, old_price=None, discount=None, days_ago=0):
        return CompetitorPriceHistory.objects.create(
            company=self.company,
            competitor_product=self.product,
            price=price,
            old_price=old_price,
            discount_percent=discount,
            currency='EUR',
            availability='in_stock',
            checked_at=timezone.now() - timezone.timedelta(days=days_ago),
        )

    def test_create_price_history(self):
        h = self._add_history(Decimal('100.00'))
        self.assertIsNotNone(h.pk)

    def test_price_history_str(self):
        h = self._add_history(Decimal('100.00'))
        self.assertIsNotNone(str(h))

    def test_price_history_ordering(self):
        self._add_history(Decimal('100.00'), days_ago=2)
        self._add_history(Decimal('90.00'), days_ago=1)
        self._add_history(Decimal('95.00'), days_ago=0)
        qs = CompetitorPriceHistory.objects.filter(competitor_product=self.product)
        self.assertEqual(qs.count(), 3)

    def test_update_price_history_via_service(self):
        from apps.competitor_intelligence.services.price_tracker import update_price_history
        # L'entreprise se deduit du produit, et la devise vit sur le produit :
        # les passer a part permettait d'enregistrer un historique attribue a
        # une autre entreprise que celle du produit.
        update_price_history(
            self.product,
            Decimal('85.00'),
            availability='in_stock',
        )
        latest = CompetitorPriceHistory.objects.filter(competitor_product=self.product).order_by('-checked_at').first()
        self.assertEqual(latest.price, Decimal('85.00'))

    def test_detect_price_change_decrease(self):
        from apps.competitor_intelligence.services.price_tracker import detect_price_change
        # La fonction compare au prix COURANT du produit (100,00), et non a
        # son historique ; elle renvoie desormais l'alerte creee, ou None.
        alerte = detect_price_change(self.product, Decimal('80.00'))
        self.assertIsNotNone(alerte)
        self.assertEqual(alerte.alert_type, 'price_drop')

    def test_detect_price_change_increase(self):
        from apps.competitor_intelligence.services.price_tracker import detect_price_change
        self.product.price = Decimal('80.00')
        self.product.save()
        alerte = detect_price_change(self.product, Decimal('100.00'))
        self.assertIsNotNone(alerte)
        self.assertEqual(alerte.alert_type, 'price_increase')

    def test_detect_no_price_change(self):
        from apps.competitor_intelligence.services.price_tracker import detect_price_change
        # Prix inchange : aucune alerte, donc None. C'est la propriete utile --
        # alerter sur un prix identique noierait les vraies variations.
        self.assertIsNone(detect_price_change(self.product, Decimal('100.00')))

    def test_calculate_price_index(self):
        from apps.competitor_intelligence.services.price_tracker import calculate_price_index
        self._add_history(Decimal('100.00'))
        # Le second argument est une CATEGORIE, pas un prix : le passer en
        # Decimal filtrait sur « 90.00 » et ne trouvait rien. Et le retour est
        # un dictionnaire de metriques, pas un nombre.
        index = calculate_price_index(self.company)
        self.assertIsInstance(index, dict)
        self.assertIn('competitor_avg', index)
        self.assertIn('products_tracked', index)
        self.assertEqual(index['products_tracked'], 1)

    def test_multiple_products_price_history(self):
        product2 = CompetitorProduct.objects.create(
            company=self.company,
            competitor=self.competitor,
            site=self.site,
            name='Second Widget',
            price=Decimal('200.00'),
            currency='EUR',
        )
        CompetitorPriceHistory.objects.create(
            company=self.company,
            competitor_product=product2,
            price=Decimal('200.00'),
            currency='EUR',
            availability='in_stock',
        )
        self._add_history(Decimal('100.00'))
        total = CompetitorPriceHistory.objects.filter(company=self.company).count()
        self.assertEqual(total, 2)
