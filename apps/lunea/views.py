"""
LUNEA — API views pour le frontend React.

Toutes les vues API retournent du JSON et sont accessibles via /api/v1/lunea/.
"""
import json
import secrets
from django.http import JsonResponse
from django.views import View
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.db.models import Avg, Q
from django.utils import timezone

from .models import (
    LuneaProduct, ProductCategory, ProductShade, ProductReview,
    BeautyRoutine, MakeupLook, CustomerWishlistItem, LoyaltyAccount,
    LoyaltyTransaction, GiftCard, GiftCardDesign, NewsletterSubscriber,
    BeautyBlogPost, SampleProduct, CartGiftThreshold, BeautySubscription,
    ShadeStockAlert, WebOrder, WebOrderLine, BeautyQuizResult,
    ShadeFinderResult, CustomerBeautyProfile, CustomerShadeProfile,
    CustomerSkinDiagnostic,
)


def _get_company(request):
    company = getattr(request, 'current_company', None)
    if company is None:
        from apps.core.models import Company
        company = Company.objects.filter(is_active=True).first()
    return company


def _json(data, status=200):
    return JsonResponse(data, status=status, json_dumps_params={'ensure_ascii': False})


def _product_dict(p, include_shades=False):
    d = {
        'id': p.id,
        'name': p.name,
        'slug': p.slug,
        'short_description': p.short_description,
        'price': str(p.price),
        'compare_price': str(p.compare_price) if p.compare_price else None,
        'category': p.category.name if p.category else None,
        'category_slug': p.category.slug if p.category else None,
        'is_best_seller': p.is_best_seller,
        'is_new': p.is_new,
        'is_vegan': p.is_vegan,
        'is_limited_edition': p.is_limited_edition,
        'has_shades': p.has_shades,
        'finish': p.finish,
        'coverage': p.coverage,
        'skin_types': p.skin_types,
        'loyalty_points': p.loyalty_points,
        'rating_avg': p.rating_avg,
        'review_count': p.review_count,
        'primary_image': None,
    }
    primary = p.images.filter(is_primary=True).first() or p.images.first()
    if primary:
        d['primary_image'] = primary.image.url if primary.image else None
    if include_shades:
        d['shades'] = [
            {
                'id': s.id,
                'name': s.name,
                'hex_color': s.hex_color,
                'undertone': s.undertone,
                'stock': s.stock,
                'is_in_stock': s.is_in_stock,
                'recommended_skin_tones': s.recommended_skin_tones,
            }
            for s in p.shades.filter(is_active=True)
        ]
    return d


# ── Produits ──────────────────────────────────────────────────────────────────

class ProductListView(View):
    def get(self, request):
        company = _get_company(request)
        qs = LuneaProduct.objects.filter(company=company, is_active=True).select_related('category').prefetch_related('images', 'shades')

        category = request.GET.get('category')
        if category:
            qs = qs.filter(category__slug=category)

        q = request.GET.get('q')
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(short_description__icontains=q))

        finish = request.GET.get('finish')
        if finish:
            qs = qs.filter(finish=finish)

        coverage = request.GET.get('coverage')
        if coverage:
            qs = qs.filter(coverage=coverage)

        skin_type = request.GET.get('skin_type')
        if skin_type:
            qs = qs.filter(skin_types__icontains=skin_type)

        best_seller = request.GET.get('best_seller')
        if best_seller == 'true':
            qs = qs.filter(is_best_seller=True)

        is_new = request.GET.get('new')
        if is_new == 'true':
            qs = qs.filter(is_new=True)

        sort = request.GET.get('sort', '-created_at')
        allowed_sorts = ['price', '-price', 'name', '-name', '-created_at', '-rating_avg']
        if sort in ['price', '-price', 'name', '-name', '-created_at']:
            qs = qs.order_by(sort)

        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 24))
        total = qs.count()
        products = list(qs[(page - 1) * per_page:page * per_page])

        return _json({
            'results': [_product_dict(p) for p in products],
            'total': total,
            'page': page,
            'pages': (total + per_page - 1) // per_page,
        })


