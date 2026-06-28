from django.db.models import Q, Count, Prefetch
from django.utils import timezone

from .models import PDCACycle, PDCAAction, PDCAKPI, PDCAStandard, PDCATemplate, PDCAEventLog


def get_cycles_for_company(company, brand_key=None, stage=None, status=None, category=None, priority=None):
    qs = PDCACycle.objects.filter(company=company)
    if brand_key:
        qs = qs.filter(brand_key=brand_key)
    if stage:
        qs = qs.filter(stage=stage)
    if status:
        qs = qs.filter(status=status)
    if category:
        qs = qs.filter(category=category)
    if priority:
        qs = qs.filter(priority=priority)
    return qs.select_related('owner', 'created_by').order_by('-created_at')


def get_active_cycles(company, brand_key=None):
    return get_cycles_for_company(company, brand_key=brand_key, status='active')


def get_late_cycles(company):
    return PDCACycle.objects.filter(
        company=company,
        target_date__lt=timezone.now().date(),
        status='active',
    ).select_related('owner')


def get_cycle_detail(pk, company):
    return (
        PDCACycle.objects
        .filter(pk=pk, company=company)
        .select_related('owner', 'created_by', 'parent_cycle')
        .prefetch_related(
            Prefetch('actions', queryset=PDCAAction.objects.order_by('order', 'due_date')),
            Prefetch('kpis', queryset=PDCAKPI.objects.all()),
            Prefetch('event_logs', queryset=PDCAEventLog.objects.order_by('-created_at')[:20]),
            'standards',
        )
        .first()
    )


def get_cycles_for_user(user, company=None):
    qs = PDCACycle.objects.filter(
        Q(owner=user) | Q(created_by=user)
    )
    if company:
        qs = qs.filter(company=company)
    return qs.exclude(status='cancelled').order_by('-updated_at')


def get_pending_actions_for_user(user, company=None):
    qs = PDCAAction.objects.filter(
        assigned_to=user,
        status__in=('todo', 'in_progress'),
    )
    if company:
        qs = qs.filter(cycle__company=company)
    return qs.select_related('cycle').order_by('due_date')


def get_overdue_actions(company):
    return PDCAAction.objects.filter(
        cycle__company=company,
        due_date__lt=timezone.now().date(),
        status__in=('todo', 'in_progress'),
    ).select_related('cycle', 'assigned_to').order_by('due_date')


def get_company_kpis_summary(company):
    return PDCAKPI.objects.filter(cycle__company=company).select_related('cycle')


def get_standards_for_company(company, brand_key=None, module=None):
    qs = PDCAStandard.objects.filter(company=company, is_active=True)
    if brand_key:
        qs = qs.filter(brand_key=brand_key)
    if module:
        qs = qs.filter(module=module)
    return qs.select_related('cycle', 'created_by').order_by('-created_at')


def get_active_templates(category=None):
    qs = PDCATemplate.objects.filter(is_active=True)
    if category:
        qs = qs.filter(category=category)
    return qs.order_by('category', 'title')


def get_dashboard_stats(company):
    total = PDCACycle.objects.filter(company=company)
    active = total.filter(status='active')
    late = total.filter(status='active', target_date__lt=timezone.now().date())
    completed = total.filter(status='completed')
    pending_actions = PDCAAction.objects.filter(
        cycle__company=company, status__in=('todo', 'in_progress')
    )
    return {
        'total_cycles': total.count(),
        'active_cycles': active.count(),
        'late_cycles': late.count(),
        'completed_cycles': completed.count(),
        'pending_actions': pending_actions.count(),
        'stages': {
            stage: active.filter(stage=stage).count()
            for stage in ('plan', 'do', 'check', 'act')
        },
    }
