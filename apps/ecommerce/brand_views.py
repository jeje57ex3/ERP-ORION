"""
Brand-aware e-commerce views — cart, wishlist, orders, rewards, watch configs.
"""
import json
from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from apps.core.models import Company
from .models import Cart, CartItem, CustomerStoreAccount, CustomerBrandProfile, WebOrder


def _get_company(request):
    return getattr(request, 'current_company', None) or Company.objects.filter(is_active=True).first()


def _json(request):
    try:
        return json.loads(request.body)
    except Exception:
        return {}


def _get_brand_key(request):
    return getattr(request, 'brand_key', 'siecle')


def _get_or_create_cart(request, company, brand_key):
    account = None
    if request.user.is_authenticated:
        try:
            account = CustomerStoreAccount.objects.get(company=company, user=request.user)
        except CustomerStoreAccount.DoesNotExist:
            pass

    if account:
        cart, _ = Cart.objects.get_or_create(
            company=company,
            brand_key=brand_key,
            store_account=account,
            is_active=True,
            defaults={'session_key': request.session.session_key or ''},
        )
    else:
        session_key = request.session.session_key or ''
        if not session_key:
            request.session.create()
            session_key = request.session.session_key
        cart, _ = Cart.objects.get_or_create(
            company=company,
            brand_key=brand_key,
            session_key=session_key,
            store_account=None,
            is_active=True,
        )
    return cart


def _cart_to_dict(cart):
    items = []
    for item in cart.items.select_related('product').all():
        items.append({
            'id': item.pk,
            'product_id': item.product.pk,
            'product_name': item.product.name,
            'quantity': item.quantity,
            'unit_price': str(item.unit_price),
            'total': str(item.total),
        })
    return {
        'id': cart.pk,
        'brand_key': cart.brand_key,
        'items': items,
        'count': sum(i['quantity'] for i in items),
        'subtotal': str(cart.subtotal),
        'total': str(cart.total),
    }


@method_decorator(csrf_exempt, name='dispatch')
class BrandCartView(View):
    def get(self, request):
        company = _get_company(request)
        brand_key = _get_brand_key(request)
        cart = _get_or_create_cart(request, company, brand_key)
        return JsonResponse(_cart_to_dict(cart))


@method_decorator(csrf_exempt, name='dispatch')
class BrandCartAddView(View):
    def post(self, request):
        company = _get_company(request)
        brand_key = _get_brand_key(request)
        data = _json(request)
        product_id = data.get('product_id')
        quantity = int(data.get('quantity', 1))

        if not product_id:
            return JsonResponse({'error': 'product_id requis.'}, status=400)

        try:
            from apps.inventory.models import Product
            product = Product.objects.get(pk=product_id, company=company)
        except Exception:
            return JsonResponse({'error': 'Produit introuvable.'}, status=404)

        cart = _get_or_create_cart(request, company, brand_key)
        item, created = CartItem.objects.get_or_create(
            cart=cart, product=product,
            defaults={'unit_price': product.selling_price or 0, 'quantity': quantity},
        )
        if not created:
            item.quantity += quantity
            item.save(update_fields=['quantity'])

        return JsonResponse({'status': 'ok', 'cart': _cart_to_dict(cart)})


@method_decorator(csrf_exempt, name='dispatch')
class BrandCartUpdateView(View):
    def post(self, request):
        company = _get_company(request)
        brand_key = _get_brand_key(request)
        data = _json(request)
        item_id = data.get('item_id')
        quantity = int(data.get('quantity', 1))

        cart = _get_or_create_cart(request, company, brand_key)
        try:
            item = cart.items.get(pk=item_id)
            if quantity <= 0:
                item.delete()
            else:
                item.quantity = quantity
                item.save(update_fields=['quantity'])
        except CartItem.DoesNotExist:
            pass
        return JsonResponse({'status': 'ok', 'cart': _cart_to_dict(cart)})


@method_decorator(csrf_exempt, name='dispatch')
class BrandCartRemoveView(View):
    def post(self, request):
        company = _get_company(request)
        brand_key = _get_brand_key(request)
        data = _json(request)
        item_id = data.get('item_id')

        cart = _get_or_create_cart(request, company, brand_key)
        cart.items.filter(pk=item_id).delete()
        return JsonResponse({'status': 'ok', 'cart': _cart_to_dict(cart)})


@method_decorator(csrf_exempt, name='dispatch')
class BrandWishlistView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({'items': [], 'brand_key': _get_brand_key(request)})

        company = _get_company(request)
        brand_key = _get_brand_key(request)

        try:
            from apps.lunea.models import CustomerWishlistItem
            items = CustomerWishlistItem.objects.filter(
                company=company,
                customer=request.user,
            ).select_related('product')
            return JsonResponse({
                'brand_key': brand_key,
                'items': [{'product_id': i.product.pk, 'product_name': i.product.name} for i in items],
            })
        except Exception:
            return JsonResponse({'items': [], 'brand_key': brand_key})

    def post(self, request):
        return JsonResponse({'status': 'ok'})


@method_decorator(csrf_exempt, name='dispatch')
class BrandOrdersView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({'orders': [], 'brand_key': _get_brand_key(request)}, status=401)

        company = _get_company(request)
        brand_key = _get_brand_key(request)

        orders = WebOrder.objects.filter(
            company=company,
            brand_key=brand_key,
            customer_email=request.user.email,
        ).order_by('-created_at')[:20]

        return JsonResponse({
            'brand_key': brand_key,
            'orders': [
                {'id': o.pk, 'number': o.order_number, 'status': o.status, 'total': str(o.total_ttc)}
                for o in orders
            ],
        })


