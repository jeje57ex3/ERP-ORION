from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from .models import IntegrationConfig
from .services import create_integration, get_active_integrations, get_sync_logs, get_integration_stats


@login_required
def integration_list(request):
    company = request.current_company
    if not company:
        return redirect('core:dashboard')
    integrations = IntegrationConfig.objects.filter(company=company).order_by('name')
    stats = get_integration_stats(company)
    return render(request, 'integration_center/integration_list.html', {
        'page_title': 'Centre d\'intégrations',
        'integrations': integrations, 'stats': stats,
    })


@login_required
def integration_detail(request, pk):
    company = request.current_company
    integration = get_object_or_404(IntegrationConfig, pk=pk, company=company)
    logs = get_sync_logs(company, integration=integration, limit=30)
    return render(request, 'integration_center/integration_detail.html', {
        'page_title': integration.name, 'integration': integration, 'logs': logs,
    })


@login_required
@require_POST
def toggle_integration(request, pk):
    company = request.current_company
    integration = get_object_or_404(IntegrationConfig, pk=pk, company=company)
    integration.is_active = not integration.is_active
    integration.save(update_fields=['is_active', 'updated_at'])
    messages.success(request, f'Intégration {"activée" if integration.is_active else "désactivée"}.')
    return redirect('integration_center:list')
