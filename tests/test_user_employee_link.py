"""
tests/test_user_employee_link.py
Tests du système de liaison Utilisateur ↔ Salarié.
"""
import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from apps.core.models import Company
from apps.hr.models import Employee
from apps.accounts.services.user_employee_link_service import (
    is_user_exempt_from_employee_link,
    get_user_employee,
    link_user_to_employee,
    unlink_user_from_employee,
    create_employee_for_user,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def company(db):
    return Company.objects.create(
        name='Test SA', slug='test-sa', status='active', is_active=True,
    )


@pytest.fixture
def regular_user(db, company):
    u = User.objects.create_user(
        username='jdupont', email='jdupont@test.com',
        first_name='Jean', last_name='Dupont', password='pass',
    )
    profile = u.profile
    profile.role = 'user'
    profile.current_company = company
    profile.save()
    return u


@pytest.fixture
def admin_user(db, company):
    u = User.objects.create_user(
        username='admin_co', email='admin_co@test.com', password='pass',
    )
    profile = u.profile
    profile.role = 'admin'
    profile.current_company = company
    profile.save()
    return u


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser(
        username='root', email='root@test.com', password='pass',
    )


@pytest.fixture
def employee(db, company):
    return Employee.objects.create(
        company=company,
        first_name='Jean', last_name='Dupont',
        email='jdupont@test.com',
    )


@pytest.fixture
def employee_b(db, company):
    return Employee.objects.create(
        company=company,
        first_name='Marie', last_name='Martin',
        email='mmartin@test.com',
    )


# ---------------------------------------------------------------------------
# 1. is_user_exempt_from_employee_link
# ---------------------------------------------------------------------------

class TestExemption:
    def test_superuser_is_exempt(self, superuser):
        assert is_user_exempt_from_employee_link(superuser) is True

    def test_admin_role_is_exempt(self, admin_user):
        assert is_user_exempt_from_employee_link(admin_user) is True

    def test_regular_user_not_exempt(self, regular_user):
        assert is_user_exempt_from_employee_link(regular_user) is False

    def test_none_user_is_exempt(self):
        assert is_user_exempt_from_employee_link(None) is True

    def test_staff_is_exempt(self, db):
        u = User.objects.create_user(username='staff1', password='pass', is_staff=True)
        assert is_user_exempt_from_employee_link(u) is True


# ---------------------------------------------------------------------------
# 2. get_user_employee
# ---------------------------------------------------------------------------

class TestGetUserEmployee:
    def test_returns_none_when_no_employee(self, regular_user):
        assert get_user_employee(regular_user) is None

    def test_returns_employee_when_linked(self, regular_user, employee):
        employee.user = regular_user
        employee.save()
        result = get_user_employee(regular_user)
        assert result == employee

    def test_returns_none_for_none(self):
        assert get_user_employee(None) is None


# ---------------------------------------------------------------------------
# 3. link_user_to_employee
# ---------------------------------------------------------------------------

class TestLinkUserToEmployee:
    def test_basic_link(self, regular_user, employee):
        link_user_to_employee(regular_user, employee)
        employee.refresh_from_db()
        assert employee.user == regular_user

    def test_back_reference(self, regular_user, employee):
        link_user_to_employee(regular_user, employee)
        assert get_user_employee(regular_user) == employee

    def test_fills_empty_email_from_user(self, db, company):
        u = User.objects.create_user(username='x', email='x@test.com', password='pass')
        u.profile.role = 'user'
        u.profile.save()
        emp = Employee.objects.create(company=company, first_name='X', last_name='Y', email='')
        link_user_to_employee(u, emp)
        emp.refresh_from_db()
        assert emp.email == 'x@test.com'

    def test_raises_if_user_already_linked(self, regular_user, employee, employee_b):
        link_user_to_employee(regular_user, employee)
        with pytest.raises(ValidationError):
            link_user_to_employee(regular_user, employee_b)

    def test_raises_if_employee_already_linked(self, db, company, employee):
        u1 = User.objects.create_user(username='u1', email='u1@test.com', password='pass')
        u1.profile.role = 'user'
        u1.profile.save()
        u2 = User.objects.create_user(username='u2', email='u2@test.com', password='pass')
        u2.profile.role = 'user'
        u2.profile.save()
        link_user_to_employee(u1, employee)
        with pytest.raises(ValidationError):
            link_user_to_employee(u2, employee)


# ---------------------------------------------------------------------------
# 4. unlink_user_from_employee
# ---------------------------------------------------------------------------

class TestUnlinkUserFromEmployee:
    def test_admin_can_unlink(self, admin_user, employee):
        employee.user = admin_user
        employee.save()
        unlink_user_from_employee(admin_user)
        employee.refresh_from_db()
        assert employee.user is None

    def test_non_exempt_cannot_unlink(self, regular_user, employee):
        employee.user = regular_user
        employee.save()
        with pytest.raises(ValidationError):
            unlink_user_from_employee(regular_user)


# ---------------------------------------------------------------------------
# 5. create_employee_for_user
# ---------------------------------------------------------------------------

class TestCreateEmployeeForUser:
    def test_creates_employee(self, regular_user, company):
        emp = create_employee_for_user(regular_user, company)
        assert emp.pk is not None
        assert emp.user == regular_user
        assert emp.company == company

    def test_uses_user_name(self, regular_user, company):
        emp = create_employee_for_user(regular_user, company)
        assert emp.first_name == regular_user.first_name
        assert emp.last_name == regular_user.last_name

    def test_returns_existing_if_already_linked(self, regular_user, company, employee):
        employee.user = regular_user
        employee.save()
        result = create_employee_for_user(regular_user, company)
        assert result == employee

    def test_extra_data_applied(self, regular_user, company):
        emp = create_employee_for_user(
            regular_user, company, extra_data={'job_title': 'Développeur'}
        )
        assert emp.job_title == 'Développeur'
