"""
smart_alerts/services.py
Service centralisé de création et gestion des alertes Orion ERP.
"""
from django.utils import timezone
from .models import SmartAlert


def create_alert(
    company, title, source_module, *,
    message='', priority='normal', brand_key='',
    related_object_type='', related_object_id='',
    assigned_to=None, metadata=None,
):
    """Crée une alerte. Évite les doublons actifs sur le même objet."""
    if related_object_type and related_object_id:
        existing = SmartAlert.objects.filter(
            company=company,
            source_module=source_module,
            related_object_type=related_object_type,
            related_object_id=str(related_object_id),
            status__in=('open', 'acknowledged'),
        ).first()
        if existing:
            return existing

    return SmartAlert.objects.create(
        company=company,
        brand_key=brand_key,
        title=title,
        message=message,
        source_module=source_module,
        priority=priority,
        related_object_type=related_object_type,
        related_object_id=str(related_object_id) if related_object_id else '',
        assigned_to=assigned_to,
        metadata=metadata or {},
    )


def resolve_alert(alert, user=None):
    alert.status = 'resolved'
    alert.resolved_at = timezone.now()
    alert.resolved_by = user
    alert.save(update_fields=['status', 'resolved_at', 'resolved_by', 'updated_at'])
    return alert


def acknowledge_alert(alert):
    if alert.status == 'open':
        alert.status = 'acknowledged'
        alert.save(update_fields=['status', 'updated_at'])
    return alert


def ignore_alert(alert):
    alert.status = 'ignored'
    alert.save(update_fields=['status', 'updated_at'])
    return alert


def get_open_alerts(company, *, priority=None, source_module=None, brand_key=None):
    qs = SmartAlert.objects.filter(company=company, status__in=('open', 'acknowledged'))
    if priority:
        qs = qs.filter(priority=priority)
    if source_module:
        qs = qs.filter(source_module=source_module)
    if brand_key:
        qs = qs.filter(brand_key=brand_key)
    return qs.select_related('assigned_to').order_by('-priority', '-created_at')


def get_critical_alerts(company):
    return SmartAlert.objects.filter(
        company=company, priority='critical', status__in=('open', 'acknowledged')
    ).order_by('-created_at')


def get_alert_stats(company):
    qs = SmartAlert.objects.filter(company=company)
    return {
        'total_open': qs.filter(status='open').count(),
        'critical': qs.filter(status='open', priority='critical').count(),
        'high': qs.filter(status='open', priority='high').count(),
        'total_resolved_today': qs.filter(
            status='resolved', resolved_at__date=timezone.now().date()
        ).count(),
    }
