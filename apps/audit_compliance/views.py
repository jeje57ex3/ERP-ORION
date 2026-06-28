from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.core.paginator import Paginator

from apps.core.models import AuditLog
from .services import get_audit_logs, get_sensitive_logs, get_audit_stats, export_audit_csv


@login_required
def audit_log_list(request):
    company = request.current_company
    if not company:
        return redirect('core:dashboard')
    if not (request.user.is_superuser or request.user.is_staff
            or getattr(getattr(request.user, 'profile', None), 'role', '') in ('superadmin', 'admin')):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied

    action = request.GET.get('action', '')
    module = request.GET.get('module', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    user_id = request.GET.get('user_id', '')

    user_filter = None
    if user_id:
        try:
            user_filter = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            pass

    qs = get_audit_logs(
        company,
        action=action or None,
        module=module or None,
        user=user_filter,
        date_from=date_from or None,
        date_to=date_to or None,
        limit=2000,
    )

    if 'export_csv' in request.GET:
        csv_data = export_audit_csv(company, qs)
        resp = HttpResponse(csv_data, content_type='text/csv; charset=utf-8')
        resp['Content-Disposition'] = 'attachment; filename="audit_log.csv"'
        return resp

    paginator = Paginator(qs, 50)
    page = paginator.get_page(request.GET.get('page', 1))
    stats = get_audit_stats(company)
    actions = AuditLog.objects.filter(company=company).values_list('action', flat=True).distinct()
    modules = AuditLog.objects.filter(company=company).values_list('module', flat=True).exclude(module='').distinct()

    return render(request, 'audit_compliance/audit_log_list.html', {
        'page_title': 'Journal d\'audit',
        'logs': page,
        'stats': stats,
        'actions': sorted(actions),
        'modules': sorted(modules),
        'filter_action': action,
        'filter_module': module,
        'filter_date_from': date_from,
        'filter_date_to': date_to,
    })


@login_required
def sensitive_actions(request):
    company = request.current_company
    if not company:
        return redirect('core:dashboard')
    logs = get_sensitive_logs(company, limit=200)
    return render(request, 'audit_compliance/sensitive_actions.html', {
        'page_title': 'Actions sensibles',
        'logs': logs,
    })
