"""
Tests : inscription portail client — flux de base.
"""
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from apps.core.models import Company
from apps.portals.models import (
    ClientPortalSettings,
    ClientPortalSignupRequest,
    ClientPortalAccount,
)

STATIC_OVERRIDE = override_settings(
    STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage'
)


def make_company(name='Test SA'):
    return Company.objects.create(name=name, slug=name.lower().replace(' ', '-'), is_active=True)


def make_settings(company, **kwargs):
    defaults = dict(
        allow_client_registration=True,
        registration_requires_approval=True,
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


VALID_POST = {
    'first_name': 'Jean',
    'last_name': 'Dupont',
    'email': 'jean.dupont@example.com',
    'phone': '0600000000',
    'company_name': 'Dupont SARL',
    'password': 'MotDePasseSecurise1!',
    'password_confirm': 'MotDePasseSecurise1!',
    'message': 'Test',
    'accept_terms': 'on',
    'website': '',
}


@STATIC_OVERRIDE
class SignupButtonVisibilityTest(TestCase):

    def setUp(self):
        self.company = make_company()
        self.client = Client()

    def test_register_page_returns_200(self):
        make_settings(self.company, allow_client_registration=True)
        response = self.client.get(reverse('client_portal:register'))
        self.assertEqual(response.status_code, 200)

    def test_register_page_no_error_field(self):
        make_settings(self.company, allow_client_registration=True)
        response = self.client.get(reverse('client_portal:register'))
        self.assertIsNone(response.context.get('error'))


@STATIC_OVERRIDE
class SignupFormValidationTest(TestCase):

    def setUp(self):
        self.company = make_company('FormTest SA')
        make_settings(self.company, allow_client_registration=True,
                      registration_requires_email_verification=False,
                      registration_requires_approval=False,
                      notify_admin_on_registration=False)
        self.client = Client()

    def test_valid_form_creates_signup_request(self):
        count_before = ClientPortalSignupRequest.objects.count()
        response = self.client.post(reverse('client_portal:register'), VALID_POST)
        self.assertEqual(response.status_code, 302)
        self.assertGreater(ClientPortalSignupRequest.objects.count(), count_before)

    def test_missing_required_fields_shows_errors(self):
        bad_data = {**VALID_POST, 'first_name': '', 'email': ''}
        response = self.client.post(reverse('client_portal:register'), bad_data)
        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)
        self.assertTrue(response.context['form'].errors)

    def test_password_mismatch_shows_error(self):
        bad_data = {**VALID_POST, 'password_confirm': 'different'}
        response = self.client.post(reverse('client_portal:register'), bad_data)
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertIn('password_confirm', form.errors)

    def test_short_password_rejected(self):
        bad_data = {**VALID_POST, 'password': 'short', 'password_confirm': 'short'}
        response = self.client.post(reverse('client_portal:register'), bad_data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)

    def test_terms_required(self):
        bad_data = {k: v for k, v in VALID_POST.items() if k != 'accept_terms'}
        response = self.client.post(reverse('client_portal:register'), bad_data)
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertIn('accept_terms', form.errors)

    def test_duplicate_active_email_blocked(self):
        self.client.post(reverse('client_portal:register'), VALID_POST)
        response = self.client.post(reverse('client_portal:register'), VALID_POST)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].non_field_errors())


@STATIC_OVERRIDE
class SignupSuccessPageTest(TestCase):

    def test_success_page_renders(self):
        response = self.client.get(reverse('client_portal:register_success'))
        self.assertEqual(response.status_code, 200)
