"""
tests/test_competitor_alerts.py — Tests des alertes concurrentielles

Lance avec : pytest tests/test_competitor_alerts.py -v
"""
from django.test import TestCase
from django.contrib.auth.models import User
from decimal import Decimal

from apps.core.models import Company
from apps.competitor_intelligence.models import (
    Competitor, CompetitorSite, CompetitorProduct, CompetitorAlert,
)


class TestCompetitorAlertModel(TestCase):

    def setUp(self):
        self.user = User.objects.create_superuser(
            username='admin', password='adminpass', email='admin@test.com'
        )
        self.company = Company.objects.create(
            name='Alert SA', slug='alert-sa', status='active', is_active=True
        )
        self.competitor = Competitor.objects.create(
            company=self.company,
            name='Alert Competitor',
            website_url='https://alert.example.com',
            created_by=self.user,
        )

    def test_create_alert(self):
        alert = CompetitorAlert.objects.create(
            company=self.company,
            competitor=self.competitor,
            alert_type='price_drop',
            title='Prix baisse chez Alert Competitor',
            message='Le prix du produit X a baisse de 20%',
            severity='medium',
        )
        self.assertIsNotNone(alert.pk)
        self.assertFalse(alert.is_read)

    def test_alert_str(self):
        alert = CompetitorAlert.objects.create(
            company=self.company,
            competitor=self.competitor,
            alert_type='new_product',
            title='Nouveau produit detecte',
            message='Nouveau produit Y detecte',
            severity='low',
        )
        self.assertIsNotNone(str(alert))

    def test_alert_unread_by_default(self):
        alert = CompetitorAlert.objects.create(
            company=self.company,
            competitor=self.competitor,
            alert_type='price_drop',
            title='Test',
            message='Test message',
            severity='low',
        )
        self.assertFalse(alert.is_read)

    def test_severity_color_low(self):
        alert = CompetitorAlert(severity='low')
        self.assertIn(alert.severity_color, ['secondary', 'info', 'success', 'muted'])

    def test_severity_color_medium(self):
        alert = CompetitorAlert(severity='medium')
        self.assertIn(alert.severity_color, ['warning', 'primary'])

    def test_severity_color_high(self):
        alert = CompetitorAlert(severity='high')
        self.assertIn(alert.severity_color, ['danger', 'warning'])

    def test_severity_color_critical(self):
        alert = CompetitorAlert(severity='critical')
        self.assertEqual(alert.severity_color, 'danger')

    def test_severity_icon_exists(self):
        for severity in ['low', 'medium', 'high', 'critical']:
            alert = CompetitorAlert(severity=severity)
            self.assertIsNotNone(alert.severity_icon)
            self.assertTrue(len(alert.severity_icon) > 0)

    def test_unread_alerts_count_on_competitor(self):
        CompetitorAlert.objects.create(
            company=self.company, competitor=self.competitor,
            alert_type='price_drop', title='A1', message='m', severity='low',
        )
        CompetitorAlert.objects.create(
            company=self.company, competitor=self.competitor,
            alert_type='price_drop', title='A2', message='m', severity='medium',
            is_read=True,
        )
        CompetitorAlert.objects.create(
            company=self.company, competitor=self.competitor,
            alert_type='new_product', title='A3', message='m', severity='high',
        )
        self.assertEqual(self.competitor.unread_alerts_count, 2)

    def test_alert_types(self):
        valid_types = ['price_drop', 'price_increase', 'new_product', 'promotion', 'traffic_change', 'new_site', 'product_removed', 'stock_change']
        for atype in valid_types:
            alert = CompetitorAlert(
                company=self.company, competitor=self.competitor,
                alert_type=atype, title='X', message='m', severity='low',
            )
            self.assertEqual(alert.alert_type, atype)


class TestAlertService(TestCase):

    def setUp(self):
        self.user = User.objects.create_superuser(
            username='admin2', password='adminpass', email='admin2@test.com'
        )
        self.company = Company.objects.create(
            name='Service Alert SA', slug='service-alert-sa', status='active', is_active=True
        )
        self.competitor = Competitor.objects.create(
            company=self.company,
            name='Service Alert Competitor',
            website_url='https://sa.example.com',
            created_by=self.user,
        )
        self.site = CompetitorSite.objects.create(
            competitor=self.competitor,
            site_url='https://sa.example.com',
            site_type='main',
        )
        self.product = CompetitorProduct.objects.create(
            company=self.company,
            competitor=self.competitor,
            site=self.site,
            name='Alert Widget',
            price=Decimal('100.00'),
            currency='EUR',
        )

    def test_create_price_drop_alert(self):
        from apps.competitor_intelligence.services.alert_service import create_price_drop_alert
        alert = create_price_drop_alert(
            company=self.company,
            competitor=self.competitor,
            product=self.product,
            old_price=Decimal('100.00'),
            new_price=Decimal('75.00'),
        )
        self.assertIsNotNone(alert.pk)
        self.assertEqual(alert.alert_type, 'price_drop')

    def test_create_price_increase_alert(self):
        from apps.competitor_intelligence.services.alert_service import create_price_increase_alert
        alert = create_price_increase_alert(
            company=self.company,
            competitor=self.competitor,
            product=self.product,
            old_price=Decimal('75.00'),
            new_price=Decimal('100.00'),
        )
        self.assertIsNotNone(alert.pk)
        self.assertEqual(alert.alert_type, 'price_increase')

    def test_create_new_product_alert(self):
        from apps.competitor_intelligence.services.alert_service import create_new_product_alert
        alert = create_new_product_alert(
            company=self.company,
            competitor=self.competitor,
            product=self.product,
        )
        self.assertIsNotNone(alert.pk)
        self.assertEqual(alert.alert_type, 'new_product')

    def test_create_promotion_alert(self):
        from apps.competitor_intelligence.services.alert_service import create_promotion_alert
        alert = create_promotion_alert(
            company=self.company,
            competitor=self.competitor,
            product=self.product,
            discount_percent=Decimal('30.00'),
        )
        self.assertIsNotNone(alert.pk)
        self.assertEqual(alert.alert_type, 'promotion')
