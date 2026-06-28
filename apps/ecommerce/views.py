from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Count
from django.utils import timezone
from .models import (
    WebOrder, Shipment, ReturnRequest, SalesChannel, OnlineStore, StoreConnector, SyncLog,
    Promotion, CouponCode, PaymentProvider, OnlinePayment, Carrier, ShippingMethod,
    CustomerSegment, CustomerProfile, CustomerStoreAccount, AbandonedCart,
    MarketplaceAccount, MarketplaceListing, StorePickupPoint,
)
from .forms import (
    WebOrderForm, SalesChannelForm, OnlineStoreForm, StoreConnectorForm,
    PromotionForm, CouponCodeForm, PaymentProviderForm, CarrierForm, ShippingMethodForm,
    ReturnRequestAdminForm, CustomerSegmentForm, MarketplaceAccountForm,
    MarketplaceListingForm, StorePickupPointForm, CustomerStoreAccountForm,
)


# ─── INDEX ────────────────────────────────────────────────────────────────────

@login_required
def index(request):
    return redirect('ecommerce:order_list')


# ─── COMMANDES WEB ────────────────────────────────────────────────────────────

@login_required
def order_list(request):
    company = request.current_company
    qs = WebOrder.objects.filter(company=company)
    status = request.GET.get('status', '')
    search = request.GET.get('q', '')
    if status:
        qs = qs.filter(status=status)
    if search:
        qs = qs.filter(Q(order_number__icontains=search) | Q(customer_name__icontains=search) | Q(customer_email__icontains=search))
    total_orders = qs.count()
    pending_count = WebOrder.objects.filter(company=company, status='pending').count()
    processing_count = WebOrder.objects.filter(company=company, status='processing').count()
    revenue = WebOrder.objects.filter(company=company, payment_status='paid').aggregate(v=Sum('total_ttc'))['v'] or 0
    return render(request, 'ecommerce/order_list.html', {
        'orders': qs, 'status': status, 'search': search,
        'status_choices': WebOrder.STATUS_CHOICES,
        'total_orders': total_orders, 'pending_count': pending_count,
        'processing_count': processing_count, 'revenue': revenue,
    })


@login_required
def order_detail(request, pk):
    company = request.current_company
    order = get_object_or_404(WebOrder, pk=pk, company=company)
    return render(request, 'ecommerce/order_detail.html', {'order': order})


@login_required
def order_create(request):
    company = request.current_company
    form = WebOrderForm(company=company)
    if request.method == 'POST':
        form = WebOrderForm(request.POST, company=company)
        if form.is_valid():
            order = form.save(commit=False)
            order.company = company
            count = WebOrder.objects.filter(company=company).count()
            order.order_number = f'WEB-{count + 1:05d}'
            order.save()
            messages.success(request, f'Commande {order.order_number} créée.')
            return redirect('ecommerce:order_detail', pk=order.pk)
    return render(request, 'ecommerce/order_form.html', {'form': form, 'action': 'create'})


@login_required
def order_edit(request, pk):
    company = request.current_company
    order = get_object_or_404(WebOrder, pk=pk, company=company)
    form = WebOrderForm(instance=order, company=company)
    if request.method == 'POST':
        form = WebOrderForm(request.POST, instance=order, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, 'Commande mise à jour.')
            return redirect('ecommerce:order_detail', pk=pk)
    return render(request, 'ecommerce/order_form.html', {'form': form, 'order': order, 'action': 'edit'})


@login_required
def order_ship(request, pk):
    company = request.current_company
    order = get_object_or_404(WebOrder, pk=pk, company=company)
    if request.method == 'POST':
        order.status = 'shipped'
        tracking = request.POST.get('tracking_number', '')
        if tracking:
            order.tracking_number = tracking
        order.shipped_at = timezone.now()
        order.save()
        messages.success(request, 'Commande marquée comme expédiée.')
    return redirect('ecommerce:order_detail', pk=pk)


@login_required
def product_list(request):
    company = request.current_company
    from apps.inventory.models import Product
    qs = Product.objects.filter(company=company, is_active=True)
    search = request.GET.get('q', '')
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(reference__icontains=search))
    return render(request, 'ecommerce/product_list.html', {'products': qs, 'search': search})


@login_required
def shipment_list(request):
    company = request.current_company
    qs = WebOrder.objects.filter(company=company, status__in=['shipped', 'delivered'])
    return render(request, 'ecommerce/shipment_list.html', {'orders': qs})


