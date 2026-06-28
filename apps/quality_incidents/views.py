from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from .models import QualityIncident
from .services import get_open_incidents, get_incident_stats, resolve_incident, add_comment


@login_required
def incident_list(request):
    company = request.current_company
    if not company:
        return redirect('core:dashboard')
    severity = request.GET.get('severity', '')
    incident_type = request.GET.get('type', '')
    qs = get_open_incidents(company, severity=severity or None, incident_type=incident_type or None)
    paginator = Paginator(qs, 25)
    page = paginator.get_page(request.GET.get('page', 1))
    stats = get_incident_stats(company)
    return render(request, 'quality_incidents/incident_list.html', {
        'page_title': 'Qualité & Incidents',
        'incidents': page, 'stats': stats,
        'filter_severity': severity, 'filter_type': incident_type,
    })


@login_required
def incident_detail(request, pk):
    company = request.current_company
    incident = get_object_or_404(QualityIncident, pk=pk, company=company)
    return render(request, 'quality_incidents/incident_detail.html', {
        'page_title': incident.title, 'incident': incident,
        'comments': incident.comments.all(),
    })


@login_required
@require_POST
def incident_resolve(request, pk):
    company = request.current_company
    incident = get_object_or_404(QualityIncident, pk=pk, company=company)
    corrective_action = request.POST.get('corrective_action', '')
    comment = request.POST.get('comment', '')
    resolve_incident(incident, corrective_action=corrective_action, user=request.user, comment=comment)
    messages.success(request, 'Incident résolu.')
    return redirect('quality_incidents:list')


@login_required
@require_POST
def add_comment_view(request, pk):
    company = request.current_company
    incident = get_object_or_404(QualityIncident, pk=pk, company=company)
    content = request.POST.get('content', '').strip()
    if content:
        add_comment(incident, request.user, content)
    return redirect('quality_incidents:detail', pk=pk)
