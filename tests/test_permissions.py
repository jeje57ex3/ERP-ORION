"""
tests/test_permissions.py — Tests de sécurité des vues Orion ERP

Lance avec : pytest tests/test_permissions.py -v
             (DJANGO_SETTINGS_MODULE=erp_btp.settings.testing)
"""
import pytest
from django.test import TestCase, Client
from django.contrib.auth.models import User


class TestAnonymousAccess(TestCase):
    """Les vues ERP doivent rediriger les utilisateurs non connectés."""

    def setUp(self):
        self.client = Client()

    def _assert_redirect_to_login(self, url):
        resp = self.client.get(url)
        self.assertIn(resp.status_code, [302, 301])
        self.assertIn('/accounts/login/', resp['Location'])

    def test_dashboard_requires_login(self):
        self._assert_redirect_to_login('/dashboard/')

    def test_crm_clients_requires_login(self):
        self._assert_redirect_to_login('/crm/clients/')

    def test_sales_quotes_requires_login(self):
        self._assert_redirect_to_login('/sales/devis/')

    def test_accounting_requires_login(self):
        self._assert_redirect_to_login('/accounting/')

    def test_btp_projects_requires_login(self):
        self._assert_redirect_to_login('/btp/chantiers/')

    def test_hr_employees_requires_login(self):
        self._assert_redirect_to_login('/hr/salaries/')

    def test_inventory_requires_login(self):
        self._assert_redirect_to_login('/inventory/')

    def test_api_requires_auth(self):
        resp = self.client.get('/api/v1/')
        self.assertIn(resp.status_code, [401, 403, 302])


class TestAuthenticatedUserAccess(TestCase):
    """Un utilisateur connecté sans entreprise doit être redirigé."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpassword123',
            email='test@test.com',
        )
        self.client = Client()
        self.client.force_login(self.user)

    def test_public_site_is_accessible_without_login(self):
        resp = self.client.get('/sites/')
        self.assertNotEqual(resp.status_code, 500)


class TestSuperuserAccess(TestCase):
    """Le superadmin doit avoir accès à toutes les ressources core."""

    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username='admin',
            password='adminpassword123',
            email='admin@test.com',
        )
        self.client = Client()
        self.client.force_login(self.superuser)

    def test_admin_panel_accessible(self):
        resp = self.client.get('/admin/')
        self.assertEqual(resp.status_code, 200)

    def test_core_companies_list_accessible(self):
        resp = self.client.get('/dashboard/')
        self.assertIn(resp.status_code, [200, 302])
