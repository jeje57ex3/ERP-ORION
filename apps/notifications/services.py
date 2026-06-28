"""
apps/notifications/services.py — Fonctions utilitaires pour les notifications ERP
"""
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()


def create_notification(
    user,
    title,
    message='',
    notification_type='info',
    company=None,
    link_url='',
    link_label='',
    priority='normal',
    source_module='',
    source_model='',
    source_id=None,
    icon='bi-bell',
    icon_color='primary',
):
    """
    Crée et persiste une notification pour un utilisateur.

    Returns:
        Notification instance
    """
    from apps.notifications.models import Notification
    return Notification.objects.create(
        user=user,
        company=company,
        title=title,
        message=message,
        notification_type=notification_type,
        priority=priority,
        link_url=link_url,
        link_label=link_label,
        source_module=source_module,
        source_model=source_model,
        source_id=source_id,
        icon=icon,
        icon_color=icon_color,
    )


def notify_user(
    user,
    title,
    message='',
    notification_type='info',
    company=None,
    link_url='',
    link_label='',
    priority='normal',
    source_module='',
    source_model='',
    source_id=None,
    icon='bi-bell',
    icon_color='primary',
):
    """Alias de create_notification pour un utilisateur unique."""
    return create_notification(
        user=user,
        title=title,
        message=message,
        notification_type=notification_type,
        company=company,
        link_url=link_url,
        link_label=link_label,
        priority=priority,
        source_module=source_module,
        source_model=source_model,
        source_id=source_id,
        icon=icon,
        icon_color=icon_color,
    )


def notify_company(
    company,
    title,
    message='',
    notification_type='info',
    link_url='',
    link_label='',
    priority='normal',
    source_module='',
    source_model='',
    source_id=None,
    icon='bi-bell',
    icon_color='primary',
    exclude_user=None,
):
    """
    Envoie une notification à tous les utilisateurs actifs d'une entreprise.

    Args:
        company: instance Company
        exclude_user: optionnel, exclure cet utilisateur de la diffusion

    Returns:
        list[Notification]
    """
    from apps.notifications.models import Notification
    from django.contrib.auth.models import User

    # Cherche les users liés à cette entreprise via UserProfile ou CompanyAccess
    try:
        from apps.accounts.models import UserProfile
        user_ids = UserProfile.objects.filter(
            company=company, user__is_active=True
        ).values_list('user_id', flat=True)
        users = User.objects.filter(id__in=user_ids)
    except Exception:
        # Fallback : tous les users actifs
        users = User.objects.filter(is_active=True)

    if exclude_user:
        users = users.exclude(pk=exclude_user.pk)

    notifications = []
    for user in users:
        notif = Notification.objects.create(
            user=user,
            company=company,
            title=title,
            message=message,
            notification_type=notification_type,
            priority=priority,
            link_url=link_url,
            link_label=link_label,
            source_module=source_module,
            source_model=source_model,
            source_id=source_id,
            icon=icon,
            icon_color=icon_color,
        )
        notifications.append(notif)
    return notifications


def mark_all_read(user, company=None):
    """
    Marque toutes les notifications non lues de l'utilisateur comme lues.

    Args:
        user: User instance
        company: optionnel, limiter à une entreprise

    Returns:
        int — nombre de notifications mises à jour
    """
    from apps.notifications.models import Notification
    qs = Notification.objects.filter(user=user, is_read=False)
    if company is not None:
        qs = qs.filter(company=company)
    return qs.update(is_read=True, read_at=timezone.now())


def get_unread_count(user, company=None):
    """
    Retourne le nombre de notifications non lues pour l'utilisateur.

    Args:
        user: User instance
        company: optionnel, limiter à une entreprise

    Returns:
        int
    """
    from apps.notifications.models import Notification
    qs = Notification.objects.filter(user=user, is_read=False)
    if company is not None:
        qs = qs.filter(company=company)
    return qs.count()


def get_recent_notifications(user, company=None, limit=10):
    """
    Retourne les notifications récentes de l'utilisateur.

    Args:
        user: User instance
        company: optionnel, limiter à une entreprise
        limit: nombre max de résultats (défaut 10)

    Returns:
        QuerySet[Notification]
    """
    from apps.notifications.models import Notification
    qs = Notification.objects.filter(user=user)
    if company is not None:
        qs = qs.filter(company=company)
    return qs.order_by('-created_at')[:limit]


def cleanup_old_notifications(days=90):
    """
    Supprime les notifications lues plus vieilles que `days` jours.

    Args:
        days: âge en jours au-delà duquel supprimer (défaut 90)

    Returns:
        int — nombre de notifications supprimées
    """
    from apps.notifications.models import Notification
    cutoff = timezone.now() - timezone.timedelta(days=days)
    deleted, _ = Notification.objects.filter(is_read=True, created_at__lt=cutoff).delete()
    return deleted
