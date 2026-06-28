"""
tests/test_private_saas_modules.py — Tests gestion modules par entreprise
"""
from django.test import TestCase
from unittest.mock import patch, MagicMock


class TestPrivateSaaSSettings(TestCase):

    def test_settings_singleton(self):
        """PrivateSaaSSettings.get() retourne toujours le même objet."""
        from apps.private_saas.models import PrivateSaaSSettings
        with patch.object(PrivateSaaSSettings.objects, 'get_or_create') as mock_get:
            mock_obj = MagicMock()
            mock_obj.private_mode_enabled = True
            mock_obj.public_signup_enabled = False
            mock_get.return_value = (mock_obj, True)
            result = PrivateSaaSSettings.get()
            self.assertTrue(result.private_mode_enabled)
            self.assertFalse(result.public_signup_enabled)

    def test_private_mode_on_by_default(self):
        """Le mode privé est activé par défaut."""
        from apps.private_saas.models import PrivateSaaSSettings
        s = PrivateSaaSSettings()
        self.assertTrue(s.private_mode_enabled)
        self.assertFalse(s.public_signup_enabled)


class TestCompanyModule(TestCase):

    def test_module_enable(self):
        """enable() active le module et met à jour enabled_at."""
        from apps.private_saas.models import CompanyModule
        from django.utils import timezone
        mod = CompanyModule()
        mod.is_enabled = False
        mod.save = MagicMock()

        user = MagicMock()
        mod.enable(user=user)

        self.assertTrue(mod.is_enabled)
        self.assertIsNotNone(mod.enabled_at)
        self.assertEqual(mod.enabled_by, user)

    def test_module_disable(self):
        """disable() désactive le module."""
        from apps.private_saas.models import CompanyModule
        mod = CompanyModule()
        mod.is_enabled = True
        mod.save = MagicMock()

        mod.disable()
        self.assertFalse(mod.is_enabled)


class TestCompanyBackup(TestCase):

    def test_size_display_bytes(self):
        """size_display retourne l'unité correcte pour les petits fichiers."""
        from apps.private_saas.models import CompanyBackup
        b = CompanyBackup(size=512)
        self.assertEqual(b.size_display, '512 o')

    def test_size_display_ko(self):
        from apps.private_saas.models import CompanyBackup
        b = CompanyBackup(size=2048)
        self.assertIn('Ko', b.size_display)

    def test_size_display_mo(self):
        from apps.private_saas.models import CompanyBackup
        b = CompanyBackup(size=2 * 1024 * 1024)
        self.assertIn('Mo', b.size_display)
