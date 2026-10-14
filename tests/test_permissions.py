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
        # Une entreprise doit exister, et c'est le coeur de ces tests.
        #
        # Tant qu'aucune entreprise n'est creee, SetupRequiredMiddleware
        # redirige TOUTE requete vers /setup/ : c'est voulu en production --
        # une appliance neuve montre son assistant de premier acces. Ces
        # tests recevaient donc « /setup/ » et non « /accounts/login/ ».
        #
        # Ils ne passaient que lorsqu'un test precedent avait cree une
        # entreprise : l'intergiciel garde son etat dans une variable de
        # MODULE, et « installation terminee » reste vrai pour tout le
        # processus pytest. Selon l'ordre d'execution, ces sept tests
        # passaient ou echouaient -- sans que le code teste ait change.
        from apps.core.models import Company
        Company.objects.create(name='Permissions SA', slug='permissions-sa')

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

    def test_api_erp_requires_auth(self):
        """Un point d'entree API de l'ERP refuse un anonyme.

        Ce test interrogeait « /api/v1/ », qui n'existe pas : il recevait 404,
        et aurait continue de le recevoir meme si toute l'API devenait
        publique. Il faut viser une route reelle -- et une route de l'ERP, car
        « /api/v1/ » heberge surtout des points PUBLICS de boutique
        (catalogue, panier), qui n'exigent justement aucune authentification.
        """
        resp = self.client.post('/api/v1/orion-ai/chat/', {})
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
