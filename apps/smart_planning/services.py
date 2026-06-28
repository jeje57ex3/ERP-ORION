from django.utils import timezone
from .models import PlanningEvent, PlanningConflict


def create_event(company, title, event_type, start_at, end_at, *, employee=None,
                 customer=None, project_id='', location='', notes='', created_by=None):
    event = PlanningEvent.objects.create(
        company=company, title=title, event_type=event_type,
        employee=employee, customer=customer, project_id=project_id,
        location=location, start_at=start_at, end_at=end_at,
        notes=notes, created_by=created_by,
    )
    detect_conflicts(event)
    return event


def detect_conflicts(event):
    """Détecte les doubles réservations pour un salarié."""
    conflicts = []
    if not event.employee:
        return conflicts

    overlapping = PlanningEvent.objects.filter(
        company=event.company,
        employee=event.employee,
        start_at__lt=event.end_at,
        end_at__gt=event.start_at,
        status__in=('planned', 'confirmed', 'in_progress'),
    ).exclude(pk=event.pk)

    for other in overlapping:
        conflict = PlanningConflict.objects.create(
            company=event.company,
            event=event,
            conflicting_event=other,
            conflict_type='double_booking',
            message=f'Chevauchement avec « {other.title} » ({other.start_at:%d/%m %H:%M} – {other.end_at:%H:%M})',
            severity='high',
        )
        conflicts.append(conflict)
    return conflicts


def get_events_for_period(company, start_date, end_date, *, employee=None, event_type=None):
    qs = PlanningEvent.objects.filter(
        company=company, start_at__date__gte=start_date, end_at__date__lte=end_date
    ).select_related('employee', 'customer')
    if employee:
        qs = qs.filter(employee=employee)
    if event_type:
        qs = qs.filter(event_type=event_type)
    return qs.order_by('start_at')


def get_conflicts(company):
    return PlanningConflict.objects.filter(
        company=company, is_resolved=False
    ).select_related('event', 'conflicting_event').order_by('-created_at')


def get_planning_stats(company):
    from datetime import timedelta
    today = timezone.now().date()
    week_end = today + timedelta(days=7)
    qs = PlanningEvent.objects.filter(company=company)
    return {
        'this_week': qs.filter(start_at__date__gte=today, start_at__date__lte=week_end).count(),
        'conflicts': PlanningConflict.objects.filter(company=company, is_resolved=False).count(),
        'total': qs.count(),
    }