class ProductDetailView(View):
    def get(self, request, slug):
        company = _get_company(request)
        try:
            p = LuneaProduct.objects.select_related('category').prefetch_related(
                'images', 'shades', 'reviews', 'shade_media'
            ).get(slug=slug, company=company, is_active=True)
        except LuneaProduct.DoesNotExist:
            return _json({'error': 'Produit introuvable'}, 404)

        d = _product_dict(p, include_shades=True)
        d.update({
            'description': p.description,
            'ingredients': p.ingredients,
            'how_to_use': p.how_to_use,
            'benefits': p.benefits,
            'hold_hours': p.hold_hours,
            'images': [
                {'url': img.image.url if img.image else None, 'alt': img.alt_text, 'is_primary': img.is_primary}
                for img in p.images.all()
            ],
            'shade_media': [
                {
                    'shade_name': sm.shade_name,
                    'skin_tone': sm.skin_tone,
                    'image': sm.image.url if sm.image else None,
                }
                for sm in p.shade_media.filter(is_active=True)
            ],
        })
        return _json(d)


class BestSellersView(View):
    def get(self, request):
        company = _get_company(request)
        products = LuneaProduct.objects.filter(
            company=company, is_active=True, is_best_seller=True
        ).select_related('category').prefetch_related('images')[:12]
        return _json({'results': [_product_dict(p) for p in products]})


class NewProductsView(View):
    def get(self, request):
        company = _get_company(request)
        products = LuneaProduct.objects.filter(
            company=company, is_active=True, is_new=True
        ).select_related('category').prefetch_related('images').order_by('-created_at')[:12]
        return _json({'results': [_product_dict(p) for p in products]})


class CategoryListView(View):
    def get(self, request):
        company = _get_company(request)
        cats = ProductCategory.objects.filter(company=company, is_active=True).order_by('order', 'name')
        return _json({'results': [
            {'id': c.id, 'name': c.name, 'slug': c.slug, 'description': c.description}
            for c in cats
        ]})


# ── Recherche ─────────────────────────────────────────────────────────────────

class SearchView(View):
    def get(self, request):
        company = _get_company(request)
        q = request.GET.get('q', '').strip()
        if not q:
            return _json({'results': [], 'query': q})

        products = LuneaProduct.objects.filter(
            company=company, is_active=True
        ).filter(Q(name__icontains=q) | Q(short_description__icontains=q)).prefetch_related('images')[:8]

        return _json({
            'results': [_product_dict(p) for p in products],
            'query': q,
            'count': len(list(products)),
        })


# ── Diagnostic produit ────────────────────────────────────────────────────────

class ProductDiagnosticView(View):
    def post(self, request):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return _json({'error': 'JSON invalide'}, 400)

        skin_type = data.get('skin_type', '')
        finish = data.get('finish', '')
        skin_tone = data.get('skin_tone', '')
        product_id = data.get('product_id')

        score = 75
        if skin_type:
            score += 5
        if finish:
            score += 7
        if skin_tone:
            score += 5
        score = min(score, 98)

        return _json({'score': score, 'recommended': score >= 70})


# ── Finder de teinte ──────────────────────────────────────────────────────────

class ShadeFinderView(View):
    def post(self, request):
        company = _get_company(request)
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return _json({'error': 'JSON invalide'}, 400)

        skin_tone = data.get('skin_tone', '')
        undertone = data.get('undertone', '')
        finish = data.get('finish', '')
        coverage = data.get('coverage', '')

        results = {}

        foundation_qs = LuneaProduct.objects.filter(
            company=company, is_active=True, category__slug='teint'
        ).prefetch_related('images', 'shades')
        if finish:
            foundation_qs = foundation_qs.filter(finish=finish)
        if coverage:
            foundation_qs = foundation_qs.filter(coverage=coverage)
        foundation = foundation_qs.first()
        if foundation:
            results['foundation'] = _product_dict(foundation, include_shades=True)
            shade = foundation.shades.filter(
                recommended_skin_tones__icontains=skin_tone, is_active=True
            ).first() or foundation.shades.filter(is_active=True).first()
            results['foundation_shade'] = shade.name if shade else None

        lip_qs = LuneaProduct.objects.filter(
            company=company, is_active=True, category__slug='levres'
        ).prefetch_related('images', 'shades')
        lip = lip_qs.first()
        if lip:
            results['lip'] = _product_dict(lip, include_shades=True)

        if request.user.is_authenticated:
            ShadeFinderResult.objects.create(
                company=company, customer=request.user,
                skin_tone=skin_tone, undertone=undertone, finish=finish, coverage=coverage,
            )

        return _json({'results': results, 'skin_tone': skin_tone, 'undertone': undertone})


