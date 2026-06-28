"""
tests/test_private_saas_permissions.py — Tests permissions SaaS privé
"""
from django.test import TestCase
from unittest.mock import patch, MagicMock


class TestCompanyHasModule(TestCase):

    def test_superuser_always_has_access(self):
        """Un superuser a accès à tous les modules."""
        from apps.private_saas.permissions import user_can_access_module
        user = MagicMock(is_authenticated=True, is_superuser=True)
        self.assertTrue(user_can_access_module(user, None, 'crm'))
        self.assertTrue(user_can_access_module(user, None, 'btp'))

    def test_no_company_returns_true(self):
        """Sans entreprise, pas de filtre — retourne True."""
        from apps.private_saas.permissions import company_has_module
        self.assertTrue(company_has_module(None, 'crm'))

    def test_unauthenticated_denied(self):
        """Un utilisateur non authentifié est refusé."""
        from apps.private_saas.permissions import user_can_access_module
        user = MagicMock(is_authenticated=False, is_superuser=False)
        self.assertFalse(user_can_access_module(user, MagicMock(), 'crm'))

    def test_enabled_module_allowed(self):
        """Un module activé est accessible."""
        from apps.private_saas.permissions import company_has_module
        company = MagicMock(pk=1)
        with patch('apps.private_saas.permissions.CompanyModule') as mock_cm:
            mock_cm.objects.filter.return_value.exists.return_value = True
            result = company_has_module(company, 'crm')
            self.assertTrue(result)

    def test_disabled_module_blocked(self):
        """Un module désactivé n'est pas accessible."""
        from apps.private_saas.permissions import company_has_module
        company = MagicMock(pk=1)
        with patch('apps.private_saas.permissions.CompanyModule') as mock_cm:
            mock_cm.objects.filter.return_value.exists.return_value = False
            result = company_has_module(company, 'btp')
            self.assertFalse(result)


class TestFilterNavModules(TestCase):

    def test_superuser_sees_all_modules(self):
        """Un superuser voit tous les modules incluant Super Admin."""
        from apps.private_saas.permissions import filter_nav_modules
        nav = [
            {'id': 'crm', 'label': 'CRM'},
            {'id': 'private_saas', 'label': 'Super Admin', 'super_admin_only': True},
            {'id': 'dashboard', 'label': 'Dashboard'},
        ]
        user = MagicMock(is_superuser=True)
        result = filter_nav_modules(nav, None, user)
        ids = [m['id'] for m in result]
        self.assertIn('private_saas', ids)

    def test_non_superuser_no_super_admin(self):
        """Un utilisateur normal ne voit pas le Super Admin."""
        from apps.private_saas.permissions import filter_nav_modules
        nav = [
            {'id': 'private_saas', 'label': 'Super Admin', 'super_admin_only': True},
            {'id': 'dashboard', 'label': 'Dashboard'},
        ]
        user = MagicMock(is_superuser=False)
        result = filter_nav_modules(nav, None, user)
        ids = [m['id'] for m in result]
        self.assertNotIn('private_saas', ids)
        self.assertIn('dashboard', ids)