@login_required
def return_list(request):
    company = request.current_company
    qs = ReturnRequest.objects.filter(company=company).select_related('order')
    status = request.GET.get('status', '')
    if status:
        qs = qs.filter(status=status)
    return render(request, 'ecommerce/return_list.html', {'returns': qs, 'status': status})


@login_required
def return_detail(request, pk):
    company = request.current_company
    ret = get_object_or_404(ReturnRequest, pk=pk, company=company)
    form = ReturnRequestAdminForm(instance=ret)
    if request.method == 'POST':
        form = ReturnRequestAdminForm(request.POST, instance=ret)
        if form.is_valid():
            form.save()
            messages.success(request, 'Retour mis à jour.')
            return redirect('ecommerce:return_detail', pk=pk)
    return render(request, 'ecommerce/return_detail.html', {'return_obj': ret, 'form': form})


# ─── CANAUX DE VENTE ──────────────────────────────────────────────────────────

@login_required
def sales_channel_list(request):
    company = request.current_company
    channels = SalesChannel.objects.filter(company=company)
    return render(request, 'ecommerce/sales_channel_list.html', {'channels': channels})


@login_required
def sales_channel_create(request):
    company = request.current_company
    form = SalesChannelForm()
    if request.method == 'POST':
        form = SalesChannelForm(request.POST)
        if form.is_valid():
            ch = form.save(commit=False)
            ch.company = company
            ch.save()
            messages.success(request, f'Canal « {ch.name} » créé.')
            return redirect('ecommerce:sales_channel_list')
    return render(request, 'ecommerce/sales_channel_form.html', {'form': form, 'action': 'create'})


@login_required
def sales_channel_edit(request, pk):
    company = request.current_company
    ch = get_object_or_404(SalesChannel, pk=pk, company=company)
    form = SalesChannelForm(instance=ch)
    if request.method == 'POST':
        form = SalesChannelForm(request.POST, instance=ch)
        if form.is_valid():
            form.save()
            messages.success(request, 'Canal mis à jour.')
            return redirect('ecommerce:sales_channel_list')
    return render(request, 'ecommerce/sales_channel_form.html', {'form': form, 'channel': ch, 'action': 'edit'})


@login_required
def sales_channel_delete(request, pk):
    company = request.current_company
    ch = get_object_or_404(SalesChannel, pk=pk, company=company)
    if request.method == 'POST':
        name = ch.name
        ch.delete()
        messages.success(request, f'Canal « {name} » supprimé.')
        return redirect('ecommerce:sales_channel_list')
    return render(request, 'ecommerce/sales_channel_confirm_delete.html', {'channel': ch})


# ─── BOUTIQUE EN LIGNE ────────────────────────────────────────────────────────

@login_required
def online_store_detail(request, pk):
    company = request.current_company
    store = get_object_or_404(OnlineStore, pk=pk, company=company)
    connectors = StoreConnector.objects.filter(company=company, sales_channel=store.sales_channel)
    return render(request, 'ecommerce/online_store_detail.html', {'store': store, 'connectors': connectors})


@login_required
def online_store_form(request, pk=None):
    company = request.current_company
    store = get_object_or_404(OnlineStore, pk=pk, company=company) if pk else None
    form = OnlineStoreForm(instance=store, company=company)
    if request.method == 'POST':
        form = OnlineStoreForm(request.POST, request.FILES, instance=store, company=company)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.company = company
            obj.save()
            messages.success(request, 'Boutique enregistrée.')
            return redirect('ecommerce:online_store_detail', pk=obj.pk)
    return render(request, 'ecommerce/online_store_form.html', {'form': form, 'store': store, 'action': 'edit' if store else 'create'})


# ─── SYNCHRONISATION ──────────────────────────────────────────────────────────

@login_required
def sync_dashboard(request):
    company = request.current_company
    connectors = StoreConnector.objects.filter(company=company).select_related('sales_channel')
    recent_logs = SyncLog.objects.filter(connector__company=company).order_by('-started_at')[:50]
    return render(request, 'ecommerce/sync_dashboard.html', {
        'connectors': connectors,
        'recent_logs': recent_logs,
    })


# ─── PROMOTIONS ───────────────────────────────────────────────────────────────

@login_required
def promotion_list(request):
    company = request.current_company
    qs = Promotion.objects.filter(company=company)
    status = request.GET.get('status', '')
    if status:
        qs = qs.filter(status=status)
    active_count = Promotion.objects.filter(company=company, status='active').count()
    return render(request, 'ecommerce/promotion_list.html', {
        'promotions': qs, 'status': status,
        'status_choices': Promotion.STATUS_CHOICES, 'active_count': active_count,
    })


