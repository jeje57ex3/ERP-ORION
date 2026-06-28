"""
apps/notifications/views.py — Vues pour la gestion des notifications ERP
"""
import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import Notification, NOTIFICATION_TYPES
from . import services


def _get_company(request):
    """Retourne l'entreprise courante depuis la session/contexte."""
    return getattr(request, 'company', None)


@login_required
def notification_list(request):
    """Liste paginée des notifications avec filtres type, statut, module."""
    company = _get_company(request)
    qs = Notification.objects.filter(user=request.user)
    if company:
        qs = qs.filter(company=company)

    # Filtres
    filter_type = request.GET.get('type', '')
    filter_read = request.GET.get('read', '')
    filter_priority = request.GET.get('priority', '')
    filter_module = request.GET.get('module', '')

    if filter_type:
        qs = qs.filter(notification_type=filter_type)
    if filter_read == 'unread':
        qs = qs.filter(is_read=False)
    elif filter_read == 'read':
        qs = qs.filter(is_read=True)
    if filter_priority:
        qs = qs.filter(priority=filter_priority)
    if filter_module:
        qs = qs.filter(source_module=filter_module)

    # Pagination
    paginator = Paginator(qs, 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    unread_count = services.get_unread_count(request.user, company=company)

    # Modules disponibles pour le filtre
    available_modules = (
        Notification.objects.filter(user=request.user)
        .exclude(source_module='')
        .values_list('source_module', flat=True)
        .distinct()
        .order_by('source_module')
    )

    context = {
        'page_obj': page_obj,
        'unread_count': unread_count,
        'notification_types': NOTIFICATION_TYPES,
        'available_modules': available_modules,
        'filter_type': filter_type,
        'filter_read': filter_read,
        'filter_priority': filter_priority,
        'filter_module': filter_module,
        'page_title': 'Notifications',
    }
    return render(request, 'notifications/notification_list.html', context)


@login_required
@require_POST
def mark_read(request, pk):
    """Marque une notification comme lue (POST)."""
    company = _get_company(request)
    qs = Notification.objects.filter(user=request.user)
    if company:
        qs = qs.filter(company=company)
    notif = get_object_or_404(qs, pk=pk)
    notif.mark_read()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'ok', 'pk': pk})

    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER', '')
    return redirect(next_url or 'notifications:list')


@login_required
@require_POST
def mark_all_read(request):
    """Marque toutes les notifications comme lues (POST)."""
    company = _get_company(request)
    count = services.mark_all_read(request.user, company=company)
    messages.success(request, f'{count} notification(s) marquée(s) comme lue(s).')

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'ok', 'count': count})

    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER', '')
    return redirect(next_url or 'notifications:list')


@login_required
def notification_count_api(request):
    """API JSON retournant le nombre de notifications non lues."""
    company = _get_company(request)
    count = services.get_unread_count(request.user, company=company)
    return JsonResponse({'count': count})


@login_required
@require_POST
def delete_notification(request, pk):
    """Supprime une notification (POST)."""
    company = _get_company(request)
    qs = Notification.objects.filter(user=request.user)
    if company:
        qs = qs.filter(company=company)
    notif = get_object_or_404(qs, pk=pk)
    notif.delete()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'ok', 'pk': pk})

    messages.success(request, 'Notification supprimée.')
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER', '')
    return redirect(next_url or 'notifications:list')
