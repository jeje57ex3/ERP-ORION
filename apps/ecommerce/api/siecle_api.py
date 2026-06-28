"""
apps/ecommerce/api/siecle_api.py — API publique SIECLE Store

Endpoints :
  GET  /api/v1/siecle/products/
  GET  /api/v1/siecle/products/<slug>/
  GET  /api/v1/siecle/collections/
  POST /api/v1/siecle/cart/validate/
  POST /api/v1/siecle/create-checkout-session/
  POST /api/v1/siecle/stripe/webhook/

Security : le site est identifie par le slug passe en query param ou header.
"""
import json
import uuid
import logging

import stripe

from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.shortcuts import get_object_or_404

logger = logging.getLogger(__name__)

SITE_SLUG_PARAM = 'site'  # ?site=siecle ou header X-Site-Slug


def _get_site(request):
    """Recupere le site depuis le query param ou header."""
    from apps.websites.models import Website
    slug = request.GET.get(SITE_SLUG_PARAM) or request.headers.get('X-Site-Slug', '')
    if slug:
        return Website.objects.filter(slug=slug, site_type='ecommerce', is_active=True).first()
    return None


def _product_to_dict(product, request):
    """Serialize un StoreProduct en dict JSON."""
    main_image = None
    try:
        img = product.images.order_by('order').first()
        if img and img.image:
            main_image = request.build_absolute_uri(img.image.url)
    except Exception:
        pass

    gallery = []
    try:
        for img in product.images.order_by('order'):
            if img.image:
                gallery.append(request.build_absolute_uri(img.image.url))
    except Exception:
        pass

    model_3d_url = None
    if getattr(product, 'model_3d_file', None) and product.model_3d_file:
        model_3d_url = request.build_absolute_uri(product.model_3d_file.url)

    return {
        'id':              product.pk,
        'name':            product.name,
        'slug':            product.slug,
        'category':        product.category.name if product.category else None,
        'category_slug':   product.category.slug if product.category else None,
        'price':           str(product.price),
        'compare_at_price':str(product.compare_at_price) if product.compare_at_price else None,
        'short_description': product.short_description,
        'description':     product.description,
        'image':           main_image,
        'gallery':         gallery,
        'model_3d_url':    model_3d_url,
        'sizes':           getattr(product, 'available_sizes', []) or [],
        'stock_available': product.stock_quantity > 0,
        'stock_quantity':  product.stock_quantity,
        'is_popular':       getattr(product, 'is_popular', False),
        'is_featured':      product.is_featured,
        'is_customizable':  getattr(product, 'is_customizable', False),
        'sku':              product.sku,
        'meta_title':       product.meta_title,
        'meta_description': product.meta_description,
    }


class ProductListView(View):
    """GET /api/v1/siecle/products/"""

    def get(self, request):
        from apps.websites.models import StoreProduct
        site = _get_site(request)
        qs = StoreProduct.objects.filter(status='published').select_related('category').prefetch_related('images')
        if site:
            qs = qs.filter(website=site)

        category = request.GET.get('category')
        if category:
            qs = qs.filter(category__slug=category)

        popular = request.GET.get('popular')
        if popular:
            qs = qs.filter(is_popular=True)

        sort = request.GET.get('sort', '-created_at')
        sort_map = {
            'newest':     '-created_at',
            'price_asc':  'price',
            'price_desc': '-price',
            'popular':    '-is_popular',
            'featured':   '-is_featured',
        }
        qs = qs.order_by(sort_map.get(sort, '-created_at'))

        # Filtres prix
        min_price = request.GET.get('min_price')
        max_price = request.GET.get('max_price')
        if min_price:
            qs = qs.filter(price__gte=min_price)
        if max_price:
            qs = qs.filter(price__lte=max_price)

        data = [_product_to_dict(p, request) for p in qs]
        return JsonResponse({'products': data, 'count': len(data)}, safe=False)


class ProductDetailView(View):
    """GET /api/v1/siecle/products/<slug>/"""

    def get(self, request, slug):
        from apps.websites.models import StoreProduct
        site = _get_site(request)
        qs = StoreProduct.objects.filter(slug=slug, status='published').select_related('category').prefetch_related('images')
        if site:
            qs = qs.filter(website=site)
        product = qs.first()
        if not product:
            return JsonResponse({'error': 'Produit introuvable'}, status=404)

        data = _product_to_dict(product, request)

        # Produits similaires (meme categorie)
        related = []
        if product.category:
            rel_qs = StoreProduct.objects.filter(
                category=product.category, status='published'
            ).exclude(pk=product.pk).prefetch_related('images')[:4]
            related = [_product_to_dict(p, request) for p in rel_qs]
        data['related_products'] = related

        return JsonResponse(data, safe=False)


