"""
apps/orders/views.py — Commandes boutique SIÈCLE dans Orion ERP.
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db.models import Q

from apps.private_saas.decorators import require_company_module
from apps.websites.models import StoreOrder, Website


def _get_siecle_website(company):
    return Website.objects.filter(
        company=company,
        slug='siecle',
        site_type='ecommerce',
        is_active=True,
    ).first()


@login_required
@require_company_module('orders')
def order_list(request):
    company = request.current_company
    website = _get_siecle_website(company)

    if website:
        qs = StoreOrder.objects.filter(website=website).select_related('website')
    else:
        qs = StoreOrder.objects.none()

    status_filter = request.GET.get('status', '')
    payment_filter = request.GET.get('payment', '')
    search = request.GET.get('q', '')

    if status_filter:
        qs = qs.filter(status=status_filter)
    if payment_filter:
        qs = qs.filter(payment_status=payment_filter)
    if search:
        qs = qs.filter(
            Q(order_number__icontains=search)
            | Q(customer_name__icontains=search)
            | Q(customer_email__icontains=search)
        )

    orders = qs.order_by('-created_at')

    return render(request, 'orders/order_list.html', {
        'page_title': 'Commandes SIÈCLE',
        'orders': orders,
        'total': orders.count(),
        'website': website,
        'status_filter': status_filter,
        'payment_filter': payment_filter,
        'search': search,
        'status_choices': StoreOrder.STATUS_CHOICES,
        'payment_choices': StoreOrder.PAYMENT_STATUS_CHOICES,
    })


@login_required
@require_company_module('orders')
def order_detail(request, order_number):
    company = request.current_company
    website = _get_siecle_website(company)

    order = get_object_or_404(
        StoreOrder,
        order_number=order_number,
        company=company,
    )

    return render(request, 'orders/order_detail.html', {
        'page_title': f'Commande {order.order_number}',
        'order': order,
        'items': order.items.select_related('product').all(),
        'website': website,
    })


@login_required
@require_company_module('orders')
@require_POST
def order_mark_processing(request, pk):
    company = request.current_company
    order = get_object_or_404(StoreOrder, pk=pk, company=company)

    if order.status not in ('pending', 'confirmed'):
        messages.warning(request, f'Commande {order.order_number} déjà en {order.get_status_display()}.')
        return redirect('orders:order_detail', order_number=order.order_number)

    order.status = 'preparing'
    order.save(update_fields=['status', 'updated_at'])
    messages.success(request, f'Commande {order.order_number} passée en préparation.')
    return redirect('orders:order_detail', order_number=order.order_number)


@login_required
@require_company_module('orders')
@require_POST
def order_mark_shipped(request, pk):
    company = request.current_company
    order = get_object_or_404(StoreOrder, pk=pk, company=company)

    tracking = request.POST.get('tracking_number', '').strip()
    carrier = request.POST.get('carrier', '').strip()

    if order.status not in ('preparing', 'confirmed', 'pending'):
        messages.warning(request, f'Impossible de passer la commande {order.order_number} en expédiée depuis le statut "{order.get_status_display()}".')
        return redirect('orders:order_detail', order_number=order.order_number)

    order.status = 'shipped'
    order.shipped_at = timezone.now()
    if tracking:
        order.tracking_number = tracking
    if carrier:
        order.carrier = carrier
    order.save(update_fields=['status', 'shipped_at', 'tracking_number', 'carrier', 'updated_at'])
    messages.success(request, f'Commande {order.order_number} marquée expédiée.')
    return redirect('orders:order_detail', order_number=order.order_number)
