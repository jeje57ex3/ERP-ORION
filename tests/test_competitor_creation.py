"""
tests/test_competitor_creation.py — Tests de creation et gestion des concurrents

Lance avec : pytest tests/test_competitor_creation.py -v
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User

from apps.core.models import Company
from apps.competitor_intelligence.models import Competitor, CompetitorSite


class TestCompetitorModel(TestCase):

    def setUp(self):
        self.user = User.objects.create_superuser(
            username='admin', password='adminpass', email='admin@test.com'
        )
        self.company = Company.objects.create(
            name='Mon Entreprise', slug='mon-entreprise', status='active', is_active=True
        )

    def test_create_competitor_minimal(self):
        c = Competitor.objects.create(
            company=self.company,
            name='Concurrent Alpha',
            website_url='https://alpha.example.com',
            created_by=self.user,
        )
        self.assertIsNotNone(c.pk)
        self.assertEqual(c.name, 'Concurrent Alpha')
        self.assertTrue(c.is_active)

    def test_competitor_str(self):
        c = Competitor.objects.create(
            company=self.company,
            name='Beta Corp',
            website_url='https://beta.example.com',
            created_by=self.user,
        )
        self.assertIn('Beta Corp', str(c))

    def test_competitor_requires_company(self):
        from django.db import IntegrityError
        with self.assertRaises((IntegrityError, Exception)):
            Competitor.objects.create(
                name='No Company',
                website_url='https://x.example.com',
                created_by=self.user,
            )

    def test_competitor_is_active_by_default(self):
        c = Competitor.objects.create(
            company=self.company,
            name='Default Active',
            website_url='https://active.example.com',
            created_by=self.user,
        )
        self.assertTrue(c.is_active)

    def test_competitor_can_be_deactivated(self):
        c = Competitor.objects.create(
            company=self.company,
            name='Inactive Corp',
            website_url='https://inactive.example.com',
            is_active=False,
            created_by=self.user,
        )
        self.assertFalse(c.is_active)

    def test_competitor_ordering(self):
        Competitor.objects.create(
            company=self.company, name='Zeta', website_url='https://z.example.com', created_by=self.user
        )
        Competitor.objects.create(
            company=self.company, name='Alpha', website_url='https://a.example.com', created_by=self.user
        )
        names = list(Competitor.objects.filter(company=self.company).values_list('name', flat=True))
        self.assertIn('Alpha', names)
        self.assertIn('Zeta', names)

    def test_competitor_industry_optional(self):
        c = Competitor.objects.create(
            company=self.company,
            name='No Industry',
            website_url='https://noindustry.example.com',
            created_by=self.user,
        )
        self.assertEqual(c.industry, '')

    def test_active_products_count_property(self):
        c = Competitor.objects.create(
            company=self.company,
            name='Count Test',
            website_url='https://count.example.com',
            created_by=self.user,
        )
        self.assertEqual(c.active_products_count, 0)

    def test_unread_alerts_count_property(self):
        c = Competitor.objects.create(
            company=self.company,
            name='Alert Test',
            website_url='https://alert.example.com',
            created_by=self.user,
        )
        self.assertEqual(c.unread_alerts_count, 0)


class TestCompetitorSiteModel(TestCase):

    def setUp(self):
        self.user = User.objects.create_superuser(
            username='admin2', password='adminpass', email='admin2@test.com'
        )
        self.company = Company.objects.create(
            name='Site SA', slug='site-sa', status='active', is_active=True
        )
        self.competitor = Competitor.objects.create(
            company=self.company,
            name='Site Competitor',
            website_url='https://site.example.com',
            created_by=self.user,
        )

    def test_create_site(self):
        site = CompetitorSite.objects.create(
            competitor=self.competitor,
            site_url='https://site.example.com',
            site_type='main',
            tracking_enabled=True,
        )
        self.assertIsNotNone(site.pk)

    def test_site_robots_policy_default(self):
        site = CompetitorSite.objects.create(
            competitor=self.competitor,
            site_url='https://site2.example.com',
            site_type='main',
        )
        self.assertEqual(site.robots_policy, 'respect')

    def test_site_str(self):
        site = CompetitorSite.objects.create(
            competitor=self.competitor,
            site_url='https://shop.example.com',
            site_type='shop',
        )
        self.assertIsNotNone(str(site))


class TestCompetitorServiceCreate(TestCase):

    def setUp(self):
        self.user = User.objects.create_superuser(
            username='admin3', password='adminpass', email='admin3@test.com'
        )
        self.company = Company.objects.create(
            name='Service SA', slug='service-sa', status='active', is_active=True
        )

    def test_create_competitor_via_service(self):
        from apps.competitor_intelligence.services.competitor_service import create_competitor
        competitor = create_competitor(
            company=self.company,
            name='Service Competitor',
            website_url='https://service-comp.example.com',
            created_by=self.user,
        )
        self.assertIsNotNone(competitor.pk)
        self.assertEqual(competitor.company, self.company)

    def test_create_competitor_creates_site(self):
        from apps.competitor_intelligence.services.competitor_service import create_competitor
        competitor = create_competitor(
            company=self.company,
            name='Site Creator',
            website_url='https://sitecreator.example.com',
            created_by=self.user,
        )
        sites = CompetitorSite.objects.filter(competitor=competitor)
        self.assertGreaterEqual(sites.count(), 1)
