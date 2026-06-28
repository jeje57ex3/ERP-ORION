"""
tests/test_quality_incidents.py
Tests du module Qualité & Incidents.
"""
import pytest
from django.utils import timezone
from apps.core.models import Company
from apps.quality_incidents.models import QualityIncident, QualityIncidentComment
from apps.quality_incidents.services import (
    create_incident, resolve_incident, add_comment,
    get_open_incidents, get_incident_stats,
)


@pytest.fixture
def company(db):
    return Company.objects.create(name='Quality SA', slug='quality-sa', status='active', is_active=True)


@pytest.fixture
def user(db, django_user_model):
    return django_user_model.objects.create_user(username='qi_user', password='pass')


@pytest.fixture
def incident(db, company):
    return QualityIncident.objects.create(
        company=company, title='Produit défectueux', incident_type='defective_product',
        severity='normal', status='open',
    )


class TestCreateIncident:
    def test_creates_incident(self, db, company):
        inc = create_incident(company, 'Retard', 'delivery_delay')
        assert inc.pk is not None
        assert inc.status == 'open'

    def test_creates_smart_alert_for_critical(self, db, company):
        from apps.smart_alerts.models import SmartAlert
        create_incident(company, 'Accident', 'site_incident', severity='critical')
        alert = SmartAlert.objects.filter(company=company, source_module='quality_incidents').first()
        assert alert is not None
        assert alert.priority == 'critical'

    def test_creates_smart_alert_for_high(self, db, company):
        from apps.smart_alerts.models import SmartAlert
        create_incident(company, 'Grave NC', 'non_conformity', severity='high')
        alert = SmartAlert.objects.filter(
            company=company, source_module='quality_incidents', priority='high'
        ).first()
        assert alert is not None

    def test_no_alert_for_normal(self, db, company):
        from apps.smart_alerts.models import SmartAlert
        create_incident(company, 'Petite erreur', 'other', severity='normal')
        count = SmartAlert.objects.filter(company=company).count()
        assert count == 0

    def test_brand_key_stored(self, db, company):
        inc = create_incident(company, 'Retour SIÈCLE', 'customer_return', brand_key='siecle')
        assert inc.brand_key == 'siecle'


class TestResolveIncident:
    def test_sets_resolved(self, db, incident, user):
        resolve_incident(incident, corrective_action='Action corrective', user=user, comment='OK')
        incident.refresh_from_db()
        assert incident.status == 'resolved'
        assert incident.resolved_at is not None
        assert incident.corrective_action == 'Action corrective'

    def test_adds_comment_on_resolve(self, db, incident, user):
        resolve_incident(incident, user=user, comment='Clôture confirmée')
        comments = incident.comments.all()
        assert comments.count() == 1
        assert comments.first().content == 'Clôture confirmée'


class TestAddComment:
    def test_adds_comment(self, db, incident, user):
        comment = add_comment(incident, user, 'Premier commentaire')
        assert comment.pk is not None
        assert comment.user == user
        assert comment.content == 'Premier commentaire'

    def test_multiple_comments(self, db, incident, user):
        add_comment(incident, user, 'C1')
        add_comment(incident, user, 'C2')
        assert incident.comments.count() == 2


class TestGetOpenIncidents:
    def test_returns_open(self, db, company, incident):
        result = get_open_incidents(company)
        assert incident in result

    def test_excludes_resolved(self, db, company, incident, user):
        resolve_incident(incident)
        result = get_open_incidents(company)
        assert incident not in result

    def test_filter_by_severity(self, db, company):
        inc = create_incident(company, 'Critique', 'site_incident', severity='critical')
        result = get_open_incidents(company, severity='critical')
        assert inc in result
        result_low = get_open_incidents(company, severity='low')
        assert inc not in result_low


class TestGetIncidentStats:
    def test_stats_keys(self, db, company, incident):
        stats = get_incident_stats(company)
        assert 'open' in stats
        assert 'critical' in stats
        assert 'in_progress' in stats
        assert 'resolved_this_month' in stats
        assert stats['open'] >= 1
