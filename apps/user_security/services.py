import base64
import hashlib
import io
import secrets

import pyotp
import qrcode

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone
from django.utils.http import urlsafe_base64_encode

from apps.user_security.models import (
    SecurityEvent,
    TrustedDevice,
    UserRecoveryCode,
    UserTwoFactorSettings,
    generate_recovery_code,
)


TWO_FACTOR_SESSION_KEY = "orion_2fa_verified"
TWO_FACTOR_PENDING_USER_KEY = "orion_2fa_pending_user_id"
TRUSTED_DEVICE_COOKIE = "orion_trusted_device"


def get_client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def log_security_event(user, event, request=None, metadata=None):
    SecurityEvent.objects.create(
        user=user,
        event=event,
        ip_address=get_client_ip(request) if request else None,
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:500] if request else "",
        metadata=metadata or {},
    )


def get_or_create_2fa_settings(user):
    obj, _ = UserTwoFactorSettings.objects.get_or_create(user=user)
    return obj


def _refleter_sur_le_profil(user, actif):
    """Recopie l'etat de la 2FA dans accounts.UserProfile.two_factor_enabled.

    Ce champ existe depuis la premiere migration de accounts et n'est lu
    NULLE PART -- ni formulaire, ni gabarit, ni admin, ni vue. C'est donc
    un champ mort, pas une case a cocher qui mentirait a l'utilisateur.

    Mais un champ mort qui s'appelle « 2FA active » est un piege pour qui
    le lira un jour : il resterait a False sur un compte reellement
    protege. La seule source de verite est UserTwoFactorSettings ; ce
    champ en devient un reflet, et ne peut plus le contredire.

    Silencieux en cas d'absence de profil : un User sans UserProfile
    existe, et refuser d'activer la 2FA pour cette raison serait absurde.
    """
    profil = getattr(user, "profile", None)
    if profil is None:
        return
    if profil.two_factor_enabled != actif:
        profil.two_factor_enabled = actif
        profil.save(update_fields=["two_factor_enabled"])


def user_has_2fa_enabled(user):
    if not user or not user.is_authenticated:
        return False
    try:
        return bool(user.two_factor_settings.is_enabled)
    except UserTwoFactorSettings.DoesNotExist:
        return False


def user_requires_2fa(user):
    if not user or not user.is_authenticated:
        return False
    if user_has_2fa_enabled(user):
        return True
    if getattr(settings, "ORION_2FA_REQUIRED_FOR_SUPERUSERS", True) and user.is_superuser:
        return True
    return False


def generate_totp_secret():
    return pyotp.random_base32()


def start_2fa_setup(user, request=None):
    settings_obj = get_or_create_2fa_settings(user)
    if not settings_obj.totp_secret:
        settings_obj.totp_secret = generate_totp_secret()
        settings_obj.save(update_fields=["totp_secret", "updated_at"])
    log_security_event(user, "2fa_setup_started", request)
    return settings_obj


def get_totp_uri(user, secret):
    issuer = getattr(settings, "ORION_2FA_ISSUER_NAME", "Orion ERP")
    label = getattr(user, "email", "") or user.get_username()
    return pyotp.TOTP(secret).provisioning_uri(name=label, issuer_name=issuer)


def generate_qr_code_base64(uri):
    image = qrcode.make(uri)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


def verify_totp_code(secret, code):
    code = str(code or "").replace(" ", "").strip()
    if not code:
        return False
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def generate_recovery_codes_for_user(user, count=10):
    UserRecoveryCode.objects.filter(user=user).delete()
    plain_codes = []
    for _ in range(count):
        code = generate_recovery_code()
        plain_codes.append(code)
        UserRecoveryCode.objects.create(user=user, code_hash=make_password(code))
    return plain_codes


def enable_2fa(user, code, request=None):
    settings_obj = get_or_create_2fa_settings(user)
    if not settings_obj.totp_secret:
        return False, []
    if not verify_totp_code(settings_obj.totp_secret, code):
        log_security_event(user, "2fa_failed", request)
        return False, []
    settings_obj.mark_enabled()
    settings_obj.last_verified_at = timezone.now()
    settings_obj.save(update_fields=["last_verified_at", "updated_at"])
    _refleter_sur_le_profil(user, True)
    plain_codes = generate_recovery_codes_for_user(user)
    log_security_event(user, "2fa_enabled", request)
    return True, plain_codes