class CollectionListView(View):
    """GET /api/v1/siecle/collections/"""

    def get(self, request):
        from apps.websites.models import StoreCategory
        site = _get_site(request)
        qs = StoreCategory.objects.filter(is_active=True).order_by('order', 'name')
        if site:
            qs = qs.filter(website=site)

        data = [
            {
                'id':          c.pk,
                'name':        c.name,
                'slug':        c.slug,
                'description': c.description,
                'image':       request.build_absolute_uri(c.image.url) if c.image else None,
                'product_count': c.products.filter(status='published').count(),
            }
            for c in qs
        ]
        return JsonResponse({'collections': data}, safe=False)


@method_decorator(csrf_exempt, name='dispatch')
class CartValidateView(View):
    """
    POST /api/v1/siecle/cart/validate/
    Verifie les prix et stocks cote backend avant checkout.
    """

    def post(self, request):
        from apps.websites.models import StoreProduct
        try:
            payload = json.loads(request.body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({'error': 'Corps JSON invalide'}, status=400)

        items = payload.get('items', [])
        if not items:
            return JsonResponse({'error': 'Panier vide'}, status=400)

        validated = []
        errors = []

        for item in items:
            slug = item.get('slug') or ''
            qty  = int(item.get('quantity', 1))
            size = item.get('size', '')

            try:
                product = StoreProduct.objects.get(slug=slug, status='published')
            except StoreProduct.DoesNotExist:
                errors.append(f'Produit "{slug}" indisponible.')
                continue

            if product.stock_quantity < qty:
                errors.append(f'Stock insuffisant pour "{product.name}" (dispo: {product.stock_quantity}).')
                continue

            sizes = getattr(product, 'available_sizes', []) or []
            if sizes and size and size not in sizes:
                errors.append(f'Taille "{size}" invalide pour "{product.name}".')
                continue

            validated.append({
                'slug':       product.slug,
                'name':       product.name,
                'price':      str(product.price),
                'quantity':   qty,
                'size':       size,
                'subtotal':   str(product.price * qty),
            })

        if errors:
            return JsonResponse({'valid': False, 'errors': errors, 'items': validated}, status=422)
        return JsonResponse({'valid': True, 'items': validated})


@method_decorator(csrf_exempt, name='dispatch')
class CreateCheckoutSessionView(View):
    """
    POST /api/v1/siecle/create-checkout-session/
    Cree une session Stripe Checkout.
    """

    def post(self, request):
        stripe.api_key = getattr(settings, 'STRIPE_SECRET_KEY', '')
        if not stripe.api_key:
            return JsonResponse({'error': 'Stripe non configure'}, status=500)

        from apps.websites.models import StoreProduct, StoreOrder, StoreOrderItem, Website

        try:
            payload = json.loads(request.body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({'error': 'Corps JSON invalide'}, status=400)

        items     = payload.get('items', [])
        email     = payload.get('email', '')
        site_slug = payload.get('site') or request.GET.get(SITE_SLUG_PARAM, '')

        if not items:
            return JsonResponse({'error': 'Panier vide'}, status=400)

        site = None
        if site_slug:
            site = Website.objects.filter(slug=site_slug, is_active=True).first()

        # ── Validation backend ────────────────────────────────────────────────
        line_items = []
        order_lines_data = []
        grand_total = 0

        for item in items:
            slug = item.get('slug', '')
            qty  = max(1, int(item.get('quantity', 1)))
            size = item.get('size', '')
            try:
                product = StoreProduct.objects.get(slug=slug, status='published')
            except StoreProduct.DoesNotExist:
                return JsonResponse({'error': f'Produit "{slug}" indisponible'}, status=422)

            if product.stock_quantity < qty:
                return JsonResponse({'error': f'Stock insuffisant : {product.name}'}, status=422)

            price_cents = int(product.price * 100)
            grand_total += float(product.price) * qty
            line_items.append({
                'price_data': {
                    'currency': 'eur',
                    'product_data': {'name': product.name},
                    'unit_amount': price_cents,
                },
                'quantity': qty,
            })
            order_lines_data.append({
                'product':      product,
                'product_name': product.name,
                'sku':          product.sku,
                'selected_size': size,
                'quantity':     qty,
                'unit_price':   product.price,
                'total_price':  product.price * qty,
            })

        # ── Cree commande en statut checkout_started ──────────────────────────
        order_number = f'SCL-{uuid.uuid4().hex[:8].upper()}'
        order_kwargs = dict(
            order_number=order_number,
            status='checkout_started',
            payment_status='pending',
            customer_email=email,
            customer_name=email.split('@')[0] if email else 'Visiteur',
            subtotal=grand_total,
            grand_total=grand_total,
            payment_method='stripe',
        )
        if site:
            order_kwargs['website'] = site
            order_kwargs['company'] = site.company

        order = None
        if site:
            order = StoreOrder.objects.create(**order_kwargs)
            for line in order_lines_data:
                StoreOrderItem.objects.create(order=order, **line)

        # ── Cree session Stripe ───────────────────────────────────────────────
        base_url = request.build_absolute_uri('/').rstrip('/')
        success_url = payload.get('success_url') or f'{base_url}/checkout/success?session_id={{CHECKOUT_SESSION_ID}}'
        cancel_url  = payload.get('cancel_url')  or f'{base_url}/checkout/cancel'

        session_kwargs = dict(
            payment_method_types=['card'],
            line_items=line_items,
            mode='payment',
            success_url=success_url,
            cancel_url=cancel_url,
        )
        if email:
            session_kwargs['customer_email'] = email

        if order:
            session_kwargs['metadata'] = {'order_id': str(order.pk), 'order_number': order_number}

        try:
            session = stripe.checkout.Session.create(**session_kwargs)
        except stripe.StripeError as e:
            logger.error('Stripe error: %s', e)
            return JsonResponse({'error': str(e)}, status=502)

        # Sauvegarde session ID
        if order:
            order.stripe_session_id = session.id
            order.save(update_fields=['stripe_session_id'])

        return JsonResponse({'checkout_url': session.url, 'session_id': session.id})


@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookView(View):
    """
    POST /api/v1/siecle/stripe/webhook/
    Traite les evenements Stripe (paiement reussi, echoue...).
    """

    def post(self, request):
        stripe.api_key = getattr(settings, 'STRIPE_SECRET_KEY', '')
        webhook_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', '')

        payload   = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')

        try:
            if webhook_secret:
                event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
            else:
                event = stripe.Event.construct_from(json.loads(payload), stripe.api_key)
        except (ValueError, stripe.SignatureVerificationError) as e:
            logger.warning('Stripe webhook validation failed: %s', e)
            return HttpResponse(status=400)

        event_type = event['type']
        logger.info('Stripe webhook received: %s', event_type)

        if event_type == 'checkout.session.completed':
            self._handle_checkout_completed(event['data']['object'])
        elif event_type == 'checkout.session.expired':
            self._handle_checkout_expired(event['data']['object'])
        elif event_type == 'payment_intent.payment_failed':
            self._handle_payment_failed(event['data']['object'])

        return HttpResponse(status=200)

    def _handle_checkout_completed(self, session):
        from apps.websites.models import StoreOrder
        order_id = (session.get('metadata') or {}).get('order_id')
        if not order_id:
            return
        try:
            order = StoreOrder.objects.get(pk=order_id)
            order.status = 'confirmed'
            order.payment_status = 'paid'
            order.stripe_payment_intent = session.get('payment_intent', '')
            order.payment_reference = session.get('payment_intent', '')
            order.save(update_fields=['status', 'payment_status', 'stripe_payment_intent', 'payment_reference'])
            # Decrementer stocks
            for line in order.items.select_related('product'):
                if line.product:
                    line.product.stock_quantity = max(0, line.product.stock_quantity - line.quantity)
                    line.product.save(update_fields=['stock_quantity'])
            logger.info('Order %s paid via Stripe.', order.order_number)
            # Send confirmation email
            try:
                from apps.ecommerce.order_emails import send_order_confirmation
                send_order_confirmation(order)
            except Exception as email_err:
                logger.warning('Order confirmation email failed: %s', email_err)
        except StoreOrder.DoesNotExist:
            logger.warning('StoreOrder %s not found for checkout.session.completed', order_id)

    def _handle_checkout_expired(self, session):
        from apps.websites.models import StoreOrder
        order_id = (session.get('metadata') or {}).get('order_id')
        if not order_id:
            return
        try:
            StoreOrder.objects.filter(pk=order_id, status='checkout_started').update(status='cancelled')
        except Exception:
            pass

    def _handle_payment_failed(self, payment_intent):
        from apps.websites.models import StoreOrder
        pi_id = payment_intent.get('id', '')
        if pi_id:
            StoreOrder.objects.filter(stripe_payment_intent=pi_id).update(
                status='payment_failed', payment_status='failed'
            )


@method_decorator(csrf_exempt, name='dispatch')
class NewsletterSubscribeView(View):
    """
    POST /api/v1/siecle/newsletter/
    Body: { "email": "..." }
    Returns 201 on subscribe, 200 if already subscribed, 400 for invalid email.
    """

    def post(self, request):
        import re
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'detail': 'Corps JSON invalide.'}, status=400)

        email = (data.get('email') or '').strip().lower()
        if not email or not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
            return JsonResponse({'email': ['Adresse e-mail invalide.']}, status=400)

        try:
            from apps.websites.models import NewsletterSubscriber
            obj, created = NewsletterSubscriber.objects.get_or_create(email=email)
            if not created and not obj.active:
                obj.active = True
                obj.save(update_fields=['active'])
                created = True
            return JsonResponse(
                {'subscribed': True, 'created': created},
                status=201 if created else 200,
            )
        except Exception:
            # Model may not exist yet — store email in a fallback log
            logger.info('Newsletter subscription (no model): %s', email)
            return JsonResponse({'subscribed': True, 'created': True}, status=201)