# ── Comparateur de teintes ────────────────────────────────────────────────────

class ShadeCompareView(View):
    def get(self, request):
        shade_ids = request.GET.getlist('shades')
        shades = ProductShade.objects.filter(id__in=shade_ids).select_related('product')
        return _json({'shades': [
            {
                'id': s.id,
                'name': s.name,
                'product': s.product.name,
                'product_slug': s.product.slug,
                'hex_color': s.hex_color,
                'undertone': s.undertone,
                'recommended_skin_tones': s.recommended_skin_tones,
                'is_in_stock': s.is_in_stock,
            }
            for s in shades
        ]})


# ── Quiz beauté ───────────────────────────────────────────────────────────────

class BeautyQuizView(View):
    def post(self, request):
        company = _get_company(request)
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return _json({'error': 'JSON invalide'}, 400)

        skin_type = data.get('skin_type', '')
        skin_tone = data.get('skin_tone', '')
        undertone = data.get('undertone', '')
        finish = data.get('preferred_finish', '')

        products_qs = LuneaProduct.objects.filter(company=company, is_active=True)
        if skin_type:
            products_qs = products_qs.filter(skin_types__icontains=skin_type)
        if finish:
            products_qs = products_qs.filter(finish=finish)
        recommended = list(products_qs[:6])

        routine = BeautyRoutine.objects.filter(company=company, is_active=True).first()

        customer = request.user if request.user.is_authenticated else None
        BeautyQuizResult.objects.create(
            company=company, customer=customer,
            answers=data, skin_type=skin_type, skin_tone=skin_tone, undertone=undertone,
        )

        bonus_points = 50

        return _json({
            'recommended_products': [_product_dict(p) for p in recommended],
            'routine': {'id': routine.id, 'name': routine.name, 'slug': routine.slug} if routine else None,
            'bonus_points': bonus_points,
            'skin_type': skin_type,
            'skin_tone': skin_tone,
            'undertone': undertone,
        })


# ── Routines ──────────────────────────────────────────────────────────────────

class RoutineListView(View):
    def get(self, request):
        company = _get_company(request)
        routines = BeautyRoutine.objects.filter(company=company, is_active=True).prefetch_related('items__product')
        return _json({'results': [
            {
                'id': r.id, 'name': r.name, 'slug': r.slug,
                'description': r.description, 'duration_minutes': r.duration_minutes,
                'is_quick': r.is_quick, 'occasion': r.occasion,
                'total_price': str(r.total_price), 'total_points': r.total_points,
                'product_count': r.items.count(),
            }
            for r in routines
        ]})


class RoutineDetailView(View):
    def get(self, request, slug):
        company = _get_company(request)
        try:
            r = BeautyRoutine.objects.prefetch_related('items__product__images').get(
                slug=slug, company=company, is_active=True
            )
        except BeautyRoutine.DoesNotExist:
            return _json({'error': 'Routine introuvable'}, 404)

        return _json({
            'id': r.id, 'name': r.name, 'slug': r.slug,
            'description': r.description, 'duration_minutes': r.duration_minutes,
            'is_quick': r.is_quick, 'occasion': r.occasion,
            'total_price': str(r.total_price), 'total_points': r.total_points,
            'image': r.image.url if r.image else None,
            'items': [
                {
                    'step': item.step, 'quantity': item.quantity, 'note': item.note,
                    'product': _product_dict(item.product),
                }
                for item in r.items.select_related('product').prefetch_related('product__images')
            ],
        })


# ── Looks ─────────────────────────────────────────────────────────────────────

class LookListView(View):
    def get(self, request):
        company = _get_company(request)
        looks = MakeupLook.objects.filter(company=company, is_active=True).prefetch_related('products__product')
        return _json({'results': [
            {
                'id': look.id, 'name': look.name, 'slug': look.slug,
                'image': look.image.url if look.image else None,
                'products': [
                    {
                        'zone': lp.zone, 'shade_name': lp.shade_name,
                        'zone_x': lp.zone_x, 'zone_y': lp.zone_y,
                        'product': _product_dict(lp.product),
                    }
                    for lp in look.products.select_related('product').prefetch_related('product__images')
                ],
            }
            for look in looks
        ]})


# ── Panier ────────────────────────────────────────────────────────────────────

