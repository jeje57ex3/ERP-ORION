from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q, Avg
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from apps.inventory.models import Product
from .models import (
    Cart, CartItem, CheckoutSession, CustomerStoreAccount, CustomerAddress,
    ShippingMethod, Carrier, Promotion, CouponCode, WebOrder, WebOrderLine,
    ReturnRequest, OnlineStore, SalesChannel, StorePickupPoint, PaymentProvider,
    TrackingEvent,
)


def _get_company(request):
    return getattr(request, 'current_company', None)


def _get_or_create_cart(request, company):
    if request.user.is_authenticated and hasattr(request.user, 'store_account'):
        account = request.user.store_account
        cart, _ = Cart.objects.get_or_create(
            company=company, store_account=account, is_active=True,
            defaults={'session_key': request.session.session_key or ''},
        )
    else:
        session_key = request.session.session_key
        if not session_key:
            request.session.create()
            session_key = request.session.session_key
        cart, _ = Cart.objects.get_or_create(
            company=company, session_key=session_key, store_account=None, is_active=True,
        )
    return cart


def _cart_item_count(request, company):
    try:
        cart = _get_or_create_cart(request, company)
        return cart.items.count()
    except Exception:
        return 0


# ─── ACCUEIL BOUTIQUE ─────────────────────────────────────────────────────────

def store_home(request):
    company = _get_company(request)
    featured_products = Product.objects.filter(company=company, is_active=True).order_by('-created_at')[:8]
    from apps.inventory.models import ProductCategory
    categories = ProductCategory.objects.filter(company=company)[:6]
    active_promos = Promotion.objects.filter(company=company, status='active')
    cart_count = _cart_item_count(request, company)
    return render(request, 'store/store_home.html', {
        'featured_products': featured_products,
        'categories': categories,
        'active_promos': active_promos,
        'cart_count': cart_count,
    })


# ─── CATÉGORIE ────────────────────────────────────────────────────────────────

def store_category(request, slug):
    company = _get_company(request)
    from apps.inventory.models import ProductCategory
    category = get_object_or_404(ProductCategory, company=company)
    products = Product.objects.filter(company=company, is_active=True, category=category)

    min_price = request.GET.get('min_price', '')
    max_price = request.GET.get('max_price', '')
    sort = request.GET.get('sort', 'name')

    if min_price:
        products = products.filter(sale_price__gte=min_price)
    if max_price:
        products = products.filter(sale_price__lte=max_price)
    if sort == 'price_asc':
        products = products.order_by('sale_price')
    elif sort == 'price_desc':
        products = products.order_by('-sale_price')
    elif sort == 'newest':
        products = products.order_by('-created_at')
    else:
        products = products.order_by('name')

    cart_count = _cart_item_count(request, company)
    return render(request, 'store/store_category.html', {
        'category': category, 'products': products, 'sort': sort,
        'min_price': min_price, 'max_price': max_price, 'cart_count': cart_count,
    })


# ─── DÉTAIL PRODUIT ───────────────────────────────────────────────────────────

def store_product_detail(request, slug):
    company = _get_company(request)
    try:
        product = get_object_or_404(Product, company=company, is_active=True)
    except Exception:
        product = get_object_or_404(Product, pk=slug, company=company, is_active=True)

    related_products = Product.objects.filter(
        company=company, is_active=True, category=product.category
    ).exclude(pk=product.pk)[:4]

    cart_count = _cart_item_count(request, company)
    return render(request, 'store/store_product_detail.html', {
        'product': product,
        'related_products': related_products,
        'cart_count': cart_count,
    })


# ─── RECHERCHE ────────────────────────────────────────────────────────────────

def store_search(request):
    company = _get_company(request)
    q = request.GET.get('q', '')
    products = Product.objects.none()
    if q:
        products = Product.objects.filter(
            company=company, is_active=True
        ).filter(Q(name__icontains=q) | Q(description__icontains=q) | Q(reference__icontains=q))
    cart_count = _cart_item_count(request, company)
    return render(request, 'store/store_search.html', {
        'products': products, 'q': q, 'cart_count': cart_count,
    })