# ──────────────────────────────────────────────────────────────────────────────
# Watch Configurator API
# ──────────────────────────────────────────────────────────────────────────────

VALID_GROUPS = ('case', 'dial', 'hands', 'strap')


class WatchCustomizationOptionsView(View):
    """
    GET /api/v1/siecle/products/<slug>/customization-options/
    Returns the available customization options for a configurable watch product.
    """

    def get(self, request, slug):
        from apps.websites.models import StoreProduct, ProductCustomizationOption
        site = _get_site(request)

        qs = StoreProduct.objects.filter(slug=slug, status='published')
        if site:
            qs = qs.filter(website=site)
        product = qs.first()
        if not product:
            return JsonResponse({'detail': 'Produit introuvable.'}, status=404)

        if not getattr(product, 'is_customizable', False):
            return JsonResponse({'detail': 'Ce produit n\'est pas personnalisable.'}, status=400)

        model_3d_url = None
        if product.model_3d_file:
            model_3d_url = request.build_absolute_uri(product.model_3d_file.url)

        fallback_image = None
        try:
            img = product.images.order_by('order').first()
            if img and img.image:
                fallback_image = request.build_absolute_uri(img.image.url)
        except Exception:
            pass

        # Try to load DB options; fall back to empty lists (frontend uses static data)
        options = {g: [] for g in VALID_GROUPS}
        try:
            db_opts = ProductCustomizationOption.objects.filter(
                product=product, is_active=True
            ).order_by('group', 'sort_order')
            for opt in db_opts:
                if opt.group in options:
                    options[opt.group].append({
                        'id':          opt.code,
                        'label':       opt.label,
                        'color':       opt.color,
                        'material':    opt.material,
                        'price_delta': float(opt.price_delta),
                    })
        except Exception:
            pass

        return JsonResponse({
            'product_id':     product.pk,
            'product_name':   product.name,
            'base_price':     str(product.price),
            'model_3d_url':   model_3d_url,
            'fallback_image': fallback_image,
            'options':        options,
        })


