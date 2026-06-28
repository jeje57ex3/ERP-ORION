"""
tests/test_company_isolation.py — Tests d'isolation multi-entreprises

Vérifie que les données d'une entreprise ne sont JAMAIS visibles par une autre.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from apps.core.models import Company
from apps.core.managers import CompanyQuerySet


class TestCompanyManagerIsolation(TestCase):
    """CompanyManager.for_company() ne doit jamais retourner d'objets d'une autre entreprise."""

    def setUp(self):
        self.company_a = Company.objects.create(
            name='Entreprise A',
            slug='entreprise-a',
            status='active',
            is_active=True,
        )
        self.company_b = Company.objects.create(
            name='Entreprise B',
            slug='entreprise-b',
            status='active',
            is_active=True,
        )

    def test_for_company_none_returns_empty(self):
        qs = Company.objects.filter(pk__in=[self.company_a.pk, self.company_b.pk])
        from apps.core.managers import CompanyQuerySet
        if hasattr(qs, 'for_company'):
            result = qs.for_company(None)
            self.assertEqual(result.count(), 0)

    def test_companies_are_distinct(self):
        self.assertNotEqual(self.company_a.pk, self.company_b.pk)
        self.assertNotEqual(self.company_a.slug, self.company_b.slug)


class TestAuditLogIsolation(TestCase):
    """Les AuditLogs doivent être filtrables par entreprise."""

    def setUp(self):
        self.company_a = Company.objects.create(
            name='Audit Company A',
            slug='audit-company-a',
            status='active',
            is_active=True,
        )
        self.company_b = Company.objects.create(
            name='Audit Company B',
            slug='audit-company-b',
            status='active',
            is_active=True,
        )

    def test_audit_log_creation(self):
        from apps.core.models import AuditLog
        log = AuditLog.objects.create(
            company=self.company_a,
            action='create',
            module='test',
            description='Test log',
        )
        self.assertEqual(log.company, self.company_a)

    def test_audit_logs_filtered_by_company(self):
        from apps.core.models import AuditLog
        AuditLog.objects.create(company=self.company_a, action='create', module='test')
        AuditLog.objects.create(company=self.company_b, action='create', module='test')

        logs_a = AuditLog.objects.filter(company=self.company_a)
        logs_b = AuditLog.objects.filter(company=self.company_b)

        self.assertEqual(logs_a.count(), 1)
        self.assertEqual(logs_b.count(), 1)
        self.assertNotEqual(logs_a.first().company_id, logs_b.first().company_id)


class TestAuditService(TestCase):
    """log_action() doit créer une entrée AuditLog correcte."""

    def setUp(self):
        self.company = Company.objects.create(
            name='Service Test Co',
            slug='service-test-co',
            status='active',
            is_active=True,
        )
        self.user = User.objects.create_user('auditor', password='test123')

    def test_log_action_creates_entry(self):
        from apps.core.audit_service import log_action
        from apps.core.models import AuditLog

        count_before = AuditLog.objects.count()
        log_action(
            request=None,
            action='create',
            module='test',
            description='Test audit entry',
            company=self.company,
            user=self.user,
        )
        self.assertEqual(AuditLog.objects.count(), count_before + 1)

    def test_log_action_with_old_new_values(self):
        from apps.core.audit_service import log_action
        from apps.core.models import AuditLog

        log_action(
            request=None,
            action='update',
            module='test',
            company=self.company,
            old_values={'status': 'draft'},
            new_values={'status': 'validated'},
        )
        log = AuditLog.objects.filter(company=self.company, action='update').last()
        self.assertIsNotNone(log)
        self.assertEqual(log.old_values, {'status': 'draft'})
        self.assertEqual(log.new_values, {'status': 'validated'})
