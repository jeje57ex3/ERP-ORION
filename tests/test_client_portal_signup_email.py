"""
Tests : vérification email lors de l'inscription.
"""
import secrets
from django.test import TestCase, override_settings
from django.urls import reverse
from django.core import mail
from apps.core.models import Company
from apps.portals.models import ClientPortalSettings, ClientPortalSignupRequest
from apps.portals.services import signup_service

STATIC_OVERRIDE = override_settings(
    STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage'
)


def make_company(name='EmailTest SA'):
    return Company.objects.create(name=name, slug=name.lower().replace(' ', '-'), is_active=True)


def make_settings(company, **kwargs):
    defaults = dict(
        allow_client_registration=True,
        registration_requires_approval=False,
        registration_requires_email_verification=True,
        allow_unknown_clients=True,
        notify_admin_on_registration=False,
    )
    defaults.update(kwargs)
    obj, _ = ClientPortalSettings.objects.get_or_create(company=company)
    for k, v in defaults.items():
        setattr(obj, k, v)
    obj.save()
    return obj


def make_signup_request(company, email='client@example.com', status=None):
    token = secrets.token_urlsafe(48)
    return ClientPortalSignupRequest.objects.create(
        company=company,
        first_name='Test',
        last_name='User',
        email=email,
        password_hash='hashed',
        email_verification_token=token,
        status=status or ClientPortalSignupRequest.STATUS_PENDING_EMAIL,
    )


class EmailVerificationSendTest(TestCase):

    def setUp(self):
        self.company = make_company()

    def test_send_verification_updates_sent_at(self):
        signup = make_signup_request(self.company)
        signup_service.send_email_verification(signup, base_url='http://testserver')
        signup.refresh_from_db()
        self.assertIsNotNone(signup.email_verification_sent_at)

    def test_send_verification_sends_email(self):
        signup = make_signup_request(self.company)
        signup_service.send_email_verification(signup, base_url='http://testserver')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(signup.email, mail.outbox[0].recipients())


@STATIC_OVERRIDE
class EmailVerificationViewTest(TestCase):

    def setUp(self):
        self.company = make_company('VerifyTest SA')
        make_settings(self.company, registration_requires_approval=True)

    def test_valid_token_verifies_email(self):
        signup = make_signup_request(self.company)
        url = reverse('client_portal:verify_email', kwargs={'token': signup.email_verification_token})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['success'])
        signup.refresh_from_db()
        self.assertTrue(signup.email_verified)

    def test_valid_token_sets_pending_approval(self):
        signup = make_signup_request(self.company)
        self.client.get(reverse('client_portal:verify_email', kwargs={'token': signup.email_verification_token}))
        signup.refresh_from_db()
        self.assertEqual(signup.status, ClientPortalSignupRequest.STATUS_PENDING_APPROVAL)

    def test_invalid_token_shows_error(self):
        response = self.client.get(reverse('client_portal:verify_email', kwargs={'token': 'invalid-token-xyz'}))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['success'])

    def test_already_used_token_shows_error(self):
        signup = make_signup_request(self.company)
        token = signup.email_verification_token
        self.client.get(reverse('client_portal:verify_email', kwargs={'token': token}))
        response = self.client.get(reverse('client_portal:verify_email', kwargs={'token': token}))
        self.assertFalse(response.context['success'])

    def test_verify_without_approval_creates_account(self):
        """Si approval=False, la vérification email crée immédiatement le compte."""
        make_settings(self.company, registration_requires_approval=False,
                      registration_requires_email_verification=True)
        signup = make_signup_request(self.company, email='noapproval@example.com')
        from django.contrib.auth.hashers import make_password
        signup.password_hash = make_password('testpass123')
        signup.save(update_fields=['password_hash'])
        self.client.get(reverse('client_portal:verify_email', kwargs={'token': signup.email_verification_token}))
        signup.refresh_from_db()
        self.assertEqual(signup.status, ClientPortalSignupRequest.STATUS_CONVERTED)
