from django.utils import timezone
from .models import QualityIncident, QualityIncidentComment
from apps.smart_alerts.services import create_alert


def create_incident(company, title, incident_type, *, severity='normal', brand_key='',
                    customer=None, assigned_to=None, description='', due_at=None,
                    created_by=None):
    incident = QualityIncident.objects.create(
        company=company, brand_key=brand_key, title=title,
        incident_type=incident_type, severity=severity,
        customer=customer, assigned_to=assigned_to,
        description=description, due_at=due_at, created_by=created_by,
    )
    if severity in ('critical', 'high'):
        create_alert(
            company, f'Incident qualité : {title}',
            source_module='quality_incidents',
            priority='critical' if severity == 'critical' else 'high',
            brand_key=brand_key,
            related_object_type='QualityIncident',
            related_object_id=str(incident.pk),
        )
    return incident


def resolve_incident(incident, corrective_action='', user=None, comment=''):
    incident.status = 'resolved'
    incident.resolved_at = timezone.now()
    if corrective_action:
        incident.corrective_action = corrective_action
    incident.save(update_fields=['status', 'resolved_at', 'corrective_action', 'updated_at'])
    if comment and user:
        add_comment(incident, user, comment)
    return incident


def add_comment(incident, user, content):
    return QualityIncidentComment.objects.create(
        incident=incident, user=user, content=content,
    )


def get_open_incidents(company, *, severity=None, incident_type=None, brand_key=None):
    qs = QualityIncident.objects.filter(
        company=company, status__in=('open', 'in_progress')
    ).select_related('customer', 'assigned_to')
    if severity:
        qs = qs.filter(severity=severity)
    if incident_type:
        qs = qs.filter(incident_type=incident_type)
    if brand_key:
        qs = qs.filter(brand_key=brand_key)
    return qs.order_by('-severity', '-created_at')


def get_incident_stats(company):
    qs = QualityIncident.objects.filter(company=company)
    return {
        'open': qs.filter(status='open').count(),
        'critical': qs.filter(status='open', severity='critical').count(),
        'in_progress': qs.filter(status='in_progress').count(),
        'resolved_this_month': qs.filter(
            status='resolved',
            resolved_at__year=timezone.now().year,
            resolved_at__month=timezone.now().month,
        ).count(),
    }
