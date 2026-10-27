import pyotp

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.user_security.models import UserRecoveryCode
from apps.user_security.services import (
    enable_2fa,
    get_or_create_2fa_settings,
    start_2fa_setup,
    user_has_2fa_enabled,
)


class UserTwoFactorTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="test2fa",
            email="test2fa@example.com",
            password="Password123!",
        )

    def test_security_page_requires_login(self):
        response = self.client.get(reverse("user_security:account_security"))
        self.assertNotEqual(response.status_code, 200)

    def test_start_2fa_setup_creates_secret(self):
        settings_obj = start_2fa_setup(self.user)
        self.assertTrue(settings_obj.totp_secret)

    def test_enable_2fa_with_valid_code(self):
        settings_obj = start_2fa_setup(self.user)
        code = pyotp.TOTP(settings_obj.totp_secret).now()
        success, codes = enable_2fa(self.user, code)
        self.assertTrue(success)
        self.user.refresh_from_db()  # vide le cache de relation Django
        self.assertTrue(user_has_2fa_enabled(self.user))
        self.assertEqual(len(codes), 10)
        self.assertEqual(UserRecoveryCode.objects.filter(user=self.user).count(), 10)

    def test_enable_2fa_with_invalid_code_fails(self):
        start_2fa_setup(self.user)
        success, codes = enable_2fa(self.user, "000000")
        self.assertFalse(success)
        self.assertFalse(user_has_2fa_enabled(self.user))
        self.assertEqual(codes, [])
