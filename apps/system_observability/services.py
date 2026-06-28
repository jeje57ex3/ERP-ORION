from django.utils import timezone
from .models import SystemHealthCheck, SystemObservabilityAlert


def record_health_check(company, check_type, status, *, message='',
                        response_time_ms=None, metadata=None):
    return SystemHealthCheck.objects.create(
        company=company, check_type=check_type, status=status,
        message=message, response_time_ms=response_time_ms,
        metadata=metadata or {},
    )


def get_latest_health_checks(company):
    """Returns the most recent check per check_type."""
    from django.db.models import Max
    latest_ids = (
        SystemHealthCheck.objects.filter(company=company)
        .values('check_type')
        .annotate(latest_id=Max('id'))
        .values_list('latest_id', flat=True)
    )
    return SystemHealthCheck.objects.filter(
        pk__in=latest_ids
    ).order_by('check_type')


def get_health_status(company):
    checks = list(get_latest_health_checks(company))
    if not checks:
        return 'unknown'
    statuses = {c.status for c in checks}
    if 'critical' in statuses:
        return 'critical'
    if 'warning' in statuses:
        return 'warning'
    if all(c.status == 'ok' for c in checks):
        return 'ok'
    return 'unknown'


def create_system_alert(company, alert_type, severity, title, message, metadata=None):
    return SystemObservabilityAlert.objects.create(
        company=company, alert_type=alert_type, severity=severity,
        title=title, message=message, metadata=metadata or {},
    )


def acknowledge_system_alert(alert, user):
    alert.is_acknowledged = True
    alert.acknowledged_by = user
    alert.acknowledged_at = timezone.now()
    alert.save(update_fields=['is_acknowledged', 'acknowledged_by', 'acknowledged_at'])
    return alert


def get_system_alerts(company, *, severity=None, include_acknowledged=False):
    qs = SystemObservabilityAlert.objects.filter(company=company)
    if not include_acknowledged:
        qs = qs.filter(is_acknowledged=False)
    if severity:
        qs = qs.filter(severity=severity)
    return qs.order_by('-created_at')


def get_check_history(company, check_type, limit=50):
    return SystemHealthCheck.objects.filter(
        company=company, check_type=check_type
    ).order_by('-checked_at')[:limit]


def get_observability_stats(company):
    checks = list(get_latest_health_checks(company))
    alerts = SystemObservabilityAlert.objects.filter(company=company)
    return {
        'overall_status': get_health_status(company),
        'checks_ok': sum(1 for c in checks if c.status == 'ok'),
        'checks_warning': sum(1 for c in checks if c.status == 'warning'),
        'checks_critical': sum(1 for c in checks if c.status == 'critical'),
        'unacknowledged_alerts': alerts.filter(is_acknowledged=False).count(),
        'critical_alerts': alerts.filter(severity='critical', is_acknowledged=False).count(),
    }