# ─── PANIER ───────────────────────────────────────────────────────────────────

def cart_view(request):
    company = _get_company(request)
    cart = _get_or_create_cart(request, company)
    items = cart.items.select_related('product').all()
    shipping_methods = ShippingMethod.objects.filter(carrier__company=company, is_active=True).select_related('carrier')
    return render(request, 'store/cart.html', {
        'cart': cart, 'items': items, 'shipping_methods': shipping_methods,
        'cart_count': items.count(),
    })


@require_POST
def cart_add(request):
    company = _get_company(request)
    product_id = request.POST.get('product_id')
    quantity = int(request.POST.get('quantity', 1))
    product = get_object_or_404(Product, pk=product_id, company=company, is_active=True)
    cart = _get_or_create_cart(request, company)
    item, created = CartItem.objects.get_or_create(
        cart=cart, product=product,
        defaults={'unit_price': product.sale_price or product.purchase_price or 0, 'quantity': 0}
    )
    item.quantity += quantity
    item.save()
    messages.success(request, f'« {product.name} » ajouté au panier.')
    return redirect(request.POST.get('next', 'store:cart'))


@require_POST
def cart_update(request):
    company = _get_company(request)
    item_id = request.POST.get('item_id')
    quantity = int(request.POST.get('quantity', 1))
    cart = _get_or_create_cart(request, company)
    item = get_object_or_404(CartItem, pk=item_id, cart=cart)
    if quantity <= 0:
        item.delete()
    else:
        item.quantity = quantity
        item.save()
    return redirect('store:cart')


@require_POST
def cart_remove(request):
    company = _get_company(request)
    item_id = request.POST.get('item_id')
    cart = _get_or_create_cart(request, company)
    CartItem.objects.filter(pk=item_id, cart=cart).delete()
    return redirect('store:cart')


@require_POST
def cart_apply_coupon(request):
    company = _get_company(request)
    code = request.POST.get('coupon_code', '').strip().upper()
    cart = _get_or_create_cart(request, company)
    try:
        coupon = CouponCode.objects.get(code=code, is_active=True, promotion__company=company, promotion__status='active')
        promo = coupon.promotion
        if promo.discount_type == 'percentage':
            discount = cart.subtotal * promo.discount_value / 100
        else:
            discount = promo.discount_value
        cart.coupon_code = code
        cart.discount_amount = discount
        cart.save()
        messages.success(request, f'Code promo « {code} » appliqué ! Remise : {discount:.2f}€')
    except CouponCode.DoesNotExist:
        messages.error(request, 'Code promo invalide ou expiré.')
    return redirect('store:cart')


# ─── CHECKOUT ─────────────────────────────────────────────────────────────────

