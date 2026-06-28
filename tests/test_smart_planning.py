"""
tests/test_smart_planning.py
Tests du module Planning Intelligent.
"""
import pytest
from django.utils import timezone
from datetime import timedelta
from apps.core.models import Company
from apps.smart_planning.models import PlanningEvent, PlanningConflict
from apps.smart_planning.services import (
    create_event, detect_conflicts, get_events_for_period,
    get_conflicts, get_planning_stats,
)


@pytest.fixture
def company(db):
    return Company.objects.create(name='Planning SA', slug='planning-sa', status='active', is_active=True)


@pytest.fixture
def user(db, django_user_model):
    return django_user_model.objects.create_user(username='plan_user', password='pass')


@pytest.fixture
def now():
    return timezone.now()


class TestCreateEvent:
    def test_creates_event(self, db, company, now):
        event = create_event(company, 'RDV chantier', 'site_visit',
                             start_at=now, end_at=now + timedelta(hours=2))
        assert event.pk is not None
        assert event.status == 'planned'

    def test_no_conflict_no_employee(self, db, company, now):
        event = create_event(company, 'Réunion', 'meeting',
                             start_at=now, end_at=now + timedelta(hours=1))
        conflicts = PlanningConflict.objects.filter(company=company)
        assert conflicts.count() == 0


class TestDetectConflicts:
    def test_detects_overlap(self, db, company, now, django_user_model):
        from apps.hr.models import Employee
        emp_user = django_user_model.objects.create_user(username='emp_plan', password='pass')
        emp = Employee.objects.create(company=company, first_name='Test', last_name='Emp',
                                     job_title='Tech', contract_type='cdi')
        e1 = create_event(company, 'Matin', 'intervention',
                          start_at=now, end_at=now + timedelta(hours=4), employee=emp)
        e2 = create_event(company, 'Chevauchement', 'intervention',
                          start_at=now + timedelta(hours=2), end_at=now + timedelta(hours=6),
                          employee=emp)
        conflicts = PlanningConflict.objects.filter(company=company, event=e2)
        assert conflicts.count() == 1
        assert conflicts.first().conflict_type == 'double_booking'

    def test_no_conflict_sequential(self, db, company, now, django_user_model):
        from apps.hr.models import Employee
        emp_user = django_user_model.objects.create_user(username='emp_plan2', password='pass')
        emp = Employee.objects.create(company=company, first_name='Test', last_name='Emp2',
                                     job_title='Tech', contract_type='cdi')
        create_event(company, 'Matin', 'intervention',
                     start_at=now, end_at=now + timedelta(hours=4), employee=emp)
        create_event(company, 'Après-midi', 'intervention',
                     start_at=now + timedelta(hours=4), end_at=now + timedelta(hours=8),
                     employee=emp)
        conflicts = PlanningConflict.objects.filter(company=company)
        assert conflicts.count() == 0


class TestGetEventsForPeriod:
    def test_returns_events_in_period(self, db, company, now):
        event = create_event(company, 'Demain', 'meeting',
                             start_at=now + timedelta(days=1),
                             end_at=now + timedelta(days=1, hours=2))
        start = now.date()
        end = (now + timedelta(days=7)).date()
        result = get_events_for_period(company, start, end)
        assert event in result

    def test_excludes_out_of_range(self, db, company, now):
        event = create_event(company, 'Lointain', 'meeting',
                             start_at=now + timedelta(days=60),
                             end_at=now + timedelta(days=60, hours=1))
        start = now.date()
        end = (now + timedelta(days=7)).date()
        result = get_events_for_period(company, start, end)
        assert event not in result


class TestGetConflicts:
    def test_returns_unresolved(self, db, company, now, django_user_model):
        from apps.hr.models import Employee
        emp_user = django_user_model.objects.create_user(username='emp_plan3', password='pass')
        emp = Employee.objects.create(company=company, first_name='Test', last_name='Emp3',
                                     job_title='Tech', contract_type='cdi')
        create_event(company, 'E1', 'intervention',
                     start_at=now, end_at=now + timedelta(hours=4), employee=emp)
        create_event(company, 'E2', 'intervention',
                     start_at=now + timedelta(hours=2), end_at=now + timedelta(hours=6),
                     employee=emp)
        conflicts = get_conflicts(company)
        assert conflicts.count() >= 1


class TestPlanningStats:
    def test_stats_keys(self, db, company):
        stats = get_planning_stats(company)
        assert 'this_week' in stats
        assert 'conflicts' in stats
        assert 'total' in stats
