"""
tests/test_smart_alerts.py
Tests du module Centre d'alertes intelligent.
"""
import pytest
from django.utils import timezone
from apps.core.models import Company
from apps.smart_alerts.models import SmartAlert
from apps.smart_alerts.services import (
    create_alert, resolve_alert, acknowledge_alert, ignore_alert,
    get_open_alerts, get_alert_stats,
)


@pytest.fixture
def company(db):
    return Company.objects.create(name='Alertes SA', slug='alertes-sa', status='active', is_active=True)


@pytest.fixture
def alert(db, company):
    return SmartAlert.objects.create(
        company=company, title='Test alert', source_module='test',
        priority='high', status='open',
    )


class TestCreateAlert:
    def test_creates_alert(self, db, company):
        alert = create_alert(company, 'Stock faible', 'inventory', priority='high')
        assert alert.pk is not None
        assert alert.status == 'open'

    def test_deduplication_same_object(self, db, company):
        a1 = create_alert(company, 'Facture', 'accounting',
                          related_object_type='Invoice', related_object_id='42')
        a2 = create_alert(company, 'Facture dupliquée', 'accounting',
                          related_object_type='Invoice', related_object_id='42')
        assert a1.pk == a2.pk

    def test_no_dedup_different_objects(self, db, company):
        a1 = create_alert(company, 'Facture 1', 'accounting',
                          related_object_type='Invoice', related_object_id='1')
        a2 = create_alert(company, 'Facture 2', 'accounting',
                          related_object_type='Invoice', related_object_id='2')
        assert a1.pk != a2.pk


class TestAlertLifecycle:
    def test_resolve(self, db, company, alert):
        resolve_alert(alert)
        alert.refresh_from_db()
        assert alert.status == 'resolved'
        assert alert.resolved_at is not None

    def test_acknowledge(self, db, company, alert):
        acknowledge_alert(alert)
        alert.refresh_from_db()
        assert alert.status == 'acknowledged'

    def test_ignore(self, db, company, alert):
        ignore_alert(alert)
        alert.refresh_from_db()
        assert alert.status == 'ignored'


class TestAlertQueries:
    def test_get_open_alerts_filters_by_company(self, db, company, alert):
        other = Company.objects.create(name='Other', slug='other-co', status='active', is_active=True)
        SmartAlert.objects.create(company=other, title='Other alert', source_module='test')
        result = list(get_open_alerts(company))
        assert all(a.company_id == company.pk for a in result)

    def test_get_open_alerts_excludes_resolved(self, db, company, alert):
        resolve_alert(alert)
        result = list(get_open_alerts(company))
        assert alert not in result

    def test_get_alert_stats(self, db, company):
        SmartAlert.objects.create(company=company, title='Crit', source_module='test', priority='critical')
        SmartAlert.objects.create(company=company, title='High', source_module='test', priority='high')
        stats = get_alert_stats(company)
        assert stats['critical'] == 1
        assert stats['total_open'] >= 2


class TestAlertCompanyIsolation:
    def test_company_isolation(self, db, company):
        other = Company.objects.create(name='Other', slug='other-c2', status='active', is_active=True)
        create_alert(other, 'Alert other company', 'test')
        assert get_open_alerts(company).filter(company=other).count() == 0
