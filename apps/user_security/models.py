import secrets
import string

from django.conf import settings
from django.db import models
from django.utils import timezone


def generate_recovery_code(length=10):
    alphabet = string.ascii_uppercase + string.digits
    raw = "".join(secrets.choice(alphabet) for _ in range(length))
    return "-".join([raw[:5], raw[5:]])


class UserTwoFactorSettings(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="two_factor_settings",
    )

    is_enabled = models.BooleanField(default=False)
    totp_secret = models.CharField(max_length=64, blank=True)

    confirmed_at = models.DateTimeField(null=True, blank=True)
    disabled_at = models.DateTimeField(null=True, blank=True)
    last_verified_at = models.DateTimeField(null=True, blank=True)
    remember_device_enabled = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def mark_enabled(self):
        self.is_enabled = True
        self.confirmed_at = timezone.now()
        self.disabled_at = None
        self.save(update_fields=["is_enabled", "confirmed_at", "disabled_at", "updated_at"])

    def mark_disabled(self):
        self.is_enabled = False
        self.disabled_at = timezone.now()
        self.save(update_fields=["is_enabled", "disabled_at", "updated_at"])

    def __str__(self):
        return f"2FA — {self.user}"


class UserRecoveryCode(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recovery_codes",
    )
    code_hash = models.CharField(max_length=128)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["user", "used_at"])]

    @property
    def is_used(self):
        return self.used_at is not None


class TrustedDevice(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="trusted_devices",
    )
    token_hash = models.CharField(max_length=128, unique=True)
    user_agent = models.CharField(max_length=500, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["user", "expires_at"])]

    def is_valid(self):
        return self.expires_at > timezone.now()


class SecurityEvent(models.Model):
    EVENT_CHOICES = [
        ("2fa_setup_started", "Activation 2FA commencée"),
        ("2fa_enabled", "2FA activée"),
        ("2fa_disabled", "2FA désactivée"),
        ("2fa_verified", "2FA vérifiée"),
        ("2fa_failed", "Échec 2FA"),
        ("recovery_code_used", "Code de récupération utilisé"),
        ("recovery_codes_regenerated", "Codes de récupération régénérés"),
        ("trusted_device_added", "Appareil de confiance ajouté"),
        ("trusted_device_removed", "Appareil de confiance supprimé"),
        ("login_requires_2fa", "Connexion en attente de 2FA"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="security_events",
    )
    event = models.CharField(max_length=80, choices=EVENT_CHOICES)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "event"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.user} — {self.event}"
