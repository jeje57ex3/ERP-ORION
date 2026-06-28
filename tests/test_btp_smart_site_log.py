import pytest
from django.utils import timezone
from apps.btp_smart_site_log.models import SiteLog, SiteLogIncident
from apps.btp_smart_site_log import services

pytestmark = pytest.mark.django_db


@pytest.fixture
def company(db):
    from apps.core.models import Company
    return Company.objects.create(name='BTP Smart Test', slug='btp-smart-test', is_active=True)


@pytest.fixture
def user(db):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create_user(username='chef_chantier', password='testpass123')


@pytest.fixture
def site_log(company, user):
    return services.create_site_log(
        company, 'PROJ-001', 'daily', 'Journal du 26/06', timezone.now(),
        project_name='Construction Immeuble A',
        description='Coulage béton niveau 3',
        workers_count=12,
        weather='sunny',
        temperature_celsius=22,
        progress_percent=45,
        logged_by=user,
    )


# ── Model tests ───────────────────────────────────────────────────────────────

def test_site_log_str(site_log):
    assert 'PROJ-001' in str(site_log) or 'Journal' in str(site_log)


def test_site_log_fields(site_log):
    assert site_log.project_id == 'PROJ-001'
    assert site_log.log_type == 'daily'
    assert site_log.workers_count == 12
    assert site_log.weather == 'sunny'
    assert site_log.progress_percent == 45


def test_site_log_project_name(site_log):
    assert site_log.project_name == 'Construction Immeuble A'


# ── Service tests — create_site_log ──────────────────────────────────────────

def test_create_site_log(company, user):
    log = services.create_site_log(
        company, 'PROJ-002', 'inspection', 'Inspection fondations', timezone.now(),
        workers_count=4, progress_percent=20,
    )
    assert log.pk is not None
    assert log.company == company
    assert log.log_type == 'inspection'


def test_site_log_default_workers(company):
    log = services.create_site_log(
        company, 'PROJ-003', 'meeting', 'Réunion hebdo', timezone.now(),
    )
    assert log.workers_count == 0


# ── Service tests — add_incident ──────────────────────────────────────────────

def test_add_incident(company, site_log):
    incident = services.add_incident(
        company, site_log, 'accident', 'low', 'Chute légère d\'un outil',
    )
    assert incident.pk is not None
    assert incident.severity == 'low'
    assert incident.is_resolved is False


def test_add_incident_high_severity(company, site_log):
    incident = services.add_incident(
        company, site_log, 'accident', 'high', 'Blessure légère sur chantier',
    )
    assert incident.severity == 'high'
    assert incident.is_resolved is False


def test_site_log_incidents_relation(company, site_log):
    services.add_incident(company, site_log, 'equipment', 'low', 'Panne grue')
    services.add_incident(company, site_log, 'delay', 'low', 'Retard livraison')
    assert site_log.incidents.count() == 2


# ── Service tests — resolve_incident ─────────────────────────────────────────

def test_resolve_incident(company, site_log):
    incident = services.add_incident(company, site_log, 'accident', 'low', 'Incident test')
    services.resolve_incident(incident, corrective_action='Mesures prises')
    incident.refresh_from_db()
    assert incident.is_resolved is True
    assert incident.resolved_at is not None
    assert incident.corrective_action == 'Mesures prises'


def test_resolve_incident_no_action(company, site_log):
    incident = services.add_incident(company, site_log, 'delay', 'low', 'Retard')
    services.resolve_incident(incident)
    incident.refresh_from_db()
    assert incident.is_resolved is True


# ── Service tests — get_site_logs ────────────────────────────────────────────

def test_get_site_logs_all(company, site_log):
    logs = services.get_site_logs(company, project_id=None, log_type=None, date_from=None, date_to=None)
    assert site_log in logs


def test_get_site_logs_filter_project(company, site_log):
    services.create_site_log(company, 'PROJ-999', 'daily', 'Autre journal', timezone.now())
    logs = services.get_site_logs(company, project_id='PROJ-001', log_type=None, date_from=None, date_to=None)
    assert all(l.project_id == 'PROJ-001' for l in logs)


def test_get_site_logs_filter_type(company, site_log):
    services.create_site_log(company, 'PROJ-001', 'inspection', 'Inspection', timezone.now())
    daily = services.get_site_logs(company, project_id=None, log_type='daily', date_from=None, date_to=None)
    assert all(l.log_type == 'daily' for l in daily)


# ── Service tests — get_open_incidents ───────────────────────────────────────

def test_get_open_incidents(company, site_log):
    services.add_incident(company, site_log, 'accident', 'low', 'Open')
    open_inc = services.get_open_incidents(company)
    assert open_inc.count() >= 1


def test_get_open_incidents_excludes_resolved(company, site_log):
    incident = services.add_incident(company, site_log, 'accident', 'low', 'Resolved')
    services.resolve_incident(incident)
    open_inc = services.get_open_incidents(company)
    assert incident not in open_inc


# ── Service tests — get_site_stats ───────────────────────────────────────────

def test_get_site_stats(company, site_log):
    services.add_incident(company, site_log, 'accident', 'low', 'Inc 1')
    incident2 = services.add_incident(company, site_log, 'delay', 'low', 'Inc 2')
    services.resolve_incident(incident2)
    stats = services.get_site_stats(company, 'PROJ-001')
    assert stats['total_logs'] >= 1
    assert stats['open_incidents'] >= 1
    assert stats['resolved_incidents'] >= 1


def test_get_site_stats_empty_project(company):
    stats = services.get_site_stats(company, 'PROJ-NONEXISTENT')
    assert stats['total_logs'] == 0
    assert stats['open_incidents'] == 0


# ── Isolation test ────────────────────────────────────────────────────────────

def test_company_isolation(company, site_log):
    from apps.core.models import Company
    other_company = Company.objects.create(name='Other BTP', slug='other-btp', is_active=True)
    logs = services.get_site_logs(other_company, project_id=None, log_type=None, date_from=None, date_to=None)
    assert site_log not in logs