@login_required
def promotion_create(request):
    company = request.current_company
    form = PromotionForm(company=company)
    if request.method == 'POST':
        form = PromotionForm(request.POST, company=company)
        if form.is_valid():
            promo = form.save(commit=False)
            promo.company = company
            promo.save()
            messages.success(request, f'Promotion « {promo.name} » créée.')
            return redirect('ecommerce:promotion_list')
    return render(request, 'ecommerce/promotion_form.html', {'form': form, 'action': 'create'})


@login_required
def promotion_edit(request, pk):
    company = request.current_company
    promo = get_object_or_404(Promotion, pk=pk, company=company)
    form = PromotionForm(instance=promo, company=company)
    if request.method == 'POST':
        form = PromotionForm(request.POST, instance=promo, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, 'Promotion mise à jour.')
            return redirect('ecommerce:promotion_list')
    coupons = promo.coupon_codes.all()
    return render(request, 'ecommerce/promotion_form.html', {'form': form, 'promo': promo, 'coupons': coupons, 'action': 'edit'})


@login_required
def promotion_toggle(request, pk):
    company = request.current_company
    promo = get_object_or_404(Promotion, pk=pk, company=company)
    if request.method == 'POST':
        promo.status = 'disabled' if promo.status == 'active' else 'active'
        promo.save()
        messages.success(request, f'Promotion « {promo.name} » : {promo.get_status_display()}.')
    return redirect('ecommerce:promotion_list')


@login_required
def coupon_create(request, promo_pk):
    company = request.current_company
    promo = get_object_or_404(Promotion, pk=promo_pk, company=company)
    form = CouponCodeForm()
    if request.method == 'POST':
        form = CouponCodeForm(request.POST)
        if form.is_valid():
            coupon = form.save(commit=False)
            coupon.promotion = promo
            coupon.save()
            messages.success(request, f'Code « {coupon.code} » créé.')
            return redirect('ecommerce:promotion_edit', pk=promo_pk)
    return render(request, 'ecommerce/coupon_form.html', {'form': form, 'promo': promo})


# ─── PAIEMENTS ────────────────────────────────────────────────────────────────

@login_required
def payment_provider_list(request):
    company = request.current_company
    providers = PaymentProvider.objects.filter(company=company)
    return render(request, 'ecommerce/payment_provider_list.html', {'providers': providers})


@login_required
def payment_provider_form(request, pk=None):
    company = request.current_company
    provider = get_object_or_404(PaymentProvider, pk=pk, company=company) if pk else None
    form = PaymentProviderForm(instance=provider)
    if request.method == 'POST':
        form = PaymentProviderForm(request.POST, instance=provider)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.company = company
            obj.save()
            messages.success(request, 'Fournisseur de paiement enregistré.')
            return redirect('ecommerce:payment_provider_list')
    return render(request, 'ecommerce/payment_provider_form.html', {
        'form': form, 'provider': provider, 'action': 'edit' if provider else 'create'
    })


@login_required
def payment_list(request):
    company = request.current_company
    qs = OnlinePayment.objects.filter(company=company).select_related('order', 'provider')
    status = request.GET.get('status', '')
    if status:
        qs = qs.filter(status=status)
    total_paid = OnlinePayment.objects.filter(company=company, status='paid').aggregate(v=Sum('amount'))['v'] or 0
    return render(request, 'ecommerce/payment_list.html', {
        'payments': qs, 'status': status,
        'status_choices': OnlinePayment.STATUS_CHOICES, 'total_paid': total_paid,
    })


# ─── TRANSPORTEURS ────────────────────────────────────────────────────────────

@login_required
def carrier_list(request):
    company = request.current_company
    carriers = Carrier.objects.filter(company=company)
    return render(request, 'ecommerce/carrier_list.html', {'carriers': carriers})


@login_required
def carrier_create(request):
    company = request.current_company
    form = CarrierForm()
    if request.method == 'POST':
        form = CarrierForm(request.POST)
        if form.is_valid():
            c = form.save(commit=False)
            c.company = company
            c.save()
            messages.success(request, f'Transporteur « {c.name} » créé.')
            return redirect('ecommerce:carrier_list')
    return render(request, 'ecommerce/carrier_form.html', {'form': form, 'action': 'create'})


@login_required
def carrier_edit(request, pk):
    company = request.current_company
    carrier = get_object_or_404(Carrier, pk=pk, company=company)
    form = CarrierForm(instance=carrier)
    if request.method == 'POST':
        form = CarrierForm(request.POST, instance=carrier)
        if form.is_valid():
            form.save()
            messages.success(request, 'Transporteur mis à jour.')
            return redirect('ecommerce:carrier_list')
    methods = carrier.shipping_methods.all()
    return render(request, 'ecommerce/carrier_form.html', {'form': form, 'carrier': carrier, 'methods': methods, 'action': 'edit'})


