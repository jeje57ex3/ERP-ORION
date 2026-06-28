from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.contrib import messages
from .models import SiteLog, SiteLogIncident
from . import services


@login_required
def dashboard(request):
    company = request.current_company
    open_incidents = services.get_open_incidents(company)
    recent_logs = SiteLog.objects.filter(company=company).order_by('-logged_at')[:5]
    return render(request, 'btp_smart_site_log/dashboard.html', {
        'open_incidents': open_incidents,
        'recent_logs': recent_logs,
        'open_count': open_incidents.count(),
    })


@login_required
def log_list(request):
    company = request.current_company
    project_id = request.GET.get('project_id', '')
    log_type = request.GET.get('log_type', '')
    logs = services.get_site_logs(
        company,
        project_id=project_id or None,
        log_type=log_type or None,
        date_from=None,
        date_to=None,
    )
    return render(request, 'btp_smart_site_log/log_list.html', {
        'logs': logs,
        'project_id': project_id,
        'log_type': log_type,
    })


@login_required
def log_detail(request, pk):
    company = request.current_company
    site_log = get_object_or_404(SiteLog, pk=pk, company=company)
    incidents = site_log.incidents.all().order_by('-created_at')
    stats = services.get_site_stats(company, site_log.project_id)
    return render(request, 'btp_smart_site_log/log_detail.html', {
        'site_log': site_log,
        'incidents': incidents,
        'stats': stats,
    })


@login_required
def resolve_incident(request, pk):
    company = request.current_company
    incident = get_object_or_404(SiteLogIncident, pk=pk, company=company)
    if request.method == 'POST':
        corrective = request.POST.get('corrective_action', '')
        services.resolve_incident(incident, corrective_action=corrective)
        messages.success(request, 'Incident résolu.')
    from django.shortcuts import redirect
    return redirect('btp_smart_site_log:log_detail', pk=incident.site_log_id)
