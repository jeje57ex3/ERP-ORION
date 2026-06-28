"""
tests/test_competitor_widgets.py — Tests des widgets du dashboard concurrent

Lance avec : pytest tests/test_competitor_widgets.py -v
"""
from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from decimal import Decimal

from apps.core.models import Company
from apps.competitor_intelligence.models import (
    Competitor, CompetitorSite, CompetitorProduct, CompetitorAlert,
    CompetitorTrafficEstimate,
)
from apps.competitor_intelligence.widgets import AVAILABLE_WIDGETS


class TestAvailableWidgets(TestCase):

    def test_available_widgets_is_dict(self):
        self.assertIsInstance(AVAILABLE_WIDGETS, dict)

    def test_all_expected_widgets_present(self):
        expected = [
            'price_index', 'traffic_estimate', 'product_gap',
            'competitor_alerts', 'market_position', 'multi_site_comparison',
            'top_products', 'price_change',
        ]
        for key in expected:
            self.assertIn(key, AVAILABLE_WIDGETS, f"Widget '{key}' manquant dans AVAILABLE_WIDGETS")

    def test_widget_classes_are_callable(self):
        for key, widget_class in AVAILABLE_WIDGETS.items():
            self.assertTrue(callable(widget_class), f"Widget '{key}' n'est pas callable")


class TestPriceIndexWidget(TestCase):

    def setUp(self):
        self.user = User.objects.create_superuser(
            username='admin', password='adminpass', email='admin@test.com'
        )
        self.company = Company.objects.create(
            name='Widget SA', slug='widget-sa', status='active', is_active=True
        )
        self.factory = RequestFactory()

    def test_price_index_widget_render(self):
        from apps.competitor_intelligence.widgets import PriceIndexWidget
        widget = PriceIndexWidget(company=self.company)
        request = self.factory.get('/')
        request.user = self.user
        context = widget.get_context(request)
        self.assertIsNotNone(context)

    def test_price_index_widget_has_title(self):
        from apps.competitor_intelligence.widgets import PriceIndexWidget
        widget = PriceIndexWidget(company=self.company)
        self.assertTrue(len(widget.title) > 0)

    def test_price_index_widget_template(self):
        from apps.competitor_intelligence.widgets import PriceIndexWidget
        widget = PriceIndexWidget(company=self.company)
        self.assertIn('price_index', widget.template_name)


class TestTrafficEstimateWidget(TestCase):

    def setUp(self):
        self.user = User.objects.create_superuser(
            username='admin2', password='adminpass', email='admin2@test.com'
        )
        self.company = Company.objects.create(
            name='Traffic Widget SA', slug='tw-sa', status='active', is_active=True
        )
        self.factory = RequestFactory()

    def test_traffic_estimate_widget_render(self):
        from apps.competitor_intelligence.widgets import TrafficEstimateWidget
        widget = TrafficEstimateWidget(company=self.company)
        request = self.factory.get('/')
        request.user = self.user
        context = widget.get_context(request)
        self.assertIsNotNone(context)


class TestCompetitorAlertsWidget(TestCase):

    def setUp(self):
        self.user = User.objects.create_superuser(
            username='admin3', password='adminpass', email='admin3@test.com'
        )
        self.company = Company.objects.create(
            name='Alert Widget SA', slug='aw-sa', status='active', is_active=True
        )
        self.competitor = Competitor.objects.create(
            company=self.company,
            name='Widget Comp',
            website_url='https://wc.example.com',
            created_by=self.user,
        )
        self.factory = RequestFactory()

    def test_alerts_widget_empty(self):
        from apps.competitor_intelligence.widgets import CompetitorAlertsWidget
        widget = CompetitorAlertsWidget(company=self.company)
        request = self.factory.get('/')
        request.user = self.user
        context = widget.get_context(request)
        self.assertIn('alerts', context)

    def test_alerts_widget_with_data(self):
        from apps.competitor_intelligence.widgets import CompetitorAlertsWidget
        CompetitorAlert.objects.create(
            company=self.company,
            competitor=self.competitor,
            alert_type='price_drop',
            title='Test Alert',
            message='Test',
            severity='high',
        )
        widget = CompetitorAlertsWidget(company=self.company)
        request = self.factory.get('/')
        request.user = self.user
        context = widget.get_context(request)
        self.assertGreaterEqual(len(context['alerts']), 1)


class TestMarketPositionWidget(TestCase):

    def setUp(self):
        self.user = User.objects.create_superuser(
            username='admin4', password='adminpass', email='admin4@test.com'
        )
        self.company = Company.objects.create(
            name='Market Widget SA', slug='mw-sa', status='active', is_active=True
        )
        self.factory = RequestFactory()

    def test_market_position_widget_render(self):
        from apps.competitor_intelligence.widgets import MarketPositionWidget
        widget = MarketPositionWidget(company=self.company)
        request = self.factory.get('/')
        request.user = self.user
        context = widget.get_context(request)
        self.assertIn('market_data', context)