class CartView(View):
    def get(self, request):
        cart = request.session.get('lunea_cart', {})
        company = _get_company(request)
        items = []
        subtotal = 0

        for key, item in cart.items():
            try:
                p = LuneaProduct.objects.get(id=item['product_id'], company=company, is_active=True)
                line_total = float(p.price) * item['quantity']
                subtotal += line_total
                items.append({
                    'key': key,
                    'product_id': p.id,
                    'name': p.name,
                    'slug': p.slug,
                    'price': str(p.price),
                    'quantity': item['quantity'],
                    'shade_name': item.get('shade_name', ''),
                    'line_total': line_total,
                    'loyalty_points': p.loyalty_points * item['quantity'],
                    'image': None,
                })
            except LuneaProduct.DoesNotExist:
                pass

        thresholds = CartGiftThreshold.objects.filter(company=company, is_active=True).order_by('amount')
        next_threshold = thresholds.filter(amount__gt=subtotal).first()
        unlocked = [t for t in thresholds if float(t.amount) <= subtotal]

        return _json({
            'items': items,
            'subtotal': subtotal,
            'count': sum(i['quantity'] for i in cart.values()),
            'next_gift': {
                'amount': str(next_threshold.amount),
                'description': next_threshold.description,
                'remaining': str(float(next_threshold.amount) - subtotal),
            } if next_threshold else None,
            'unlocked_gifts': [{'description': t.description, 'is_free_shipping': t.is_free_shipping} for t in unlocked],
        })

    def post(self, request):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return _json({'error': 'JSON invalide'}, 400)

        product_id = data.get('product_id')
        quantity = int(data.get('quantity', 1))
        shade_name = data.get('shade_name', '')

        company = _get_company(request)
        try:
            p = LuneaProduct.objects.get(id=product_id, company=company, is_active=True)
        except LuneaProduct.DoesNotExist:
            return _json({'error': 'Produit introuvable'}, 404)

        cart = request.session.get('lunea_cart', {})
        key = f'{product_id}_{shade_name}'
        if key in cart:
            cart[key]['quantity'] += quantity
        else:
            cart[key] = {'product_id': product_id, 'quantity': quantity, 'shade_name': shade_name}

        request.session['lunea_cart'] = cart
        request.session.modified = True

        total_count = sum(i['quantity'] for i in cart.values())
        return _json({'success': True, 'cart_count': total_count, 'message': f'{p.name} ajouté au panier'})


class CartAddRoutineView(View):
    def post(self, request):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return _json({'error': 'JSON invalide'}, 400)

        slug = data.get('slug')
        company = _get_company(request)
        try:
            routine = BeautyRoutine.objects.prefetch_related('items__product').get(slug=slug, company=company)
        except BeautyRoutine.DoesNotExist:
            return _json({'error': 'Routine introuvable'}, 404)

        cart = request.session.get('lunea_cart', {})
        for item in routine.items.all():
            key = f'{item.product_id}_'
            if key in cart:
                cart[key]['quantity'] += item.quantity
            else:
                cart[key] = {'product_id': item.product_id, 'quantity': item.quantity, 'shade_name': ''}

        request.session['lunea_cart'] = cart
        request.session.modified = True
        return _json({'success': True, 'message': f'Routine «{routine.name}» ajoutée au panier'})


class CartAddLookView(View):
    def post(self, request):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return _json({'error': 'JSON invalide'}, 400)

        slug = data.get('slug')
        company = _get_company(request)
        try:
            look = MakeupLook.objects.prefetch_related('products__product').get(slug=slug, company=company)
        except MakeupLook.DoesNotExist:
            return _json({'error': 'Look introuvable'}, 404)

        cart = request.session.get('lunea_cart', {})
        for lp in look.products.all():
            key = f'{lp.product_id}_{lp.shade_name}'
            if key in cart:
                cart[key]['quantity'] += 1
            else:
                cart[key] = {'product_id': lp.product_id, 'quantity': 1, 'shade_name': lp.shade_name}

        request.session['lunea_cart'] = cart
        request.session.modified = True
        return _json({'success': True, 'message': f'Look «{look.name}» ajouté au panier'})


# ── Newsletter ────────────────────────────────────────────────────────────────

class NewsletterView(View):
    def post(self, request):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return _json({'error': 'JSON invalide'}, 400)

        email = data.get('email', '').strip().lower()
        if not email:
            return _json({'error': 'Email requis'}, 400)

        company = _get_company(request)
        obj, created = NewsletterSubscriber.objects.get_or_create(
            company=company, email=email,
            defaults={'first_name': data.get('first_name', '')}
        )
        if not created and not obj.is_active:
            obj.is_active = True
            obj.save(update_fields=['is_active'])

        return _json({'success': True, 'message': 'Merci de rejoindre l\'univers LUNEA !'})