def checkout_view(request):
    company = _get_company(request)
    cart = _get_or_create_cart(request, company)
    if not cart.items.exists():
        messages.warning(request, 'Votre panier est vide.')
        return redirect('store:cart')

    shipping_methods = ShippingMethod.objects.filter(carrier__company=company, is_active=True).select_related('carrier')
    pickup_points = StorePickupPoint.objects.filter(company=company, is_active=True)
    addresses = []
    if request.user.is_authenticated and hasattr(request.user, 'store_account'):
        addresses = request.user.store_account.addresses.all()

    if request.method == 'POST':
        # Collect form data
        if request.user.is_authenticated:
            first_name = request.user.first_name
            last_name = request.user.last_name
            email = request.user.email
        else:
            first_name = request.POST.get('first_name', '')
            last_name = request.POST.get('last_name', '')
            email = request.POST.get('email', '')
        phone = request.POST.get('phone', '')
        address_str = request.POST.get('shipping_address', '')
        zip_code = request.POST.get('shipping_zip', '')
        city = request.POST.get('shipping_city', '')
        country = request.POST.get('shipping_country', 'France')
        shipping_method_id = request.POST.get('shipping_method')

        # Build full address string
        shipping_address = f'{first_name} {last_name}\n{address_str}\n{zip_code} {city}\n{country}'
        if phone:
            shipping_address += f'\nTél: {phone}'

        # Get shipping cost
        shipping_cost = 0
        shipping_name = ''
        if shipping_method_id:
            try:
                sm = ShippingMethod.objects.get(pk=shipping_method_id, carrier__company=company)
                shipping_cost = sm.base_price
                if sm.free_above and cart.total >= sm.free_above:
                    shipping_cost = 0
                shipping_name = str(sm)
            except ShippingMethod.DoesNotExist:
                pass

        # Create order
        count = WebOrder.objects.filter(company=company).count()
        order_number = f'WEB-{count + 1:05d}'
        total_ttc = cart.total + shipping_cost

        payment_method = 'bank_transfer'
        payment_provider_id = request.POST.get('payment_provider')
        if payment_provider_id:
            try:
                pp = PaymentProvider.objects.get(pk=payment_provider_id, company=company)
                payment_method = pp.provider_type
            except PaymentProvider.DoesNotExist:
                pass

        order = WebOrder.objects.create(
            company=company,
            order_number=order_number,
            customer_name=f'{first_name} {last_name}',
            customer_email=email,
            customer_phone=phone,
            shipping_address=shipping_address,
            status='pending',
            payment_status='pending',
            payment_method=payment_method,
            subtotal=cart.subtotal,
            shipping_cost=shipping_cost,
            total_ttc=total_ttc,
        )

        # Create order lines
        for item in cart.items.select_related('product'):
            WebOrderLine.objects.create(
                order=order,
                product=item.product,
                product_name=item.product.name,
                quantity=item.quantity,
                unit_price=item.unit_price,
                total_price=item.total,
            )

        # Deactivate cart
        cart.is_active = False
        cart.save()

        # Associate with account if logged in
        if request.user.is_authenticated and hasattr(request.user, 'store_account'):
            account = request.user.store_account
            account.total_orders += 1
            account.total_spent += total_ttc
            account.save()

        request.session['last_order_pk'] = order.pk
        return redirect('store:checkout_success')

    items = cart.items.select_related('product').all()
    payment_providers = PaymentProvider.objects.filter(company=company, is_active=True)
    return render(request, 'store/checkout.html', {
        'cart': cart,
        'items': items,
        'shipping_methods': shipping_methods,
        'pickup_points': pickup_points,
        'addresses': addresses,
        'payment_providers': payment_providers,
        'cart_count': items.count(),
        'form': request.POST if request.method == 'POST' else {},
    })


def checkout_success(request):
    company = _get_company(request)
    order_pk = request.session.get('last_order_pk')
    order = None
    if order_pk:
        try:
            order = WebOrder.objects.get(pk=order_pk, company=company)
        except WebOrder.DoesNotExist:
            pass
    return render(request, 'store/checkout_success.html', {'order': order})


# ─── COMPTE CLIENT ────────────────────────────────────────────────────────────

def customer_login(request):
    company = _get_company(request)
    if request.method == 'POST':
        email = request.POST.get('email', '')
        password = request.POST.get('password', '')
        try:
            user = User.objects.get(email=email)
            user = authenticate(request, username=user.username, password=password)
            if user:
                login(request, user)
                return redirect(request.POST.get('next', 'store:customer_account'))
            else:
                messages.error(request, 'Email ou mot de passe incorrect.')
        except User.DoesNotExist:
            messages.error(request, 'Aucun compte avec cet email.')
    return render(request, 'store/customer_login.html', {'cart_count': _cart_item_count(request, company)})


def customer_register(request):
    company = _get_company(request)
    if request.method == 'POST':
        email = request.POST.get('email', '')
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        password = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')

        if password != password2:
            messages.error(request, 'Les mots de passe ne correspondent pas.')
        elif User.objects.filter(email=email).exists():
            messages.error(request, 'Un compte existe déjà avec cet email.')
        else:
            username = email.split('@')[0]
            base = username
            i = 1
            while User.objects.filter(username=username).exists():
                username = f'{base}{i}'
                i += 1
            user = User.objects.create_user(username=username, email=email, password=password, first_name=first_name, last_name=last_name)
            CustomerStoreAccount.objects.create(
                company=company, user=user,
                email=email, first_name=first_name, last_name=last_name,
            )
            login(request, user)
            messages.success(request, 'Compte créé avec succès.')
            return redirect('store:customer_account')
    return render(request, 'store/customer_register.html', {'cart_count': _cart_item_count(request, company)})


