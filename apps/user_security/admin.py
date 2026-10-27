from django.contrib import admin

from apps.user_security.models import (
    SecurityEvent,
    TrustedDevice,
    UserRecoveryCode,
    UserTwoFactorSettings,
)


@admin.register(UserTwoFactorSettings)
class UserTwoFactorSettingsAdmin(admin.ModelAdmin):
    list_display = ["user", "is_enabled", "confirmed_at", "last_verified_at"]
    list_filter = ["is_enabled"]
    search_fields = ["user__username", "user__email"]


@admin.register(UserRecoveryCode)
class UserRecoveryCodeAdmin(admin.ModelAdmin):
    list_display = ["user", "used_at", "created_at"]
    list_filter = ["used_at"]
    search_fields = ["user__username", "user__email"]


@admin.register(TrustedDevice)
class TrustedDeviceAdmin(admin.ModelAdmin):
    list_display = ["user", "ip_address", "expires_at", "created_at", "last_used_at"]
    list_filter = ["expires_at"]
    search_fields = ["user__username", "user__email", "ip_address"]


@admin.register(SecurityEvent)
class SecurityEventAdmin(admin.ModelAdmin):
    list_display = ["user", "event", "ip_address", "created_at"]
    list_filter = ["event", "created_at"]
    search_fields = ["user__username", "user__email", "ip_address"]