@method_decorator(csrf_exempt, name='dispatch')
class WatchValidateCustomizationView(View):
    """
    POST /api/v1/siecle/products/<slug>/validate-customization/
    Body: { "customization": { "case": "...", "dial": "...", "hands": "...", "strap": "..." } }
    Validates and recomputes price server-side.
    """

    def post(self, request, slug):
        from apps.websites.models import StoreProduct, ProductCustomizationOption
        site = _get_site(request)

        qs = StoreProduct.objects.filter(slug=slug, status='published')
        if site:
            qs = qs.filter(website=site)
        product = qs.first()
        if not product:
            return JsonResponse({'detail': 'Produit introuvable.'}, status=404)

        if not getattr(product, 'is_customizable', False):
            return JsonResponse({'detail': 'Ce produit n\'est pas personnalisable.'}, status=400)

        if product.stock_quantity <= 0:
            return JsonResponse({'detail': 'Stock insuffisant.', 'code': 'out_of_stock'}, status=422)

        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'detail': 'Corps JSON invalide.'}, status=400)

        customization = body.get('customization') or {}
        if not isinstance(customization, dict):
            return JsonResponse({'detail': 'Format de configuration invalide.'}, status=400)

        # Check that the provided codes exist in DB options (if DB has options configured)
        db_opts = {}
        try:
            for opt in ProductCustomizationOption.objects.filter(product=product, is_active=True):
                db_opts.setdefault(opt.group, {})[opt.code] = float(opt.price_delta)
        except Exception:
            db_opts = {}

        options_price = 0
        labels = {}
        errors = {}

        for group in VALID_GROUPS:
            code = customization.get(group)
            if not code:
                errors[group] = 'Option requise.'
                continue

            if db_opts.get(group):
                # Validate against DB
                if code not in db_opts[group]:
                    errors[group] = f'Option {code!r} non disponible.'
                else:
                    options_price += db_opts[group][code]
            else:
                # No DB options configured — use frontend static pricing as trusted reference
                STATIC_DELTAS = {
                    'case_black_steel': 0,  'case_silver': 20,  'case_gold': 35, 'case_beige': 25,
                    'dial_black': 0,        'dial_white': 10,   'dial_grey': 10, 'dial_champagne': 20,
                    'hands_silver': 0,      'hands_gold': 10,   'hands_black': 5,'hands_white': 5,
                    'strap_black_leather': 0,'strap_brown_leather': 15,'strap_beige': 20,'strap_steel': 35,
                }
                options_price += STATIC_DELTAS.get(code, 0)

        if errors:
            return JsonResponse({'detail': 'Configuration invalide.', 'errors': errors}, status=422)

        base_price  = float(product.price)
        final_price = base_price + options_price

        return JsonResponse({
            'valid':         True,
            'base_price':    base_price,
            'options_price': options_price,
            'final_price':   final_price,
        })


