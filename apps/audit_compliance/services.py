"""
audit_compliance/services.py
Couche service sur core.AuditLog pour l'interface de conformité.
"""
import csv
import io
from apps.core.models import AuditLog


SENSITIVE_ACTIONS = {
    'delete', 'permission_change', 'db_create', 'db_delete',
    'db_backup', 'export', 'payment', 'validate',
}


def get_audit_logs(company, *, action=None, module=None, user=None, date_from=None, date_to=None, limit=500):
    qs = AuditLog.objects.filter(company=company).select_related('user', 'company')
    if action:
        qs = qs.filter(action=action)
    if module:
        qs = qs.filter(module=module)
    if user:
        qs = qs.filter(user=user)
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)
    return qs.order_by('-created_at')[:limit]


def get_sensitive_logs(company, limit=100):
    return AuditLog.objects.filter(
        company=company, action__in=SENSITIVE_ACTIONS
    ).select_related('user').order_by('-created_at')[:limit]


def get_audit_stats(company):
    from django.utils import timezone
    today = timezone.now().date()
    qs = AuditLog.objects.filter(company=company)
    return {
        'total': qs.count(),
        'today': qs.filter(created_at__date=today).count(),
        'sensitive_today': qs.filter(created_at__date=today, action__in=SENSITIVE_ACTIONS).count(),
        'top_modules': list(
            qs.values('module').annotate(count=__import__('django.db.models', fromlist=['Count']).Count('id'))
            .order_by('-count')[:5]
        ),
    }


def export_audit_csv(company, queryset=None):
    if queryset is None:
        queryset = AuditLog.objects.filter(company=company).select_related('user').order_by('-created_at')[:1000]
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Utilisateur', 'Action', 'Module', 'Modèle', 'ID', 'Description', 'IP'])
    for log in queryset:
        writer.writerow([
            log.created_at.strftime('%d/%m/%Y %H:%M:%S'),
            log.user.username if log.user else '—',
            log.get_action_display(),
            log.module,
            log.model_name,
            log.object_id,
            log.description,
            log.ip_address or '',
        ])
    return output.getvalue()