@login_required
def shipping_method_create(request, carrier_pk):
    company = request.current_company
    carrier = get_object_or_404(Carrier, pk=carrier_pk, company=company)
    form = ShippingMethodForm(company=company)
    if request.method == 'POST':
        form = ShippingMethodForm(request.POST, company=company)
        if form.is_valid():
            m = form.save(commit=False)
            m.carrier = carrier
            m.save()
            messages.success(request, f'Mode de livraison « {m.name} » créé.')
            return redirect('ecommerce:carrier_edit', pk=carrier_pk)
    return render(request, 'ecommerce/shipping_method_form.html', {'form': form, 'carrier': carrier})


# ─── CRM CLIENT E-COMMERCE ────────────────────────────────────────────────────

@login_required
def customer_segment_list(request):
    company = request.current_company
    segments = CustomerSegment.objects.filter(company=company).annotate(
        customer_count=Count('customerprofile')
    )
    return render(request, 'ecommerce/customer_segment_list.html', {'segments': segments})


@login_required
def customer_segment_create(request):
    company = request.current_company
    form = CustomerSegmentForm()
    if request.method == 'POST':
        form = CustomerSegmentForm(request.POST)
        if form.is_valid():
            seg = form.save(commit=False)
            seg.company = company
            seg.save()
            messages.success(request, f'Segment « {seg.name} » créé.')
            return redirect('ecommerce:customer_segment_list')
    return render(request, 'ecommerce/customer_segment_form.html', {'form': form, 'action': 'create'})


@login_required
def customer_segment_edit(request, pk):
    company = request.current_company
    seg = get_object_or_404(CustomerSegment, pk=pk, company=company)
    form = CustomerSegmentForm(instance=seg)
    if request.method == 'POST':
        form = CustomerSegmentForm(request.POST, instance=seg)
        if form.is_valid():
            form.save()
            messages.success(request, 'Segment mis à jour.')
            return redirect('ecommerce:customer_segment_list')
    return render(request, 'ecommerce/customer_segment_form.html', {'form': form, 'segment': seg, 'action': 'edit'})


@login_required
def customer_profile_list(request):
    company = request.current_company
    qs = CustomerStoreAccount.objects.filter(company=company).select_related('profile__segment')
    segment = request.GET.get('segment', '')
    search = request.GET.get('q', '')
    if segment:
        qs = qs.filter(profile__segment_id=segment)
    if search:
        qs = qs.filter(Q(email__icontains=search) | Q(first_name__icontains=search) | Q(last_name__icontains=search))
    segments = CustomerSegment.objects.filter(company=company)
    total_spent = qs.aggregate(v=Sum('total_spent'))['v'] or 0
    return render(request, 'ecommerce/customer_profile_list.html', {
        'customers': qs, 'segments': segments, 'segment': segment, 'search': search,
        'total_customers': qs.count(), 'total_spent': total_spent,
    })


@login_required
def customer_profile_detail(request, pk):
    company = request.current_company
    account = get_object_or_404(CustomerStoreAccount, pk=pk, company=company)
    orders = WebOrder.objects.filter(company=company, customer_email=account.email).order_by('-created_at')[:10]
    return render(request, 'ecommerce/customer_profile_detail.html', {
        'account': account, 'orders': orders,
    })


@login_required
def abandoned_cart_list(request):
    company = request.current_company
    qs = AbandonedCart.objects.filter(cart__company=company).select_related('store_account')
    status = request.GET.get('status', '')
    if status:
        qs = qs.filter(status=status)
    total_value = qs.aggregate(v=Sum('cart_value'))['v'] or 0
    return render(request, 'ecommerce/abandoned_cart_list.html', {
        'carts': qs, 'status': status,
        'status_choices': AbandonedCart.STATUS_CHOICES, 'total_value': total_value,
    })


# ─── MARKETPLACES ─────────────────────────────────────────────────────────────

@login_required
def marketplace_list(request):
    company = request.current_company
    accounts = MarketplaceAccount.objects.filter(company=company).annotate(
        listing_count=Count('listings')
    )
    return render(request, 'ecommerce/marketplace_list.html', {'accounts': accounts})