@method_decorator(csrf_exempt, name='dispatch')
class WatchAddCustomToCartView(View):
    """
    POST /api/v1/siecle/cart/add-custom-watch/
    Stores a ProductCustomizationConfiguration for reporting / order linkage.
    Returns a configuration ID that can be attached to the order line.
    """

    def post(self, request):
        from apps.websites.models import StoreProduct, ProductCustomizationConfiguration
        site = _get_site(request)

        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'detail': 'Corps JSON invalide.'}, status=400)

        product_id   = body.get('product_id')
        customization = body.get('customization', {})
        labels       = body.get('customization_labels', {})
        base_price   = body.get('base_price', 0)
        options_price = body.get('options_price', 0)
        final_price  = body.get('final_price', 0)

        if not product_id or not isinstance(customization, dict):
            return JsonResponse({'detail': 'Paramètres manquants.'}, status=400)

        try:
            product = StoreProduct.objects.get(pk=product_id, status='published')
        except StoreProduct.DoesNotExist:
            return JsonResponse({'detail': 'Produit introuvable.'}, status=404)

        if not getattr(product, 'is_customizable', False):
            return JsonResponse({'detail': 'Ce produit n\'est pas personnalisable.'}, status=400)

        if product.stock_quantity <= 0:
            return JsonResponse({'detail': 'Stock insuffisant.', 'code': 'out_of_stock'}, status=422)

        # Get company from product website
        company = getattr(product.website, 'company', None)
        if not company:
            # Best-effort: get first company
            from apps.core.models import Company
            company = Company.objects.first()

        customer = None
        if hasattr(request, 'siecle_user') and request.siecle_user:
            customer = request.siecle_user

        try:
            config = ProductCustomizationConfiguration.objects.create(
                company=company,
                product=product,
                customer=customer,
                configuration_json=customization,
                configuration_labels_json=labels,
                base_price=base_price,
                options_price=options_price,
                final_price=final_price,
            )
            return JsonResponse({
                'saved':          True,
                'configuration_id': config.pk,
                'final_price':    float(config.final_price),
            }, status=201)
        except Exception as e:
            logger.warning('WatchAddCustomToCartView error: %s', e)
            return JsonResponse({'saved': False, 'configuration_id': None, 'final_price': float(final_price)}, status=200)
