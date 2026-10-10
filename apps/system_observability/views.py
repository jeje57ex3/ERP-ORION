from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from .models import SystemObservabilityAlert
from .services import (
    get_latest_health_checks, get_system_alerts,
    get_observability_stats, acknowledge_system_alert,
    record_health_check, get_check_history, run_all_checks,
)


@login_required
def observability_dashboard(request):
    company = request.current_company
    if not company:
        return redirect('core:dashboard')
    checks = get_latest_health_checks(company)
    alerts = get_system_alerts(company)[:20]
    stats = get_observability_stats(company)
    return render(request, 'system_observability/dashboard.html', {
        'page_title': 'Observabilité système',
        'checks': checks, 'alerts': alerts, 'stats': stats,
    })


@login_required
@require_POST
def run_checks_now(request):
    company = request.current_company
    if not company:
        return redirect('core:dashboard')
    results = run_all_checks(company)
    problems = [r for r in results if r.status in ('warning', 'critical')]
    if problems:
        messages.warning(request, f'Analyse relancée : {len(results)} check(s), {len(problems)} à surveiller.')
    else:
        messages.success(request, f'Analyse relancée : {len(results)} check(s), tout est OK.')
    return redirect('system_observability:dashboard')


@login_required
def check_history_view(request, check_type):
    company = request.current_company
    history = get_check_history(company, check_type, limit=50)
    return render(request, 'system_observability/check_history.html', {
        'page_title': f'Historique — {check_type}',
        'check_type': check_type, 'history': history,
    })


@login_required
@require_POST
def acknowledge_alert(request, pk):
    company = request.current_company
    alert = get_object_or_404(SystemObservabilityAlert, pk=pk, company=company)
    acknowledge_system_alert(alert, request.user)
    messages.success(request, 'Alerte acquittée.')
    return redirect('system_observability:dashboard')


@login_required
def api_status(request):
    company = request.current_company
    if not company:
        return JsonResponse({'status': 'error'}, status=403)
    stats = get_observability_stats(company)
    return JsonResponse(stats)
