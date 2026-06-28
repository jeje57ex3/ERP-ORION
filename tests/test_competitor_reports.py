"""
tests/test_competitor_reports.py — Tests de generation de rapports concurrentiels

Lance avec : pytest tests/test_competitor_reports.py -v
"""
import os
import tempfile
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth.models import User
from decimal import Decimal

from apps.core.models import Company
from apps.competitor_intelligence.models import (
    Competitor, CompetitorSite, CompetitorProduct, CompetitorAdvantage,
)


class TestExcelReportGeneration(TestCase):

    def setUp(self):
        self.user = User.objects.create_superuser(
            username='admin', password='adminpass', email='admin@test.com'
        )
        self.company = Company.objects.create(
            name='Report SA', slug='report-sa', status='active', is_active=True
        )
        self.competitor = Competitor.objects.create(
            company=self.company,
            name='Report Competitor',
            website_url='https://report.example.com',
            created_by=self.user,
        )
        self.site = CompetitorSite.objects.create(
            competitor=self.competitor,
            site_url='https://report.example.com',
            site_type='main',
        )

    def test_generate_excel_report_returns_bytes(self):
        from apps.competitor_intelligence.services.report_service import generate_competitor_excel_report
        try:
            result = generate_competitor_excel_report(self.company)
            self.assertIsInstance(result, bytes)
            self.assertGreater(len(result), 0)
        except ImportError:
            self.skipTest('openpyxl non installe')

    def test_excel_report_with_products(self):
        from apps.competitor_intelligence.services.report_service import generate_competitor_excel_report
        CompetitorProduct.objects.create(
            company=self.company,
            competitor=self.competitor,
            site=self.site,
            name='Report Widget',
            price=Decimal('149.99'),
            currency='EUR',
        )
        try:
            result = generate_competitor_excel_report(self.company)
            self.assertIsInstance(result, bytes)
        except ImportError:
            self.skipTest('openpyxl non installe')

    def test_excel_report_with_advantages(self):
        from apps.competitor_intelligence.services.report_service import generate_competitor_excel_report
        CompetitorAdvantage.objects.create(
            company=self.company,
            competitor=self.competitor,
            title='Meilleur prix',
            advantage_type='price',
            score=8,
            detected_manually=True,
            created_by=self.user,
        )
        try:
            result = generate_competitor_excel_report(self.company)
            self.assertIsInstance(result, bytes)
        except ImportError:
            self.skipTest('openpyxl non installe')

    def test_excel_report_empty_company(self):
        from apps.competitor_intelligence.services.report_service import generate_competitor_excel_report
        empty_company = Company.objects.create(
            name='Empty Report SA', slug='empty-report-sa', status='active', is_active=True
        )
        try:
            result = generate_competitor_excel_report(empty_company)
            self.assertIsInstance(result, bytes)
        except ImportError:
            self.skipTest('openpyxl non installe')


class TestPdfReportGeneration(TestCase):

    def setUp(self):
        self.user = User.objects.create_superuser(
            username='admin2', password='adminpass', email='admin2@test.com'
        )
        self.company = Company.objects.create(
            name='PDF Report SA', slug='pdf-report-sa', status='active', is_active=True
        )
        self.competitor = Competitor.objects.create(
            company=self.company,
            name='PDF Competitor',
            website_url='https://pdf.example.com',
            created_by=self.user,
        )

    def test_generate_pdf_report_returns_bytes(self):
        from apps.competitor_intelligence.services.report_service import generate_competitor_pdf_report
        try:
            result = generate_competitor_pdf_report(self.company)
            self.assertIsInstance(result, bytes)
            self.assertGreater(len(result), 0)
        except ImportError:
            self.skipTest('reportlab non installe')

    def test_pdf_starts_with_pdf_header(self):
        from apps.competitor_intelligence.services.report_service import generate_competitor_pdf_report
        try:
            result = generate_competitor_pdf_report(self.company)
            self.assertTrue(result.startswith(b'%PDF'), 'Le PDF doit commencer par %PDF')
        except ImportError:
            self.skipTest('reportlab non installe')


class TestMarketPositionReport(TestCase):

    def setUp(self):
        self.user = User.objects.create_superuser(
            username='admin3', password='adminpass', email='admin3@test.com'
        )
        self.company = Company.objects.create(
            name='Position SA', slug='position-sa', status='active', is_active=True
        )

    def test_generate_market_position_report(self):
        from apps.competitor_intelligence.services.report_service import generate_market_position_report
        result = generate_market_position_report(self.company)
        self.assertIsInstance(result, dict)

    def test_market_position_report_structure(self):
        from apps.competitor_intelligence.services.report_service import generate_market_position_report
        result = generate_market_position_report(self.company)
        expected_keys = ['company', 'competitors_count', 'generated_at']
        for key in expected_keys:
            self.assertIn(key, result, f"Cle '{key}' manquante dans le rapport")

    def test_market_position_with_competitors(self):
        from apps.competitor_intelligence.services.report_service import generate_market_position_report
        for i in range(3):
            Competitor.objects.create(
                company=self.company,
                name=f'Competitor {i}',
                website_url=f'https://comp{i}.example.com',
                created_by=self.user,
            )
        result = generate_market_position_report(self.company)
        self.assertEqual(result['competitors_count'], 3)
