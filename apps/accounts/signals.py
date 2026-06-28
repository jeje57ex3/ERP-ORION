import logging
from django.db.models.signals import post_save
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import UserProfile
from apps.accounts.services.user_employee_link_service import (
    is_user_exempt_from_employee_link,
    get_user_employee,
    create_employee_for_user,
)

logger = logging.getLogger('orion')


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    try:
        instance.profile.save()
    except UserProfile.DoesNotExist:
        UserProfile.objects.create(user=instance)


def _get_ip(request):
    if request is None:
        return 'N/A'
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    return xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR', 'N/A')


@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs):
    ip = _get_ip(request)
    logger.info("Connexion: %s depuis %s", user.username, ip)
    try:
        from apps.core.audit_service import log_login
        log_login(request, user)
    except Exception as e:
        logger.debug("Impossible de journaliser la connexion: %s", e)


@receiver(user_logged_out)
def on_user_logged_out(sender, request, user, **kwargs):
    if user:
        logger.info("Deconnexion: %s depuis %s", user.username, _get_ip(request))
        try:
            from apps.core.audit_service import log_logout
            log_logout(request, user)
        except Exception as e:
            logger.debug("Impossible de journaliser la deconnexion: %s", e)


@receiver(user_login_failed)
def on_user_login_failed(sender, credentials, request, **kwargs):
    username = credentials.get('username', '?')
    logger.warning("Connexion echouee: '%s' depuis %s", username, _get_ip(request))


@receiver(post_save, sender=User)
def auto_create_employee_for_non_admin(sender, instance, created, **kwargs):
    """
    Si un utilisateur non exempté est créé avec une entreprise courante,
    crée automatiquement une fiche salarié minimale.
    """
    if not created:
        return
    if is_user_exempt_from_employee_link(instance):
        return
    if get_user_employee(instance):
        return

    # Entreprise active depuis le profil (renseignée après création du profil)
    try:
        company = instance.profile.current_company
    except Exception:
        company = None

    if not company:
        return  # Pas d'entreprise → pas de création automatique

    try:
        create_employee_for_user(
            user=instance,
            company=company,
            extra_data={
                'first_name': instance.first_name,
                'last_name': instance.last_name,
                'email': instance.email,
            },
        )
        logger.info("Fiche salarié créée automatiquement pour %s", instance.username)
    except Exception as exc:
        logger.warning("Impossible de créer la fiche salarié pour %s : %s", instance.username, exc)
