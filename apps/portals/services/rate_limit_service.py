"""
Rate limiting simple basé en base de données pour les inscriptions portail client.

Limites :
  - 5 tentatives par IP par heure
  - 3 tentatives par email par jour
"""
from datetime import timedelta
from django.utils import timezone


_MAX_PER_IP_PER_HOUR = 5
_MAX_PER_EMAIL_PER_DAY = 3


def can_submit_signup(ip_address: str, email: str) -> tuple[bool, str | None]:
    """
    Vérifie si une tentative d'inscription est autorisée.

    Returns:
        (True, None) si autorisé
        (False, message) si bloqué
    """
    from apps.portals.models import ClientPortalSignupAttempt

    hour_ago = timezone.now() - timedelta(hours=1)
    day_ago = timezone.now() - timedelta(days=1)

    ip_count = ClientPortalSignupAttempt.objects.filter(
        ip_address=ip_address,
        created_at__gte=hour_ago,
    ).count()
    if ip_count >= _MAX_PER_IP_PER_HOUR:
        return False, 'Trop de tentatives depuis votre adresse IP. Réessayez dans une heure.'

    if email:
        email_count = ClientPortalSignupAttempt.objects.filter(
            email=email.lower(),
            created_at__gte=day_ago,
        ).count()
        if email_count >= _MAX_PER_EMAIL_PER_DAY:
            return False, 'Trop de tentatives pour cette adresse email. Réessayez demain.'

    return True, None


def record_signup_attempt(ip_address: str, email: str = '') -> None:
    """Enregistre une tentative d'inscription pour le rate limiting."""
    from apps.portals.models import ClientPortalSignupAttempt
    ClientPortalSignupAttempt.objects.create(
        ip_address=ip_address,
        email=email.lower() if email else '',
    )


def cleanup_old_attempts(days: int = 7) -> int:
    """Supprime les tentatives plus vieilles que `days` jours."""
    from apps.portals.models import ClientPortalSignupAttempt
    cutoff = timezone.now() - timedelta(days=days)
    deleted, _ = ClientPortalSignupAttempt.objects.filter(created_at__lt=cutoff).delete()
    return deleted