@login_required
def marketplace_create(request):
    company = request.current_company
    form = MarketplaceAccountForm()
    if request.method == 'POST':
        form = MarketplaceAccountForm(request.POST)
        if form.is_valid():
            acc = form.save(commit=False)
            acc.company = company
            acc.save()
            messages.success(request, f'Compte marketplace « {acc.account_name} » créé.')
            return redirect('ecommerce:marketplace_list')
    return render(request, 'ecommerce/marketplace_form.html', {'form': form, 'action': 'create'})


@login_required
def marketplace_edit(request, pk):
    company = request.current_company
    acc = get_object_or_404(MarketplaceAccount, pk=pk, company=company)
    form = MarketplaceAccountForm(instance=acc)
    if request.method == 'POST':
        form = MarketplaceAccountForm(request.POST, instance=acc)
        if form.is_valid():
            form.save()
            messages.success(request, 'Compte marketplace mis à jour.')
            return redirect('ecommerce:marketplace_list')
    listings = acc.listings.select_related('product')[:30]
    return render(request, 'ecommerce/marketplace_form.html', {
        'form': form, 'marketplace': acc, 'listings': listings, 'action': 'edit'
    })


@login_required
def marketplace_listing_form(request, pk=None):
    company = request.current_company
    listing = get_object_or_404(MarketplaceListing, pk=pk) if pk else None
    form = MarketplaceListingForm(instance=listing, company=company)
    if request.method == 'POST':
        form = MarketplaceListingForm(request.POST, instance=listing, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, 'Listing enregistré.')
            return redirect('ecommerce:marketplace_list')
    return render(request, 'ecommerce/marketplace_listing_form.html', {'form': form, 'listing': listing})


# ─── PICKUP / CLICK & COLLECT ────────────────────────────────────────────────

@login_required
def pickup_point_list(request):
    company = request.current_company
    points = StorePickupPoint.objects.filter(company=company)
    return render(request, 'ecommerce/pickup_point_list.html', {'points': points})


@login_required
def pickup_point_form(request, pk=None):
    company = request.current_company
    point = get_object_or_404(StorePickupPoint, pk=pk, company=company) if pk else None
    form = StorePickupPointForm(instance=point, company=company)
    if request.method == 'POST':
        form = StorePickupPointForm(request.POST, instance=point, company=company)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.company = company
            obj.save()
            messages.success(request, 'Point de retrait enregistré.')
            return redirect('ecommerce:pickup_point_list')
    return render(request, 'ecommerce/pickup_point_form.html', {
        'form': form, 'point': point, 'action': 'edit' if point else 'create'
    })


# ─── TABLEAU DE BORD E-COMMERCE ──────────────────────────────────────────────

@login_required
def ecommerce_dashboard(request):
    company = request.current_company
    today = timezone.now().date()
    orders_today = WebOrder.objects.filter(company=company, created_at__date=today).count()
    revenue_today = WebOrder.objects.filter(company=company, created_at__date=today, payment_status='paid').aggregate(v=Sum('total_ttc'))['v'] or 0
    pending_orders = WebOrder.objects.filter(company=company, status='pending').count()
    channels = SalesChannel.objects.filter(company=company, status='active').count()
    abandoned = AbandonedCart.objects.filter(cart__company=company, status='open').count()
    active_promos = Promotion.objects.filter(company=company, status='active').count()
    recent_orders = WebOrder.objects.filter(company=company).order_by('-created_at')[:8]
    return render(request, 'ecommerce/ecommerce_dashboard.html', {
        'orders_today': orders_today,
        'revenue_today': revenue_today,
        'pending_orders': pending_orders,
        'channels': channels,
        'abandoned': abandoned,
        'active_promos': active_promos,
        'recent_orders': recent_orders,
    })


def _stub(request, *args, **kwargs):
    from django.http import HttpResponse
    return HttpResponse('<h3 style="font-family:sans-serif;padding:2rem">En cours de developpement.</h3>')
order_export = login_required(_stub)
order_import = login_required(_stub)
order_prepare = login_required(_stub)
order_refund = login_required(_stub)
product_create = login_required(_stub)
product_detail = login_required(_stub)
product_edit = login_required(_stub)
product_import = login_required(_stub)
product_publish = login_required(_stub)
product_publish_bulk = login_required(_stub)
product_sync = login_required(_stub)
return_accept = login_required(_stub)
return_accept_bulk = login_required(_stub)
return_create = login_required(_stub)
return_refund = login_required(_stub)
return_refund_bulk = login_required(_stub)
shipment_create = login_required(_stub)
shipment_dispute = login_required(_stub)
shipment_export = login_required(_stub)
shipment_label = login_required(_stub)
shipment_notify = login_required(_stub)

