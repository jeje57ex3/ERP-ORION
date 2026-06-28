"""
tests/test_audit_compliance.py
Tests du module Audit & Conformité.
"""
import pytest
from django.contrib.auth.models import User
from apps.core.models import Company, AuditLog
from apps.audit_compliance.services import (
    get_audit_logs, get_sensitive_logs, get_audit_stats, export_audit_csv,
)


@pytest.fixture
def company(db):
    return Company.objects.create(name='Audit SA', slug='audit-sa', status='active', is_active=True)


@pytest.fixture
def user(db):
    return User.objects.create_user(username='auditor', email='audit@test.com', password='pass')


@pytest.fixture
def audit_log(db, company, user):
    return AuditLog.objects.create(
        company=company, user=user,
        action='delete', module='documents',
        description='Suppression document',
    )


class TestGetAuditLogs:
    def test_filters_by_company(self, db, company, audit_log):
        other = Company.objects.create(name='Other', slug='audit-other', status='active', is_active=True)
        AuditLog.objects.create(company=other, action='create', module='crm')
        logs = list(get_audit_logs(company))
        assert all(l.company_id == company.pk for l in logs)

    def test_filters_by_action(self, db, company, user):
        AuditLog.objects.create(company=company, user=user, action='create', module='crm')
        AuditLog.objects.create(company=company, user=user, action='delete', module='crm')
        logs = list(get_audit_logs(company, action='create'))
        assert all(l.action == 'create' for l in logs)

    def test_filters_by_module(self, db, company, audit_log):
        logs = list(get_audit_logs(company, module='documents'))
        assert all(l.module == 'documents' for l in logs)


class TestGetSensitiveLogs:
    def test_returns_only_sensitive_actions(self, db, company, user):
        AuditLog.objects.create(company=company, user=user, action='delete', module='documents')
        AuditLog.objects.create(company=company, user=user, action='view', module='crm')
        logs = list(get_sensitive_logs(company))
        assert all(l.action in {'delete', 'permission_change', 'export', 'payment',
                                 'db_create', 'db_delete', 'db_backup', 'validate'} for l in logs)


class TestExportCsv:
    def test_csv_has_headers(self, db, company, audit_log):
        csv_data = export_audit_csv(company)
        assert 'Date' in csv_data
        assert 'Utilisateur' in csv_data
        assert 'Action' in csv_data

    def test_csv_has_data(self, db, company, user, audit_log):
        csv_data = export_audit_csv(company)
        assert 'auditor' in csv_data


class TestAuditStats:
    def test_stats_returns_counts(self, db, company, audit_log):
        stats = get_audit_stats(company)
        assert 'total' in stats
        assert 'today' in stats
        assert stats['total'] >= 1
