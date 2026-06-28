"""
Tests : validation et refus des demandes d'inscription (admin ERP).
"""
import secrets
from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from apps.core.models import Company
from apps.portals.models import (
    ClientPortalSettings,
    ClientPortalSignupRequest,
    ClientPortalAccount,
)
from apps.portals.services import signup_service

STATIC_OVERRIDE = override_settings(
    STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage'
)


def make_company(name='ApprovalTest SA'):
    return Company.objects.create(name=name, slug=name.lower().replace(' ', '-'), is_active=True)


def make_erp_superuser():
    return User.objects.create_superuser(username='admin_erp', password='adminpass', email='admin@test.com')


def make_signup(company, email='client@example.com',
                status=ClientPortalSignupRequest.STATUS_PENDING_APPROVAL):
    return ClientPortalSignupRequest.objects.create(
        company=company,
        first_name='Marie',
        last_name='Martin',
        email=email,
        password_hash=make_password('testpass123'),
        email_verification_token=secrets.token_urlsafe(48),
        status=status,
        email_verified=True,
    )


class ApproveSignupServiceTest(TestCase):

    def setUp(self):
        self.company = make_company()
        self.erp_user = make_erp_superuser()

    def test_approve_creates_portal_account(self):
        signup = make_signup(self.company)
        account = signup_service.approve_signup_request(signup, approved_by=self.erp_user)
        self.assertIsInstance(account, ClientPortalAccount)
        self.assertEqual(account.email, signup.email)
        self.assertTrue(account.created_from_signup)

    def test_approve_creates_django_user(self):
        signup = make_signup(self.company, email='new@example.com')
        signup_service.approve_signup_request(signup, approved_by=self.erp_user)
        self.assertTrue(User.objects.filter(username='new@example.com').exists())

    def test_approve_sets_status_converted(self):
        signup = make_signup(self.company, email='conv@example.com')
        signup_service.approve_signup_request(signup, approved_by=self.erp_user)
        signup.refresh_from_db()
        self.assertEqual(signup.status, ClientPortalSignupRequest.STATUS_CONVERTED)

    def test_approve_links_portal_account(self):
        signup = make_signup(self.company, email='link@example.com')
        signup_service.approve_signup_request(signup, approved_by=self.erp_user)
        signup.refresh_from_db()
        self.assertIsNotNone(signup.linked_portal_account)


class RejectSignupServiceTest(TestCase):

    def setUp(self):
        self.company = make_company('Reject SA')
        self.erp_user = make_erp_superuser()

    def test_reject_sets_status_rejected(self):
        signup = make_signup(self.company, email='rejected@example.com')
        signup_service.reject_signup_request(signup, rejected_by=self.erp_user, reason='Non éligible.')
        signup.refresh_from_db()
        self.assertEqual(signup.status, ClientPortalSignupRequest.STATUS_REJECTED)

    def test_reject_records_reason(self):
        signup = make_signup(self.company, email='reason@example.com')
        signup_service.reject_signup_request(signup, rejected_by=self.erp_user, reason='Raison test')
        signup.refresh_from_db()
        self.assertEqual(signup.rejection_reason, 'Raison test')

    def test_reject_records_rejected_by(self):
        signup = make_signup(self.company, email='by@example.com')
        signup_service.reject_signup_request(signup, rejected_by=self.erp_user)
        signup.refresh_from_db()
        self.assertEqual(signup.rejected_by, self.erp_user)


@STATIC_OVERRIDE
class ApproveSignupViewTest(TestCase):

    def setUp(self):
        self.company = make_company('View SA')
        self.erp_user = make_erp_superuser()
        self.client.force_login(self.erp_user)
        # Injecter l'entreprise dans la session (le CompanyMiddleware la lira)
        session = self.client.session
        session['current_company_id'] = self.company.pk
        session.save()

    def test_approve_view_requires_login(self):
        from django.test import Client as TC
        anon_client = TC()
        signup = make_signup(self.company, email='anon@example.com')
        response = anon_client.post(reverse('portals:signup_approve', kwargs={'pk': signup.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_approve_view_succeeds(self):
        signup = make_signup(self.company, email='view@example.com')
        response = self.client.post(reverse('portals:signup_approve', kwargs={'pk': signup.pk}))
        self.assertEqual(response.status_code, 302)
        signup.refresh_from_db()
        self.assertEqual(signup.status, ClientPortalSignupRequest.STATUS_CONVERTED)

    def test_reject_view_succeeds(self):
        signup = make_signup(self.company, email='reject-view@example.com')
        response = self.client.post(
            reverse('portals:signup_reject', kwargs={'pk': signup.pk}),
            {'reason': 'Refus via interface'},
        )
        self.assertEqual(response.status_code, 302)
        signup.refresh_from_db()
        self.assertEqual(signup.status, ClientPortalSignupRequest.STATUS_REJECTED)