# ── Avis ──────────────────────────────────────────────────────────────────────

class ReviewListView(View):
    def get(self, request):
        company = _get_company(request)
        qs = ProductReview.objects.filter(company=company, is_approved=True).select_related('product')

        product_slug = request.GET.get('product')
        if product_slug:
            qs = qs.filter(product__slug=product_slug)

        rating = request.GET.get('rating')
        if rating:
            qs = qs.filter(rating=rating)

        skin_tone = request.GET.get('skin_tone')
        if skin_tone:
            qs = qs.filter(skin_tone=skin_tone)

        page = int(request.GET.get('page', 1))
        per_page = 10
        total = qs.count()

        return _json({
            'results': [
                {
                    'id': r.id,
                    'product': r.product.name,
                    'rating': r.rating,
                    'title': r.title,
                    'comment': r.comment,
                    'shade_name': r.shade_name,
                    'skin_type': r.skin_type,
                    'skin_tone': r.skin_tone,
                    'undertone': r.undertone,
                    'age_range': r.age_range,
                    'is_verified_purchase': r.is_verified_purchase,
                    'image': r.image.url if r.image else None,
                    'created_at': r.created_at.isoformat(),
                }
                for r in qs[(page - 1) * per_page:page * per_page]
            ],
            'total': total,
            'page': page,
        })

    def post(self, request):
        company = _get_company(request)
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return _json({'error': 'JSON invalide'}, 400)

        product_slug = data.get('product_slug')
        try:
            product = LuneaProduct.objects.get(slug=product_slug, company=company)
        except LuneaProduct.DoesNotExist:
            return _json({'error': 'Produit introuvable'}, 404)

        ProductReview.objects.create(
            company=company,
            product=product,
            customer=request.user if request.user.is_authenticated else None,
            rating=int(data.get('rating', 5)),
            title=data.get('title', '')[:200],
            comment=data.get('comment', ''),
            shade_name=data.get('shade_name', '')[:100],
            skin_type=data.get('skin_type', '')[:20],
            skin_tone=data.get('skin_tone', '')[:20],
            undertone=data.get('undertone', '')[:10],
            age_range=data.get('age_range', '')[:10],
            is_verified_purchase=False,
            is_approved=False,
        )
        return _json({'success': True, 'message': 'Votre avis a été soumis et sera publié après modération.'})


# ── Alertes stock ─────────────────────────────────────────────────────────────

class StockAlertView(View):
    def post(self, request):
        company = _get_company(request)
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return _json({'error': 'JSON invalide'}, 400)

        email = data.get('email', '').strip().lower()
        product_slug = data.get('product_slug')
        shade_name = data.get('shade_name', '')

        try:
            product = LuneaProduct.objects.get(slug=product_slug, company=company)
        except LuneaProduct.DoesNotExist:
            return _json({'error': 'Produit introuvable'}, 404)

        ShadeStockAlert.objects.get_or_create(
            company=company, email=email, product=product, shade_name=shade_name,
            defaults={'customer': request.user if request.user.is_authenticated else None}
        )
        return _json({'success': True, 'message': 'Vous serez alerté(e) dès que cette teinte sera disponible.'})


# ── Échantillons ──────────────────────────────────────────────────────────────

class SampleListView(View):
    def get(self, request):
        company = _get_company(request)
        samples = SampleProduct.objects.filter(company=company, is_active=True, stock__gt=0).select_related('product')
        return _json({'results': [
            {
                'id': s.id,
                'name': str(s),
                'product': s.product.name,
                'shade_name': s.shade_name,
                'description': s.description,
                'stock': s.stock,
                'min_order_amount': str(s.min_order_amount),
            }
            for s in samples
        ]})


# ── Paliers cadeaux ───────────────────────────────────────────────────────────

class GiftThresholdView(View):
    def get(self, request):
        company = _get_company(request)
        thresholds = CartGiftThreshold.objects.filter(company=company, is_active=True).order_by('amount')
        return _json({'results': [
            {
                'amount': str(t.amount),
                'description': t.description,
                'is_free_shipping': t.is_free_shipping,
            }
            for t in thresholds
        ]})


