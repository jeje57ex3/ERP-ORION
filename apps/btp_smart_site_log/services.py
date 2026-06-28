from django.utils import timezone
from .models import SiteLog, SiteLogIncident


def create_site_log(company, project_id, log_type, title, logged_at=None, *,
                    project_name='', description='', workers_count=0,
                    weather='unknown', temperature_celsius=None,
                    gps_lat=None, gps_lng=None, location_label='',
                    photos=None, progress_percent=0, metadata=None,
                    brand_key='', logged_by=None):
    return SiteLog.objects.create(
        company=company, brand_key=brand_key,
        project_id=project_id, project_name=project_name,
        log_type=log_type, title=title,
        description=description, workers_count=workers_count,
        weather=weather, temperature_celsius=temperature_celsius,
        gps_lat=gps_lat, gps_lng=gps_lng, location_label=location_label,
        photos=photos or [], progress_percent=progress_percent,
        metadata=metadata or {},
        logged_at=logged_at or timezone.now(),
        logged_by=logged_by,
    )


def add_incident(company, site_log, incident_type, severity, description, *,
                 corrective_action=''):
    incident = SiteLogIncident.objects.create(
        company=company, site_log=site_log,
        incident_type=incident_type, severity=severity,
        description=description, corrective_action=corrective_action,
    )
    try:
        from apps.smart_alerts.services import create_alert
        if severity in ('high', 'critical'):
            create_alert(
                company, f'Incident chantier : {site_log.project_id} — {incident_type}',
                source_module='btp_smart_site_log',
                priority='critical' if severity == 'critical' else 'high',
                related_object_type='SiteLogIncident',
                related_object_id=str(incident.pk),
            )
    except Exception:
        pass
    return incident


def resolve_incident(incident, corrective_action=''):
    incident.is_resolved = True
    incident.resolved_at = timezone.now()
    if corrective_action:
        incident.corrective_action = corrective_action
    incident.save(update_fields=['is_resolved', 'resolved_at', 'corrective_action'])
    return incident


def get_site_logs(company, project_id=None, *, log_type=None, date_from=None,
                  date_to=None, limit=50):
    qs = SiteLog.objects.filter(company=company).select_related('logged_by')
    if project_id:
        qs = qs.filter(project_id=project_id)
    if log_type:
        qs = qs.filter(log_type=log_type)
    if date_from:
        qs = qs.filter(logged_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(logged_at__date__lte=date_to)
    return qs.order_by('-logged_at')[:limit]


def get_open_incidents(company, *, severity=None):
    qs = SiteLogIncident.objects.filter(
        company=company, is_resolved=False
    ).select_related('site_log')
    if severity:
        qs = qs.filter(severity=severity)
    return qs.order_by('-created_at')


def get_site_stats(company, project_id=None):
    logs = SiteLog.objects.filter(company=company)
    incidents = SiteLogIncident.objects.filter(company=company)
    if project_id:
        logs = logs.filter(project_id=project_id)
        incidents = incidents.filter(site_log__project_id=project_id)
    from datetime import timedelta
    since_30d = timezone.now() - timedelta(days=30)
    Avg = __import__('django.db.models', fromlist=['Avg']).Avg
    return {
        'total_logs': logs.count(),
        'logs_30d': logs.filter(logged_at__gte=since_30d).count(),
        'open_incidents': incidents.filter(is_resolved=False).count(),
        'resolved_incidents': incidents.filter(is_resolved=True).count(),
        'critical_incidents': incidents.filter(severity='critical', is_resolved=False).count(),
        'avg_workers': logs.aggregate(a=Avg('workers_count'))['a'] or 0,
        'avg_progress': logs.aggregate(a=Avg('progress_percent'))['a'] or 0,
    }