def customer_logout(request):
    logout(request)
    return redirect('store:store_home')


def customer_account(request):
    company = _get_company(request)
    if not request.user.is_authenticated:
        return redirect('store:customer_login')
    store_account = getattr(request.user, 'store_account', None)
    if not store_account:
        return redirect('store:customer_login')
    recent_orders = WebOrder.objects.filter(company=company, customer_email=request.user.email).order_by('-created_at')[:5]
    orders_count = WebOrder.objects.filter(company=company, customer_email=request.user.email).count()
    returns_count = ReturnRequest.objects.filter(company=company, order__customer_email=request.user.email).count()
    return render(request, 'store/customer_account.html', {
        'store_account': store_account,
        'recent_orders': recent_orders,
        'orders_count': orders_count,
        'returns_count': returns_count,
        'cart_count': _cart_item_count(request, company),
    })


def customer_orders(request):
    company = _get_company(request)
    if not request.user.is_authenticated:
        return redirect('store:customer_login')
    if not getattr(request.user, 'store_account', None):
        return redirect('store:customer_login')
    orders = WebOrder.objects.filter(company=company, customer_email=request.user.email).order_by('-created_at')
    return render(request, 'store/customer_orders.html', {
        'orders': orders,
        'cart_count': _cart_item_count(request, company),
    })


def customer_order_detail(request, pk):
    company = _get_company(request)
    if not request.user.is_authenticated:
        return redirect('store:customer_login')
    if not getattr(request.user, 'store_account', None):
        return redirect('store:customer_login')
    order = get_object_or_404(WebOrder, pk=pk, company=company, customer_email=request.user.email)
    status_order = ['pending', 'confirmed', 'shipped', 'delivered']
    order_step = status_order.index(order.status) if order.status in status_order else 0
    steps = [
        ('check-circle', 'Confirmée'),
        ('box-seam', 'Préparée'),
        ('truck', 'Expédiée'),
        ('house-check', 'Livrée'),
    ]
    return render(request, 'store/customer_order_detail.html', {
        'order': order,
        'order_step': order_step,
        'steps': steps,
        'cart_count': _cart_item_count(request, company),
    })


def customer_returns(request):
    company = _get_company(request)
    if not request.user.is_authenticated:
        return redirect('store:customer_login')
    if not getattr(request.user, 'store_account', None):
        return redirect('store:customer_login')
    returns = ReturnRequest.objects.filter(
        company=company, order__customer_email=request.user.email
    ).select_related('order').order_by('-created_at')
    return render(request, 'store/customer_returns.html', {
        'returns': returns, 'cart_count': _cart_item_count(request, company),
    })


def order_tracking(request):
    company = _get_company(request)
    query = request.GET.get('order', '')
    order = None
    tracking_events = []
    if query:
        try:
            order = WebOrder.objects.get(order_number=query, company=company)
            if hasattr(order, 'shipments'):
                from .models import TrackingEvent
                tracking_events = TrackingEvent.objects.filter(
                    shipment__order=order
                ).order_by('-timestamp')
        except WebOrder.DoesNotExist:
            messages.error(request, 'Commande introuvable.')

    status_icons = [
        ('check-circle', 'Confirmée', order and order.status in ('confirmed', 'shipped', 'delivered')),
        ('box-seam', 'Préparée', order and order.status in ('shipped', 'delivered')),
        ('truck', 'Expédiée', order and order.status in ('shipped', 'delivered')),
        ('house-check', 'Livrée', order and order.status == 'delivered'),
    ]

    return render(request, 'store/tracking.html', {
        'order': order,
        'query': query,
        'tracking_events': tracking_events,
        'tracking_steps': status_icons,
        'cart_count': _cart_item_count(request, company),
    })
