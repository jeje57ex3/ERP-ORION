"""
tests/test_system_observability.py
Tests du module Observabilité Système.
"""
import pytest
from apps.core.models import Company
from apps.system_observability.models import SystemHealthCheck, SystemObservabilityAlert
from apps.system_observability.services import (
    record_health_check, get_latest_health_checks, get_health_status,
    create_system_alert, acknowledge_system_alert,
    get_system_alerts, get_check_history, get_observability_stats,
)


@pytest.fixture
def company(db):
    return Company.objects.create(name='Obs SA', slug='obs-sa', status='active', is_active=True)


@pytest.fixture
def user(db, django_user_model):
    return django_user_model.objects.create_user(username='obs_user', password='pass')


class TestRecordHealthCheck:
    def test_creates_check(self, db, company):
        check = record_health_check(company, 'database', 'ok', response_time_ms=5)
        assert check.pk is not None
        assert check.status == 'ok'
        assert check.response_time_ms == 5

    def test_with_message(self, db, company):
        check = record_health_check(company, 'cache', 'warning', message='Latence élevée')
        assert check.message == 'Latence élevée'

    def test_with_metadata(self, db, company):
        check = record_health_check(company, 'disk_space', 'ok', metadata={'used_pct': 72})
        assert check.metadata == {'used_pct': 72}


class TestGetLatestHealthChecks:
    def test_returns_latest_per_type(self, db, company):
        record_health_check(company, 'database', 'ok')
        record_health_check(company, 'database', 'warning')
        checks = list(get_latest_health_checks(company))
        db_checks = [c for c in checks if c.check_type == 'database']
        assert len(db_checks) == 1
        assert db_checks[0].status == 'warning'

    def test_multiple_types(self, db, company):
        record_health_check(company, 'database', 'ok')
        record_health_check(company, 'cache', 'ok')
        checks = list(get_latest_health_checks(company))
        types = {c.check_type for c in checks}
        assert 'database' in types
        assert 'cache' in types


class TestGetHealthStatus:
    def test_ok_when_all_ok(self, db, company):
        record_health_check(company, 'database', 'ok')
        record_health_check(company, 'cache', 'ok')
        assert get_health_status(company) == 'ok'

    def test_warning_when_any_warning(self, db, company):
        record_health_check(company, 'database', 'ok')
        record_health_check(company, 'cache', 'warning')
        assert get_health_status(company) == 'warning'

    def test_critical_overrides_warning(self, db, company):
        record_health_check(company, 'database', 'warning')
        record_health_check(company, 'cache', 'critical')
        assert get_health_status(company) == 'critical'

    def test_unknown_when_no_checks(self, db, company):
        assert get_health_status(company) == 'unknown'


class TestCreateSystemAlert:
    def test_creates_alert(self, db, company):
        alert = create_system_alert(company, 'database', 'critical',
                                    'BDD inaccessible', 'Connexion refusée')
        assert alert.pk is not None
        assert alert.is_acknowledged is False

    def test_severity_stored(self, db, company):
        alert = create_system_alert(company, 'cpu', 'warning', 'CPU élevé', 'CPU à 95%')
        assert alert.severity == 'warning'


class TestAcknowledgeSystemAlert:
    def test_acknowledges(self, db, company, user):
        alert = create_system_alert(company, 'database', 'critical', 'Down', 'Msg')
        acknowledge_system_alert(alert, user)
        alert.refresh_from_db()
        assert alert.is_acknowledged is True
        assert alert.acknowledged_by == user
        assert alert.acknowledged_at is not None


class TestGetSystemAlerts:
    def test_returns_unacknowledged(self, db, company):
        alert = create_system_alert(company, 'cache', 'warning', 'Lent', 'Msg')
        result = list(get_system_alerts(company))
        assert alert in result

    def test_excludes_acknowledged_by_default(self, db, company, user):
        alert = create_system_alert(company, 'cache', 'warning', 'Lent', 'Msg')
        acknowledge_system_alert(alert, user)
        result = list(get_system_alerts(company))
        assert alert not in result

    def test_includes_acknowledged_when_requested(self, db, company, user):
        alert = create_system_alert(company, 'cache', 'warning', 'Lent', 'Msg')
        acknowledge_system_alert(alert, user)
        result = list(get_system_alerts(company, include_acknowledged=True))
        assert alert in result

    def test_filter_by_severity(self, db, company):
        create_system_alert(company, 'database', 'critical', 'Down', 'Msg')
        create_system_alert(company, 'cache', 'info', 'Info', 'Msg')
        result = list(get_system_alerts(company, severity='critical'))
        assert all(a.severity == 'critical' for a in result)


class TestGetCheckHistory:
    def test_returns_history_for_type(self, db, company):
        c1 = record_health_check(company, 'database', 'ok')
        c2 = record_health_check(company, 'database', 'warning')
        c3 = record_health_check(company, 'cache', 'ok')
        history = list(get_check_history(company, 'database'))
        assert c1 in history
        assert c2 in history
        assert c3 not in history


class TestObservabilityStats:
    def test_stats_keys(self, db, company):
        record_health_check(company, 'database', 'ok')
        create_system_alert(company, 'cache', 'warning', 'Lent', 'msg')
        stats = get_observability_stats(company)
        assert 'overall_status' in stats
        assert 'checks_ok' in stats
        assert 'checks_warning' in stats
        assert 'checks_critical' in stats
        assert 'unacknowledged_alerts' in stats
        assert stats['checks_ok'] >= 1
        assert stats['unacknowledged_alerts'] >= 1