@method_decorator(csrf_exempt, name='dispatch')
class BrandRewardsView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({'points': 0, 'brand_key': _get_brand_key(request)}, status=401)

        company = _get_company(request)
        brand_key = _get_brand_key(request)

        # LUNEA loyalty
        if brand_key == 'lunea':
            try:
                from apps.lunea.models import LoyaltyAccount
                account = LoyaltyAccount.objects.get(company=company, customer=request.user)
                return JsonResponse({
                    'brand_key': brand_key,
                    'points': account.points_balance,
                    'lifetime_points': account.points_lifetime,
                    'tier': account.tier.name if account.tier else None,
                })
            except Exception:
                return JsonResponse({'brand_key': brand_key, 'points': 0})

        # SIÈCLE loyalty — uses CustomerStoreAccount.loyalty_points
        try:
            account = CustomerStoreAccount.objects.get(company=company, user=request.user)
            return JsonResponse({
                'brand_key': brand_key,
                'points': account.loyalty_points,
                'tier': None,
            })
        except CustomerStoreAccount.DoesNotExist:
            return JsonResponse({'brand_key': brand_key, 'points': 0})


# ── Watch Customizer (SIÈCLE only) ──────────────────────────────────────────

@method_decorator(csrf_exempt, name='dispatch')
class WatchCustomizationOptionsView(View):
    def get(self, request):
        company = _get_company(request)
        try:
            from .watch_models import WatchCustomizationOption, WatchPreset
            options = WatchCustomizationOption.objects.filter(company=company, is_active=True)
            by_category = {}
            for opt in options:
                cat = opt.category
                if cat not in by_category:
                    by_category[cat] = []
                by_category[cat].append({
                    'id': opt.pk, 'name': opt.name, 'slug': opt.slug,
                    'color_hex': opt.color_hex, 'material': opt.material,
                    'extra_price': str(opt.extra_price),
                })
            presets = WatchPreset.objects.filter(company=company, is_active=True)
            return JsonResponse({
                'options': by_category,
                'presets': [
                    {'id': p.pk, 'name': p.name, 'slug': p.slug,
                     'configuration': p.configuration_json, 'base_price': str(p.base_price)}
                    for p in presets
                ],
            })
        except Exception as e:
            return JsonResponse({'options': {}, 'presets': [], 'error': str(e)})


@method_decorator(csrf_exempt, name='dispatch')
class SavedWatchConfigView(View):
    def get(self, request):
        company = _get_company(request)
        try:
            from .watch_models import SavedWatchConfiguration
            share_token = request.GET.get('token')
            if share_token:
                config = SavedWatchConfiguration.objects.get(company=company, share_token=share_token)
                return JsonResponse({'configuration': config.configuration_json, 'name': config.name})

            if not request.user.is_authenticated:
                return JsonResponse({'configs': []})
            configs = SavedWatchConfiguration.objects.filter(company=company, customer=request.user)
            return JsonResponse({
                'configs': [{'id': c.pk, 'name': c.name, 'total_price': str(c.total_price),
                             'configuration': c.configuration_json, 'share_token': c.share_token} for c in configs]
            })
        except Exception as e:
            return JsonResponse({'configs': [], 'error': str(e)})

    def post(self, request):
        company = _get_company(request)
        data = _json(request)
        try:
            from .watch_models import SavedWatchConfiguration
            config = SavedWatchConfiguration.objects.create(
                company=company,
                brand_key='siecle',
                customer=request.user if request.user.is_authenticated else None,
                session_key=request.session.session_key or '',
                name=data.get('name', 'Ma montre SIÈCLE'),
                configuration_json=data.get('configuration', {}),
                base_price=data.get('base_price', 0),
                options_price=data.get('options_price', 0),
                total_price=data.get('total_price', 0),
                engraving_text=data.get('engraving', ''),
            )
            return JsonResponse({'status': 'ok', 'share_token': config.share_token, 'id': config.pk})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)


@method_decorator(csrf_exempt, name='dispatch')
class AddCustomWatchToCartView(View):
    def post(self, request):
        company = _get_company(request)
        brand_key = 'siecle'
        data = _json(request)

        # Enforce brand_key = siecle for custom watches
        if data.get('brand_key') and data['brand_key'] != 'siecle':
            return JsonResponse({'error': 'Les montres personnalisées appartiennent uniquement à SIÈCLE.'}, status=400)

        price_data = data.get('price', {})
        total_price = price_data.get('total', data.get('total_price', 0))
        base_price = price_data.get('basePrice', 319)
        configuration = data.get('configuration', {})
        harmony_score = data.get('harmony_score', 0)
        creation_name = configuration.get('creationName', 'Montre Atelier SIÈCLE')

        # Save configuration if watch_models available
        share_token = None
        try:
            from .watch_models import SavedWatchConfiguration
            saved = SavedWatchConfiguration.objects.create(
                company=company,
                brand_key='siecle',
                customer=request.user if request.user.is_authenticated else None,
                session_key=request.session.session_key or '',
                name=creation_name,
                configuration_json=configuration,
                base_price=base_price,
                options_price=float(total_price) - float(base_price),
                total_price=total_price,
                engraving_text=configuration.get('engraving', {}).get('text', ''),
            )
            share_token = saved.share_token
        except Exception:
            pass

        cart = _get_or_create_cart(request, company, brand_key)

        watch_line = {
            'type': 'custom_watch',
            'brand_key': 'siecle',
            'name': creation_name,
            'base_product': data.get('base_product_slug', 'classic-date'),
            'price': str(total_price),
            'harmony_score': harmony_score,
            'configuration': configuration,
            'share_token': share_token,
        }

        return JsonResponse({
            'status': 'ok',
            'message': 'Montre Atelier SIÈCLE ajoutée au panier.',
            'brand_key': brand_key,
            'cart_item': watch_line,
            'share_token': share_token,
        })