def disable_2fa(user, password, request=None):
    if not user.check_password(password):
        log_security_event(user, "2fa_failed", request, {"action": "disable"})
        return False
    settings_obj = get_or_create_2fa_settings(user)
    settings_obj.mark_disabled()
    _refleter_sur_le_profil(user, False)
    UserRecoveryCode.objects.filter(user=user).delete()
    TrustedDevice.objects.filter(user=user).delete()
    log_security_event(user, "2fa_disabled", request)
    return True


def mark_2fa_verified(request, user):
    request.session[TWO_FACTOR_SESSION_KEY] = True
    request.session.pop(TWO_FACTOR_PENDING_USER_KEY, None)
    settings_obj = get_or_create_2fa_settings(user)
    settings_obj.last_verified_at = timezone.now()
    settings_obj.save(update_fields=["last_verified_at", "updated_at"])
    log_security_event(user, "2fa_verified", request)


def is_2fa_verified(request):
    return bool(request.session.get(TWO_FACTOR_SESSION_KEY))


def clear_2fa_session(request):
    request.session.pop(TWO_FACTOR_SESSION_KEY, None)
    request.session.pop(TWO_FACTOR_PENDING_USER_KEY, None)


def verify_recovery_code(user, code, request=None):
    code = str(code or "").strip().upper()
    if not code:
        return False
    for rc in UserRecoveryCode.objects.filter(user=user, used_at__isnull=True):
        if check_password(code, rc.code_hash):
            rc.used_at = timezone.now()
            rc.save(update_fields=["used_at"])
            log_security_event(user, "recovery_code_used", request)
            return True
    log_security_event(user, "2fa_failed", request, {"method": "recovery_code"})
    return False


def create_trusted_device(request, user):
    days = getattr(settings, "ORION_2FA_REMEMBER_DEVICE_DAYS", 30)
    raw_token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    TrustedDevice.objects.create(
        user=user,
        token_hash=token_hash,
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
        ip_address=get_client_ip(request),
        expires_at=timezone.now() + timezone.timedelta(days=days),
    )
    log_security_event(user, "trusted_device_added", request)
    return raw_token


def trusted_device_cookie_value(user, raw_token):
    user_part = urlsafe_base64_encode(str(user.id).encode("utf-8"))
    return f"{user_part}:{raw_token}"


def parse_trusted_device_cookie(value):
    if not value or ":" not in value:
        return None, None
    user_part, raw_token = value.split(":", 1)
    try:
        padded = user_part + "=" * (-len(user_part) % 4)
        user_id = base64.urlsafe_b64decode(padded.encode()).decode()
        return int(user_id), raw_token
    except Exception:
        return None, None


def is_trusted_device(request, user):
    cookie = request.COOKIES.get(TRUSTED_DEVICE_COOKIE)
    user_id, raw_token = parse_trusted_device_cookie(cookie)
    if not user_id or user_id != user.id or not raw_token:
        return False
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    device = TrustedDevice.objects.filter(
        user=user, token_hash=token_hash, expires_at__gt=timezone.now()
    ).first()
    if not device:
        return False
    device.last_used_at = timezone.now()
    device.save(update_fields=["last_used_at"])
    return True


def set_trusted_device_cookie(response, request, user):
    raw_token = create_trusted_device(request, user)
    cookie_value = trusted_device_cookie_value(user, raw_token)
    days = getattr(settings, "ORION_2FA_REMEMBER_DEVICE_DAYS", 30)
    response.set_cookie(
        TRUSTED_DEVICE_COOKIE,
        cookie_value,
        max_age=days * 24 * 60 * 60,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="Lax",
    )
    return response


def clear_trusted_device_cookie(response):
    response.delete_cookie(TRUSTED_DEVICE_COOKIE)
    return response
