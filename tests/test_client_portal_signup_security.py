"""
Tests : sécurité de l'inscription portail client.
"""
import secrets
from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from apps.core.models import Company
from apps.portals.models import ClientPortalSettings, ClientPortalSignupRequest, ClientPortalSignupAttempt
from apps.portals.services.rate_limit_service import can_submit_signup, record_signup_attempt

STATIC_OVERRIDE = override_settings(
    STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage'
)


def make_company(name='SecTest SA'):
    return Company.objects.create(name=name, slug=name.lower().replace(' ', '-'), is_active=True)


def make_settings(company, **kwargs):
    defaults = dict(
        allow_client_registration=True,
        registration_requires_approval=True,
        registration_requires_email_verification=False,
        allow_unknown_clients=True,
        notify_admin_on_registration=False,
    )
    defaults.update(kwargs)
    obj, _ = ClientPortalSettings.objects.get_or_create(company=company)
    for k, v in defaults.items():
        setattr(obj, k, v)
    obj.save()
    return obj


VALID_POST = {
    'first_name': 'Sec', 'last_name': 'Test',
    'email': 'sec@example.com',
    'password': 'SecurePass123!', 'password_confirm': 'SecurePass123!',
    'accept_terms': 'on', 'website': '',
}


@STATIC_OVERRIDE
class HoneypotTest(TestCase):

    def setUp(self):
        self.company = make_company()
        make_settings(self.company)

    def test_honeypot_filled_blocks_silently(self):
        """Remplir le honeypot redirige vers succès sans créer de demande."""
        count_before = ClientPortalSignupRequest.objects.count()
        post_data = {**VALID_POST, 'website': 'http://spam.com'}
        response = self.client.post(reverse('client_portal:register'), post_data)
        self.assertIn(response.status_code, [200, 302])
        self.assertEqual(ClientPortalSignupRequest.objects.count(), count_before)


class RateLimitTest(TestCase):

    def test_ip_rate_limit_5_per_hour(self):
        ip = '192.168.1.100'
        for i in range(5):
            record_signup_attempt(ip, f'user{i}@test.com')
        allowed, msg = can_submit_signup(ip, 'new@test.com')
        self.assertFalse(allowed)
        self.assertIn('IP', msg)

    def test_email_rate_limit_3_per_day(self):
        email = 'spam@test.com'
        ip_base = '10.0.0.'
        for i in range(3):
            record_signup_attempt(f'{ip_base}{i}', email)
        allowed, msg = can_submit_signup('10.0.0.99', email)
        self.assertFalse(allowed)
        self.assertIn('email', msg.lower())

    def test_new_ip_and_email_is_allowed(self):
        allowed, msg = can_submit_signup('1.2.3.4', 'fresh@test.com')
        self.assertTrue(allowed)
        self.assertIsNone(msg)


class NoERP_UserCreatedTest(TestCase):
    """S'assurer que l'inscription ne crée pas de staff ERP."""

    def setUp(self):
        self.company = make_company('NoERP SA')
        make_settings(self.company,
                      registration_requires_approval=False,
                      registration_requires_email_verification=False,
                      notify_admin_on_registration=False)

    def test_approved_user_is_not_staff(self):
        from apps.portals.services import signup_service
        from django.contrib.auth.hashers import make_password

        signup = ClientPortalSignupRequest.objects.create(
            company=self.company,
            first_name='Safe', last_name='User',
            email='nostaff@example.com',
            password_hash=make_password('TestPass1!'),
            email_verification_token=secrets.token_urlsafe(48),
            status=ClientPortalSignupRequest.STATUS_PENDING_APPROVAL,
            email_verified=True,
        )
        erp_user = User.objects.create_user('approver', password='pass')
        signup_service.approve_signup_request(signup, approved_by=erp_user)

        django_user = User.objects.get(username='nostaff@example.com')
        self.assertFalse(django_user.is_staff, 'Le compte client ne doit pas être staff')
        self.assertFalse(django_user.is_superuser, 'Le compte client ne doit pas être superuser')

    def test_approved_user_has_no_erp_permissions(self):
        from apps.portals.services import signup_service
        from django.contrib.auth.hashers import make_password

        signup = ClientPortalSignupRequest.objects.create(
            company=self.company,
            first_name='NoPerm', last_name='User',
            email='noperm@example.com',
            password_hash=make_password('TestPass1!'),
            email_verification_token=secrets.token_urlsafe(48),
            status=ClientPortalSignupRequest.STATUS_PENDING_APPROVAL,
            email_verified=True,
        )
        erp_user = User.objects.create_user('approver2', password='pass')
        signup_service.approve_signup_request(signup, approved_by=erp_user)

        django_user = User.objects.get(username='noperm@example.com')
        self.assertFalse(django_user.user_permissions.exists(), 'Aucune permission ERP')


@STATIC_OVERRIDE
class RegistrationDisabledTest(TestCase):

    def setUp(self):
        self.company = make_company('Disabled SA')
        make_settings(self.company, allow_client_registration=False)

    def test_register_page_shows_error(self):
        response = self.client.get(reverse('client_portal:register'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('error', response.context)

    def test_register_post_blocked(self):
        count_before = ClientPortalSignupRequest.objects.count()
        self.client.post(reverse('client_portal:register'), VALID_POST)
        self.assertEqual(ClientPortalSignupRequest.objects.count(), count_before)