# ── Compte client ─────────────────────────────────────────────────────────────

@method_decorator(login_required, name='dispatch')
class CustomerAccountView(View):
    def get(self, request):
        company = _get_company(request)
        user = request.user
        loyalty = LoyaltyAccount.objects.filter(company=company, customer=user).select_related('tier').first()
        beauty_profile = CustomerBeautyProfile.objects.filter(company=company, customer=user).first()
        shade_profile = CustomerShadeProfile.objects.filter(company=company, customer=user).first()

        return _json({
            'id': user.id,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'loyalty': {
                'points_balance': loyalty.points_balance if loyalty else 0,
                'points_lifetime': loyalty.points_lifetime if loyalty else 0,
                'tier': loyalty.tier.name if loyalty and loyalty.tier else 'Lunea Classic',
            },
            'beauty_profile': {
                'skin_type': beauty_profile.skin_type if beauty_profile else '',
                'skin_tone': beauty_profile.skin_tone if beauty_profile else '',
                'undertone': beauty_profile.undertone if beauty_profile else '',
                'preferred_finish': beauty_profile.preferred_finish if beauty_profile else '',
            },
            'shade_profile': {
                'foundation_shade': shade_profile.foundation_shade if shade_profile else '',
                'lip_shade': shade_profile.lip_shade if shade_profile else '',
                'finder_used_count': shade_profile.finder_used_count if shade_profile else 0,
            },
        })


@method_decorator(login_required, name='dispatch')
class CustomerOrdersView(View):
    def get(self, request):
        company = _get_company(request)
        orders = WebOrder.objects.filter(company=company, customer=request.user).prefetch_related('lines__product')
        return _json({'results': [
            {
                'order_number': o.order_number,
                'status': o.status,
                'total': str(o.total),
                'points_earned': o.points_earned,
                'created_at': o.created_at.isoformat(),
                'lines': [
                    {'product': l.product.name, 'shade_name': l.shade_name, 'quantity': l.quantity, 'unit_price': str(l.unit_price)}
                    for l in o.lines.all()
                ],
            }
            for o in orders
        ]})


@method_decorator(login_required, name='dispatch')
class CustomerRewardsView(View):
    def get(self, request):
        company = _get_company(request)
        loyalty = LoyaltyAccount.objects.filter(company=company, customer=request.user).select_related('tier').first()
        transactions = LoyaltyTransaction.objects.filter(account=loyalty).order_by('-created_at')[:20] if loyalty else []

        return _json({
            'points_balance': loyalty.points_balance if loyalty else 0,
            'points_lifetime': loyalty.points_lifetime if loyalty else 0,
            'tier': loyalty.tier.name if loyalty and loyalty.tier else 'Lunea Classic',
            'transactions': [
                {'type': t.type, 'points': t.points, 'description': t.description, 'created_at': t.created_at.isoformat()}
                for t in transactions
            ],
        })


@method_decorator(login_required, name='dispatch')
class CustomerWishlistView(View):
    def get(self, request):
        company = _get_company(request)
        items = CustomerWishlistItem.objects.filter(company=company, customer=request.user).select_related('product').prefetch_related('product__images')
        return _json({'results': [
            {
                'id': i.id,
                'product': _product_dict(i.product),
                'shade_name': i.shade_name,
                'created_at': i.created_at.isoformat(),
            }
            for i in items
        ]})

    def post(self, request):
        company = _get_company(request)
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return _json({'error': 'JSON invalide'}, 400)

        product_slug = data.get('product_slug')
        shade_name = data.get('shade_name', '')

        try:
            product = LuneaProduct.objects.get(slug=product_slug, company=company, is_active=True)
        except LuneaProduct.DoesNotExist:
            return _json({'error': 'Produit introuvable'}, 404)

        item, created = CustomerWishlistItem.objects.get_or_create(
            company=company, customer=request.user, product=product,
            defaults={'shade_name': shade_name}
        )
        if not created:
            item.delete()
            return _json({'success': True, 'action': 'removed'})
        return _json({'success': True, 'action': 'added'})


