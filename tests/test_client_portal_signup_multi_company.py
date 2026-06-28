"""
Tests : inscription multi-entreprises (isolation des données).
"""
import secrets
from django.test import TestCase
from django.contrib.auth.hashers import make_password
from apps.core.models import Company
from apps.portals.models import (
    ClientPortalSettings,
    ClientPortalSignupRequest,
    ClientPortalAccount,
)
from apps.portals.services import signup_service


def make_company(name):
    return Company.objects.create(name=name, slug=name.lower().replace(' ', '-'))


def make_settings(company, **kwargs):
    defaults = dict(
        allow_client_registration=True,
        registration_requires_approval=False,
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


def make_signup(company, email, status=ClientPortalSignupRequest.STATUS_PENDING_APPROVAL):
    return ClientPortalSignupRequest.objects.create(
        company=company,
        first_name='Multi',
        last_name='Test',
        email=email,
        password_hash=make_password('TestPass123!'),
        email_verification_token=secrets.token_urlsafe(48),
        status=status,
        email_verified=True,
    )


class MultiCompanyIsolationTest(TestCase):

    def setUp(self):
        self.company_a = make_company('Entreprise Alpha')
        self.company_b = make_company('Entreprise Beta')
        make_settings(self.company_a)
        make_settings(self.company_b)

    def test_same_email_different_companies_allowed(self):
        """Un même email peut s'inscrire chez deux entreprises distinctes."""
        email = 'shared@example.com'
        signup_a = make_signup(self.company_a, email)
        # Pas encore de demande pour company_b → doit réussir
        signup_b = make_signup(self.company_b, email)
        self.assertNotEqual(signup_a.pk, signup_b.pk)
        self.assertEqual(ClientPortalSignupRequest.objects.filter(email=email).count(), 2)

    def test_duplicate_email_same_company_blocked(self):
        """Deux demandes actives pour le même email et la même entreprise → erreur."""
        from apps.portals.services.signup_service import create_signup_request
        from unittest.mock import MagicMock

        email = 'dup@example.com'
        make_signup(self.company_a, email)

        request_mock = MagicMock()
        request_mock.META = {'REMOTE_ADDR': '127.0.0.1', 'HTTP_USER_AGENT': ''}

        form_data = {
            'first_name': 'Dup', 'last_name': 'Test',
            'email': email,
            'phone': '', 'company_name': '',
            'password': 'TestPass123!', 'message': '',
        }
        with self.assertRaises(ValueError):
            create_signup_request(self.company_a, form_data, request_mock)

    def test_signup_requests_scoped_to_company(self):
        """Les listes de demandes sont isolées par entreprise."""
        email_a = 'only_a@example.com'
        email_b = 'only_b@example.com'
        make_signup(self.company_a, email_a)
        make_signup(self.company_b, email_b)

        signups_a = ClientPortalSignupRequest.objects.filter(company=self.company_a)
        signups_b = ClientPortalSignupRequest.objects.filter(company=self.company_b)

        self.assertTrue(signups_a.filter(email=email_a).exists())
        self.assertFalse(signups_a.filter(email=email_b).exists())
        self.assertTrue(signups_b.filter(email=email_b).exists())
        self.assertFalse(signups_b.filter(email=email_a).exists())


class PortalSettingsPerCompanyTest(TestCase):

    def setUp(self):
        self.company_a = make_company('Settings Alpha')
        self.company_b = make_company('Settings Beta')

    def test_each_company_has_independent_settings(self):
        settings_a = make_settings(self.company_a, allow_client_registration=True)
        settings_b = make_settings(self.company_b, allow_client_registration=False)

        self.assertTrue(settings_a.allow_client_registration)
        self.assertFalse(settings_b.allow_client_registration)

    def test_get_for_company_creates_defaults(self):
        company = make_company('Auto Settings SA')
        settings = ClientPortalSettings.get_for_company(company)
        self.assertIsNotNone(settings)
        self.assertEqual(settings.company, company)
        # Valeurs par défaut
        self.assertTrue(settings.allow_client_registration)
        self.assertTrue(settings.registration_requires_approval)

    def test_get_for_company_none_returns_none(self):
        result = ClientPortalSettings.get_for_company(None)
        self.assertIsNone(result)


class UnknownClientRestrictionTest(TestCase):

    def setUp(self):
        self.company = make_company('Restricted SA')
        make_settings(
            self.company,
            allow_unknown_clients=False,
            registration_requires_email_verification=False,
            notify_admin_on_registration=False,
        )

    def test_unknown_email_blocked_when_unknown_not_allowed(self):
        from apps.portals.services.signup_service import create_signup_request
        from unittest.mock import MagicMock

        request_mock = MagicMock()
        request_mock.META = {'REMOTE_ADDR': '127.0.0.1', 'HTTP_USER_AGENT': ''}

        form_data = {
            'first_name': 'Unknown', 'last_name': 'Client',
            'email': 'unknown-client@example.com',
            'phone': '', 'company_name': '',
            'password': 'TestPass123!', 'message': '',
        }
        with self.assertRaises(ValueError) as ctx:
            create_signup_request(self.company, form_data, request_mock)
        self.assertIn('dossier client', str(ctx.exception))
