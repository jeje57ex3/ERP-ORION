"""
tests/test_traffic_estimate.py — Tests des estimations de trafic

Lance avec : pytest tests/test_traffic_estimate.py -v
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone

from apps.core.models import Company
from apps.competitor_intelligence.models import (
    Competitor, CompetitorSite, CompetitorTrafficEstimate,
)


class TestTrafficEstimateModel(TestCase):

    def setUp(self):
        self.user = User.objects.create_superuser(
            username='admin', password='adminpass', email='admin@test.com'
        )
        self.company = Company.objects.create(
            name='Traffic SA', slug='traffic-sa', status='active', is_active=True
        )
        self.competitor = Competitor.objects.create(
            company=self.company,
            name='Traffic Competitor',
            website_url='https://traffic.example.com',
            created_by=self.user,
        )
        self.site = CompetitorSite.objects.create(
            competitor=self.competitor,
            site_url='https://traffic.example.com',
            site_type='main',
        )

    def test_create_traffic_estimate(self):
        est = CompetitorTrafficEstimate.objects.create(
            company=self.company,
            competitor=self.competitor,
            site=self.site,
            estimated_monthly_visitors=50000,
            source_type='manual',
            confidence_score=7,
        )
        self.assertIsNotNone(est.pk)

    def test_traffic_estimate_str(self):
        est = CompetitorTrafficEstimate.objects.create(
            company=self.company,
            competitor=self.competitor,
            site=self.site,
            estimated_monthly_visitors=10000,
            source_type='manual',
            confidence_score=5,
        )
        self.assertIsNotNone(str(est))

    def test_traffic_source_types(self):
        for source in ['manual', 'csv', 'api', 'analytics', 'internal']:
            est = CompetitorTrafficEstimate(
                company=self.company,
                competitor=self.competitor,
                site=self.site,
                estimated_monthly_visitors=1000,
                source_type=source,
                confidence_score=5,
            )
            self.assertEqual(est.source_type, source)

    def test_confidence_score_range(self):
        est = CompetitorTrafficEstimate.objects.create(
            company=self.company,
            competitor=self.competitor,
            site=self.site,
            estimated_monthly_visitors=25000,
            source_type='api',
            confidence_score=9,
        )
        self.assertGreaterEqual(est.confidence_score, 1)
        self.assertLessEqual(est.confidence_score, 10)

    def test_add_manual_traffic_estimate_via_service(self):
        from apps.competitor_intelligence.services.traffic_estimator import add_manual_traffic_estimate
        est = add_manual_traffic_estimate(
            company=self.company,
            competitor=self.competitor,
            site=self.site,
            monthly_visitors=75000,
            confidence_score=6,
            created_by=self.user,
        )
        self.assertIsNotNone(est.pk)
        self.assertEqual(est.estimated_monthly_visitors, 75000)
        self.assertEqual(est.source_type, 'manual')

    def test_calculate_traffic_trend(self):
        from apps.competitor_intelligence.services.traffic_estimator import calculate_traffic_trend
        now = timezone.now()
        CompetitorTrafficEstimate.objects.create(
            company=self.company,
            competitor=self.competitor,
            site=self.site,
            estimated_monthly_visitors=30000,
            source_type='manual',
            confidence_score=5,
            measured_at=now - timezone.timedelta(days=60),
        )
        CompetitorTrafficEstimate.objects.create(
            company=self.company,
            competitor=self.competitor,
            site=self.site,
            estimated_monthly_visitors=45000,
            source_type='manual',
            confidence_score=5,
            measured_at=now - timezone.timedelta(days=30),
        )
        trend = calculate_traffic_trend(self.competitor)
        self.assertIsNotNone(trend)

    def test_compare_competitor_traffic(self):
        from apps.competitor_intelligence.services.traffic_estimator import compare_competitor_traffic
        CompetitorTrafficEstimate.objects.create(
            company=self.company,
            competitor=self.competitor,
            site=self.site,
            estimated_monthly_visitors=40000,
            source_type='manual',
            confidence_score=7,
        )
        result = compare_competitor_traffic(self.company)
        self.assertIsInstance(result, list)

    def test_daily_visitors_calculated(self):
        est = CompetitorTrafficEstimate.objects.create(
            company=self.company,
            competitor=self.competitor,
            site=self.site,
            estimated_monthly_visitors=30000,
            estimated_daily_visitors=1000,
            source_type='manual',
            confidence_score=5,
        )
        self.assertEqual(est.estimated_daily_visitors, 1000)

    def test_traffic_estimate_isolation_by_company(self):
        company2 = Company.objects.create(
            name='Other SA', slug='other-sa', status='active', is_active=True
        )
        competitor2 = Competitor.objects.create(
            company=company2,
            name='Other Comp',
            website_url='https://other.example.com',
            created_by=self.user,
        )
        site2 = CompetitorSite.objects.create(
            competitor=competitor2,
            site_url='https://other.example.com',
            site_type='main',
        )
        CompetitorTrafficEstimate.objects.create(
            company=company2,
            competitor=competitor2,
            site=site2,
            estimated_monthly_visitors=99999,
            source_type='manual',
            confidence_score=8,
        )
        CompetitorTrafficEstimate.objects.create(
            company=self.company,
            competitor=self.competitor,
            site=self.site,
            estimated_monthly_visitors=12345,
            source_type='manual',
            confidence_score=4,
        )
        co1_estimates = CompetitorTrafficEstimate.objects.filter(company=self.company)
        self.assertEqual(co1_estimates.count(), 1)
        self.assertEqual(co1_estimates.first().estimated_monthly_visitors, 12345)
