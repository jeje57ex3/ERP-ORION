from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from .models import WebhookEndpoint, WebhookDelivery
from .services import create_endpoint, get_webhook_stats, get_pending_deliveries, trigger_event


@login_required
def endpoint_list(request):
    company = request.current_company
    if not company:
        return redirect('core:dashboard')
    endpoints = WebhookEndpoint.objects.filter(company=company).order_by('-created_at')
    stats = get_webhook_stats(company)
    return render(request, 'api_webhooks/endpoint_list.html', {
        'page_title': 'API & Webhooks',
        'endpoints': endpoints, 'stats': stats,
    })


@login_required
def endpoint_detail(request, pk):
    company = request.current_company
    endpoint = get_object_or_404(WebhookEndpoint, pk=pk, company=company)
    deliveries_qs = WebhookDelivery.objects.filter(endpoint=endpoint).order_by('-created_at')
    paginator = Paginator(deliveries_qs, 20)
    deliveries = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'api_webhooks/endpoint_detail.html', {
        'page_title': endpoint.name, 'endpoint': endpoint, 'deliveries': deliveries,
    })


@login_required
@require_POST
def create_endpoint_view(request):
    company = request.current_company
    name = request.POST.get('name', '').strip()
    url = request.POST.get('url', '').strip()
    events_raw = request.POST.get('events', '')
    events = [e.strip() for e in events_raw.split(',') if e.strip()]
    raw_secret = request.POST.get('secret', '')
    if name and url:
        create_endpoint(company, name, url, events, raw_secret=raw_secret, created_by=request.user)
        messages.success(request, 'Endpoint webhook créé.')
    return redirect('api_webhooks:list')


@login_required
@require_POST
def toggle_endpoint(request, pk):
    company = request.current_company
    endpoint = get_object_or_404(WebhookEndpoint, pk=pk, company=company)
    endpoint.is_active = not endpoint.is_active
    endpoint.save(update_fields=['is_active'])
    messages.success(request, f'Endpoint {"activé" if endpoint.is_active else "désactivé"}.')
    return redirect('api_webhooks:list')