@method_decorator(login_required, name='dispatch')
class CustomerMyShadesView(View):
    def get(self, request):
        company = _get_company(request)
        shade_profile = CustomerShadeProfile.objects.filter(company=company, customer=request.user).first()
        beauty_profile = CustomerBeautyProfile.objects.filter(company=company, customer=request.user).first()
        wishlist = CustomerWishlistItem.objects.filter(company=company, customer=request.user).select_related('product').prefetch_related('product__images')
        orders = WebOrder.objects.filter(company=company, customer=request.user, status='delivered').prefetch_related('lines__product')

        purchased_products = []
        for order in orders:
            for line in order.lines.all():
                purchased_products.append({'product': _product_dict(line.product), 'shade_name': line.shade_name})

        return _json({
            'shade_profile': {
                'foundation_shade': shade_profile.foundation_shade if shade_profile else '',
                'concealer_shade': shade_profile.concealer_shade if shade_profile else '',
                'powder_shade': shade_profile.powder_shade if shade_profile else '',
                'lip_shade': shade_profile.lip_shade if shade_profile else '',
                'finder_used_count': shade_profile.finder_used_count if shade_profile else 0,
            },
            'beauty_profile': {
                'skin_tone': beauty_profile.skin_tone if beauty_profile else '',
                'undertone': beauty_profile.undertone if beauty_profile else '',
                'skin_type': beauty_profile.skin_type if beauty_profile else '',
            },
            'wishlist': [{'product': _product_dict(i.product), 'shade_name': i.shade_name} for i in wishlist],
            'purchased': purchased_products,
        })


@method_decorator(login_required, name='dispatch')
class CustomerSubscriptionsView(View):
    def get(self, request):
        company = _get_company(request)
        subs = BeautySubscription.objects.filter(company=company, customer=request.user).prefetch_related('items__product')
        return _json({'results': [
            {
                'id': s.id,
                'status': s.status,
                'frequency': s.get_frequency_display(),
                'discount_percent': s.discount_percent,
                'next_renewal_at': s.next_renewal_at.isoformat() if s.next_renewal_at else None,
                'items': [
                    {'product': _product_dict(i.product), 'shade_name': i.shade_name, 'quantity': i.quantity}
                    for i in s.items.select_related('product').prefetch_related('product__images')
                ],
            }
            for s in subs
        ]})

    def post(self, request):
        company = _get_company(request)
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return _json({'error': 'JSON invalide'}, 400)

        sub = BeautySubscription.objects.create(
            company=company,
            customer=request.user,
            frequency=data.get('frequency', 'bimonthly'),
            status='active',
        )
        return _json({'success': True, 'subscription_id': sub.id})


# ── Checkout ──────────────────────────────────────────────────────────────────

class CheckoutSessionView(View):
    def post(self, request):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return _json({'error': 'JSON invalide'}, 400)

        cart = request.session.get('lunea_cart', {})
        if not cart:
            return _json({'error': 'Panier vide'}, 400)

        company = _get_company(request)

        subtotal = 0
        for key, item in cart.items():
            try:
                p = LuneaProduct.objects.get(id=item['product_id'], company=company, is_active=True)
                subtotal += float(p.price) * item['quantity']
            except LuneaProduct.DoesNotExist:
                pass

        shipping = 0 if subtotal >= 80 else 4.90
        total = subtotal + shipping

        try:
            import stripe
            from django.conf import settings
            stripe.api_key = getattr(settings, 'STRIPE_SECRET_KEY', '')

            if stripe.api_key:
                line_items = []
                for key, item in cart.items():
                    try:
                        p = LuneaProduct.objects.get(id=item['product_id'], company=company, is_active=True)
                        line_items.append({
                            'price_data': {
                                'currency': 'eur',
                                'product_data': {'name': p.name + (f' — {item["shade_name"]}' if item.get('shade_name') else '')},
                                'unit_amount': int(float(p.price) * 100),
                            },
                            'quantity': item['quantity'],
                        })
                    except LuneaProduct.DoesNotExist:
                        pass

                session = stripe.checkout.Session.create(
                    payment_method_types=['card'],
                    line_items=line_items,
                    mode='payment',
                    success_url=data.get('success_url', 'http://localhost:5174/commande/success/?session_id={CHECKOUT_SESSION_ID}'),
                    cancel_url=data.get('cancel_url', 'http://localhost:5174/panier/'),
                    customer_email=data.get('email'),
                )
                return _json({'url': session.url, 'session_id': session.id})
        except Exception:
            pass

        return _json({
            'url': f'/commande/success/?demo=1',
            'session_id': 'demo_session',
            'total': total,
            'message': 'Mode démo — Stripe non configuré',
        })
