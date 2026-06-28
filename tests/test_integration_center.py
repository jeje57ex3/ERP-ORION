"""
tests/test_integration_center.py
Tests du module Centre d'Intégrations.
"""
import pytest
from django.utils import timezone
from apps.core.models import Company
from apps.integration_center.models import IntegrationConfig, IntegrationSyncLog
from apps.integration_center.services import (
    create_integration, update_integration_config,
    start_sync, finish_sync, get_active_integrations,
    get_sync_logs, get_integration_stats,
)


@pytest.fixture
def company(db):
    return Company.objects.create(name='Integ SA', slug='integ-sa', status='active', is_active=True)


@pytest.fixture
def user(db, django_user_model):
    return django_user_model.objects.create_user(username='integ_user', password='pass')


@pytest.fixture
def integration(db, company, user):
    return create_integration(company, 'stripe', 'Stripe Principal',
                              config={'api_key': 'sk_test_...'}, created_by=user)


class TestCreateIntegration:
    def test_creates_integration(self, db, company, user):
        integ = create_integration(company, 'slack', 'Slack RH', config={'webhook': 'url'})
        assert integ.pk is not None
        assert integ.integration_type == 'slack'
        assert integ.is_active is True

    def test_config_stored(self, db, company):
        integ = create_integration(company, 'sendgrid', 'SG', config={'key': 'SG.xxx'})
        assert integ.config == {'key': 'SG.xxx'}

    def test_interval_default(self, db, company):
        integ = create_integration(company, 'custom', 'Custom', config={})
        assert integ.sync_interval_minutes == 60


class TestUpdateConfig:
    def test_updates_config(self, db, integration):
        update_integration_config(integration, {'api_key': 'sk_new'})
        integration.refresh_from_db()
        assert integration.config == {'api_key': 'sk_new'}


class TestSyncLifecycle:
    def test_start_sync_creates_log(self, db, company, integration):
        log = start_sync(company, integration)
        assert log.pk is not None
        assert log.status == 'running'

    def test_finish_sync_success(self, db, company, integration):
        log = start_sync(company, integration)
        finish_sync(log, records_synced=50)
        log.refresh_from_db()
        assert log.status == 'success'
        assert log.records_synced == 50
        assert log.finished_at is not None

    def test_finish_sync_updates_last_sync(self, db, company, integration):
        log = start_sync(company, integration)
        finish_sync(log, records_synced=10)
        integration.refresh_from_db()
        assert integration.last_sync_at is not None

    def test_finish_sync_partial(self, db, company, integration):
        log = start_sync(company, integration)
        finish_sync(log, records_synced=10, records_failed=2)
        log.refresh_from_db()
        assert log.status == 'partial'

    def test_finish_sync_failed(self, db, company, integration):
        log = start_sync(company, integration)
        finish_sync(log, records_synced=0, records_failed=5, errors=['err1'])
        log.refresh_from_db()
        assert log.status == 'failed'
        assert log.errors == ['err1']

    def test_duration_property(self, db, company, integration):
        log = start_sync(company, integration)
        finish_sync(log, records_synced=1)
        log.refresh_from_db()
        assert log.duration_seconds is not None
        assert log.duration_seconds >= 0


class TestGetActiveIntegrations:
    def test_returns_active(self, db, company, integration):
        result = list(get_active_integrations(company))
        assert integration in result

    def test_excludes_inactive(self, db, company, integration):
        integration.is_active = False
        integration.save()
        result = list(get_active_integrations(company))
        assert integration not in result

    def test_filter_by_type(self, db, company, integration):
        result = list(get_active_integrations(company, integration_type='stripe'))
        assert integration in result
        result_slack = list(get_active_integrations(company, integration_type='slack'))
        assert integration not in result_slack


class TestGetSyncLogs:
    def test_returns_logs(self, db, company, integration):
        log = start_sync(company, integration)
        finish_sync(log, records_synced=1)
        result = list(get_sync_logs(company))
        assert log in result

    def test_filter_by_integration(self, db, company, integration, user):
        other = create_integration(company, 'slack', 'Slack', config={})
        log1 = start_sync(company, integration)
        log2 = start_sync(company, other)
        result = list(get_sync_logs(company, integration=integration))
        assert log1 in result
        assert log2 not in result


class TestIntegrationStats:
    def test_stats_keys(self, db, company, integration):
        stats = get_integration_stats(company)
        assert 'total' in stats
        assert 'active' in stats
        assert 'total_syncs' in stats
        assert 'failed_syncs' in stats
        assert stats['total'] >= 1
        assert stats['active'] >= 1
