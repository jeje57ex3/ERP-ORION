from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render

from apps.user_security.forms import DisableTwoFactorForm, RecoveryCodeForm, TwoFactorCodeForm
from apps.user_security.models import SecurityEvent, UserRecoveryCode
from apps.user_security.services import (
    TWO_FACTOR_PENDING_USER_KEY,
    clear_trusted_device_cookie,
    disable_2fa,
    enable_2fa,
    generate_qr_code_base64,
    generate_recovery_codes_for_user,
    get_or_create_2fa_settings,
    get_totp_uri,
    is_2fa_verified,
    is_trusted_device,
    log_security_event,
    mark_2fa_verified,
    set_trusted_device_cookie,
    start_2fa_setup,
    user_has_2fa_enabled,
    verify_recovery_code,
    verify_totp_code,
)


@login_required
def account_security_view(request):
    settings_obj = get_or_create_2fa_settings(request.user)
    recovery_codes_count = UserRecoveryCode.objects.filter(
        user=request.user, used_at__isnull=True
    ).count()
    recent_events = SecurityEvent.objects.filter(user=request.user)[:20]
    disable_form = DisableTwoFactorForm()

    if request.method == "POST" and request.POST.get("action") == "disable_2fa":
        disable_form = DisableTwoFactorForm(request.POST)
        if disable_form.is_valid():
            success = disable_2fa(
                request.user, disable_form.cleaned_data["password"], request
            )
            if success:
                messages.success(request, "Double authentification désactivée.")
                response = redirect("user_security:account_security")
                clear_trusted_device_cookie(response)
                return response
            messages.error(request, "Mot de passe incorrect.")

    return render(request, "user_security/account_security.html", {
        "page_title": "Sécurité du compte",
        "two_factor": settings_obj,
        "is_2fa_enabled": settings_obj.is_enabled,
        "recovery_codes_count": recovery_codes_count,
        "recent_events": recent_events,
        "disable_form": disable_form,
    })


@login_required
def two_factor_setup_view(request):
    settings_obj = start_2fa_setup(request.user, request)
    uri = get_totp_uri(request.user, settings_obj.totp_secret)
    qr_code = generate_qr_code_base64(uri)
    form = TwoFactorCodeForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        success, plain_codes = enable_2fa(
            request.user, form.cleaned_data["code"], request
        )
        if success:
            request.session["new_recovery_codes"] = plain_codes
            mark_2fa_verified(request, request.user)
            messages.success(request, "Double authentification activée.")
            return redirect("user_security:recovery_codes")
        messages.error(request, "Code invalide. Vérifiez votre application Authenticator.")

    return render(request, "user_security/two_factor_setup.html", {
        "page_title": "Activer la double authentification",
        "form": form,
        "qr_code": qr_code,
        "secret": settings_obj.totp_secret,
    })


@login_required
def recovery_codes_view(request):
    codes = request.session.pop("new_recovery_codes", None)

    if request.method == "POST":
        codes = generate_recovery_codes_for_user(request.user)
        request.session["new_recovery_codes"] = codes
        log_security_event(request.user, "recovery_codes_regenerated", request)
        return redirect("user_security:recovery_codes")

    return render(request, "user_security/recovery_codes.html", {
        "page_title": "Codes de récupération",
        "codes": codes,
        "remaining_count": UserRecoveryCode.objects.filter(
            user=request.user, used_at__isnull=True
        ).count(),
    })


def two_factor_verify_view(request):
    pending_user_id = request.session.get(TWO_FACTOR_PENDING_USER_KEY)

    if not pending_user_id:
        if request.user.is_authenticated:
            return redirect("core:dashboard")
        return redirect("accounts:login")

    User = get_user_model()
    try:
        user = User.objects.get(id=pending_user_id)
    except User.DoesNotExist:
        raise Http404

    if is_trusted_device(request, user):
        login(request, user)
        mark_2fa_verified(request, user)
        return redirect("core:dashboard")

    form = TwoFactorCodeForm(request.POST or None)
    recovery_form = RecoveryCodeForm()

    if request.method == "POST" and form.is_valid():
        settings_obj = get_or_create_2fa_settings(user)
        success = False
        if settings_obj.is_enabled and settings_obj.totp_secret:
            success = verify_totp_code(settings_obj.totp_secret, form.cleaned_data["code"])

        if success:
            login(request, user)
            mark_2fa_verified(request, user)
            response = redirect(request.GET.get("next") or "core:dashboard")
            if form.cleaned_data.get("remember_device"):
                set_trusted_device_cookie(response, request, user)
            return response

        log_security_event(user, "2fa_failed", request)
        messages.error(request, "Code 2FA invalide.")

    return render(request, "user_security/two_factor_verify.html", {
        "form": form,
        "recovery_form": recovery_form,
        "user_for_2fa": user,
    })


def two_factor_recovery_verify_view(request):
    pending_user_id = request.session.get(TWO_FACTOR_PENDING_USER_KEY)
    if not pending_user_id:
        return redirect("accounts:login")

    User = get_user_model()
    user = User.objects.filter(id=pending_user_id).first()
    if not user:
        return redirect("accounts:login")

    form = RecoveryCodeForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        success = verify_recovery_code(
            user, form.cleaned_data["recovery_code"], request
        )
        if success:
            login(request, user)
            mark_2fa_verified(request, user)
            messages.warning(request, "Code de récupération utilisé. Pensez à régénérer vos codes.")
            return redirect("user_security:account_security")
        messages.error(request, "Code de récupération invalide.")

    return render(request, "user_security/two_factor_verify.html", {
        "form": TwoFactorCodeForm(),
        "recovery_form": form,
        "user_for_2fa": user,
        "show_recovery": True,
    })
