from django.urls import path

from apps.user_security import views, api

app_name = "user_security"

urlpatterns = [
    path("account/security/", views.account_security_view, name="account_security"),
    path("account/security/2fa/setup/", views.two_factor_setup_view, name="two_factor_setup"),
    path("account/security/2fa/recovery-codes/", views.recovery_codes_view, name="recovery_codes"),
    path("auth/2fa/verify/", views.two_factor_verify_view, name="two_factor_verify"),
    path("auth/2fa/recovery/", views.two_factor_recovery_verify_view, name="two_factor_recovery"),
    path("api/v1/account/2fa/status/", api.two_factor_status_api, name="api_2fa_status"),
]
