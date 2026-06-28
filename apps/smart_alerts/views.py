from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator

from .models import SmartAlert
from .services import (
    resolve_alert, acknowledge_alert, ignore_alert,
    get_open_alerts, get_alert_stats, create_alert,
)


@login_required
def alert_list(request):
    company = request.current_company
    if not company:
        return redirect('core:dashboard')

    priority = request.GET.get('priority', '')
    status = request.GET.get('status', '')
    module = request.GET.get('module', '')

    qs = SmartAlert.objects.filter(company=company).select_related('assigned_to', 'resolved_by')
    if priority:
        qs = qs.filter(priority=priority)
    if status:
        qs = qs.filter(status=status)
    elif not status:
        qs = qs.filter(status__in=('open', 'acknowledged'))
    if module:
        qs = qs.filter(source_module=module)

    paginator = Paginator(qs.order_by('-priority', '-created_at'), 25)
    page = paginator.get_page(request.GET.get('page', 1))
    stats = get_alert_stats(company)
    modules = SmartAlert.objects.filter(company=company).values_list('source_module', flat=True).distinct()

    return render(request, 'smart_alerts/alert_list.html', {
        'page_title': 'Centre d\'alertes',
        'alerts': page,
        'stats': stats,
        'modules': sorted(modules),
        'filter_priority': priority,
        'filter_status': status,
        'filter_module': module,
    })


@login_required
def alert_detail(request, pk):
    company = request.current_company
    alert = get_object_or_404(SmartAlert, pk=pk, company=company)
    return render(request, 'smart_alerts/alert_detail.html', {
        'page_title': alert.title,
        'alert': alert,
    })


@login_required
@require_POST
def alert_resolve(request, pk):
    company = request.current_company
    alert = get_object_or_404(SmartAlert, pk=pk, company=company)
    resolve_alert(alert, user=request.user)
    messages.success(request, f'Alerte « {alert.title} » résolue.')
    return redirect('smart_alerts:list')


@login_required
@require_POST
def alert_acknowledge(request, pk):
    company = request.current_company
    alert = get_object_or_404(SmartAlert, pk=pk, company=company)
    acknowledge_alert(alert)
    return redirect('smart_alerts:list')


@login_required
@require_POST
def alert_ignore(request, pk):
    company = request.current_company
    alert = get_object_or_404(SmartAlert, pk=pk, company=company)
    ignore_alert(alert)
    messages.info(request, f'Alerte ignorée.')
    return redirect('smart_alerts:list')


@login_required
def api_widget_data(request):
    """JSON pour widget dashboard."""
    company = request.current_company
    if not company:
        return JsonResponse({'alerts': [], 'stats': {}})
    stats = get_alert_stats(company)
    critical = list(SmartAlert.objects.filter(
        company=company, priority='critical', status__in=('open', 'acknowledged')
    ).values('id', 'title', 'source_module', 'created_at')[:5])
    return JsonResponse({'stats': stats, 'critical': critical})
