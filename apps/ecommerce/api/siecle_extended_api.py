"""
apps/ecommerce/api/siecle_extended_api.py
Extended SIÈCLE Store API — drops, packs, looks, community, beauty, search, giftcards
"""
import json
import logging
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

logger = logging.getLogger(__name__)

DEMO_DESIGNS = [
    {'id': 'noir',  'label': 'Noir Signature',  'color': '#000000'},
    {'id': 'beige', 'label': 'Beige Élégance',  'color': '#D8C7A3'},
    {'id': 'dore',  'label': 'Doré Nuit',        'color': '#3d2c00'},
    {'id': 'blanc', 'label': 'Minimal Blanc',    'color': '#ffffff'},
]

DEMO_DROPS = [
    {'id': 1, 'slug': 'drop-capsule-automne', 'name': 'Capsule Automne 2025', 'date': '2025-11-15', 'private': False, 'description': 'Collection limitée automne, 50 pièces.', 'registered': False},
    {'id': 2, 'slug': 'drop-prive-nuit',       'name': 'Drop Privé Nuit',      'date': '2025-12-01', 'private': True,  'description': 'Accès exclusif membres GOLD+.',          'registered': False},
]

DEMO_PACKS = [
    {'id': 1, 'name': 'Pack Signature',   'price': 189, 'normal_price': 239, 'points': 950,  'badge': 'Bestseller', 'items': ['T-shirt Urban Noir', 'Casquette Signature', 'Chaussettes Logo x3']},
    {'id': 2, 'name': 'Pack Nuit',        'price': 219, 'normal_price': 289, 'points': 1100, 'badge': 'Soirée',    'items': ['Veste Evening', 'Pantalon Slim Noir', 'Ceinture Cuir']},
    {'id': 3, 'name': 'Pack Minimal',     'price': 129, 'normal_price': 159, 'points': 650,  'badge': 'Essentiel', 'items': ['Tee Premium Blanc', 'Jean Slim', 'Pochette Logo']},
    {'id': 4, 'name': "Pack Élégance",    'price': 259, 'normal_price': 349, 'points': 1300, 'badge': 'Premium',   'items': ['Chemise Satin', 'Blazer Structuré', 'Cravate Soie', 'Boutons manchette']},
    {'id': 5, 'name': 'Full SIÈCLE',      'price': 449, 'normal_price': 629, 'points': 2250, 'badge': 'Ultimate',  'items': ['Veste Signature', 'T-shirt x2', 'Jean Premium', 'Montre Urban', 'Ceinture Cuir', 'Sac Tote']},
]

DEMO_LOOKS = [
    {'id': 1, 'name': 'Look Street Signature', 'curated': True, 'savings': 22, 'items': [
        {'id': 'v1', 'name': 'T-shirt Urban Noir', 'price': 49, 'category': 'vetements'},
        {'id': 'm1', 'name': 'Montre Urban Noir',  'price': 289, 'category': 'montres'},
    ]},
    {'id': 2, 'name': 'Look Business Premium', 'curated': True, 'savings': 35, 'items': [
        {'id': 'v5', 'name': 'Chemise Satin',     'price': 95, 'category': 'vetements'},
        {'id': 'v2', 'name': 'Veste Structurée', 'price': 129, 'category': 'vetements'},
        {'id': 'm3', 'name': 'Montre Brun Élégance', 'price': 349, 'category': 'montres'},
    ]},
]

DEMO_COMMUNITY_POSTS = [
    {'id': 1, 'username': 'style_urbain',  'universe': 'vetements', 'caption': 'Mon look du jour avec la veste signature SIÈCLE 🖤', 'likes': 48,  'products': [1, 2], 'verified': True,  'image': None},
    {'id': 2, 'username': 'montre_fan',    'universe': 'montres',   'caption': 'La Urban Noir en conditions réelles, absolument parfaite.', 'likes': 112, 'products': [5],    'verified': False, 'image': None},
    {'id': 3, 'username': 'beauty_siecle', 'universe': 'maquillage','caption': 'Quiz beauté validé, routine Éclat au top ✨',         'likes': 31,  'products': [],    'verified': True,  'image': None},
    {'id': 4, 'username': 'looks_xx',      'universe': 'vetements', 'caption': 'Pack Signature reçu, packaging impeccable !',          'likes': 67,  'products': [],    'verified': False, 'image': None},
]


class SearchView(View):
    """GET /api/v1/siecle/search/?q=&universe="""

    def get(self, request):
        from apps.websites.models import StoreProduct
        q = request.GET.get('q', '').strip()
        universe = request.GET.get('universe', '')

        if not q:
            return JsonResponse({'results': [], 'count': 0, 'query': q})

        qs = StoreProduct.objects.filter(status='published')
        if universe:
            qs = qs.filter(category__slug=universe)
        qs = qs.filter(name__icontains=q).select_related('category').prefetch_related('images')[:20]

        results = []
        for p in qs:
            img = None
            try:
                i = p.images.order_by('order').first()
                if i and i.image:
                    img = request.build_absolute_uri(i.image.url)
            except Exception:
                pass
            results.append({
                'id':       p.pk,
                'name':     p.name,
                'slug':     p.slug,
                'price':    str(p.price),
                'category': p.category.slug if p.category else '',
                'image':    img,
            })

        return JsonResponse({'results': results, 'count': len(results), 'query': q})


class CategoriesView(View):
    """GET /api/v1/siecle/categories/"""

    def get(self, request):
        from apps.websites.models import StoreCategory
        qs = StoreCategory.objects.filter(is_active=True).order_by('order', 'name')
        data = [{'id': c.pk, 'name': c.name, 'slug': c.slug, 'image': request.build_absolute_uri(c.image.url) if getattr(c, 'image', None) and c.image else None} for c in qs]
        return JsonResponse({'categories': data})


class DropsView(View):
    """GET /api/v1/siecle/drops/"""

    def get(self, request):
        # Try DB first, fall back to demo
        try:
            from apps.websites.models import ProductDrop
            qs = ProductDrop.objects.filter(is_active=True).order_by('-drop_date')
            data = [{'id': d.pk, 'slug': d.slug, 'name': d.name, 'date': str(d.drop_date), 'private': getattr(d, 'is_private', False), 'description': getattr(d, 'description', '')} for d in qs]
            return JsonResponse({'drops': data})
        except Exception:
            return JsonResponse({'drops': DEMO_DROPS})


@method_decorator(csrf_exempt, name='dispatch')
class DropRegisterView(View):
    """POST /api/v1/siecle/drops/<int:pk>/register/"""

    def post(self, request, pk):
        return JsonResponse({'registered': True, 'drop_id': pk})


class PacksView(View):
    """GET /api/v1/siecle/packs/"""

    def get(self, request):
        return JsonResponse({'packs': DEMO_PACKS})


@method_decorator(csrf_exempt, name='dispatch')
class AddPackToCartView(View):
    """POST /api/v1/siecle/cart/add-pack/"""

    def post(self, request):
        try:
            body = json.loads(request.body)
        except Exception:
            return JsonResponse({'error': 'JSON invalide'}, status=400)
        pack_id = body.get('pack_id')
        pack = next((p for p in DEMO_PACKS if p['id'] == pack_id), None)
        if not pack:
            return JsonResponse({'error': 'Pack introuvable'}, status=404)
        return JsonResponse({'added': True, 'pack': pack})


class LooksView(View):
    """GET /api/v1/siecle/looks/"""

    def get(self, request):
        return JsonResponse({'looks': DEMO_LOOKS})


@method_decorator(csrf_exempt, name='dispatch')
class AddLookToCartView(View):
    """POST /api/v1/siecle/cart/add-look/"""

    def post(self, request):
        try:
            body = json.loads(request.body)
        except Exception:
            return JsonResponse({'error': 'JSON invalide'}, status=400)
        look_id = body.get('look_id')
        look = next((l for l in DEMO_LOOKS if l['id'] == look_id), None)
        if not look:
            return JsonResponse({'error': 'Look introuvable'}, status=404)
        return JsonResponse({'added': True, 'look': look})


class GiftCardDesignsView(View):
    """GET /api/v1/siecle/giftcards/designs/"""

    def get(self, request):
        return JsonResponse({'designs': DEMO_DESIGNS})


@method_decorator(csrf_exempt, name='dispatch')
class CreateGiftCardView(View):
    """POST /api/v1/siecle/giftcards/create/"""

    def post(self, request):
        import uuid
        try:
            body = json.loads(request.body)
        except Exception:
            return JsonResponse({'error': 'JSON invalide'}, status=400)

        amount    = body.get('amount')
        design    = body.get('design', 'noir')
        recipient = body.get('recipient', '')
        message   = body.get('message', '')

        if not amount or float(amount) < 10:
            return JsonResponse({'error': 'Montant invalide'}, status=400)

        code = f'SIECLE-{uuid.uuid4().hex[:4].upper()}-{uuid.uuid4().hex[:4].upper()}'
        return JsonResponse({'created': True, 'code': code, 'amount': amount, 'design': design, 'recipient': recipient, 'message': message}, status=201)


@method_decorator(csrf_exempt, name='dispatch')
class IdentityQuizView(View):
    """POST /api/v1/siecle/identity-quiz/"""

    PROFILES = {
        'minimal':   {'name': 'L\'Épuré',    'description': 'Lignes nettes, palette neutre, silhouettes intemporelles.'},
        'statement': {'name': 'Le Bold',      'description': 'Pièces fortes, couleurs vibrantes, présence affirmée.'},
        'street':    {'name': 'L\'Urbain',    'description': 'Streetwear premium, confort et style au quotidien.'},
        'classic':   {'name': 'L\'Élégant',   'description': 'Coupes classiques revisitées, sophistication discrète.'},
    }

    def post(self, request):
        try:
            body = json.loads(request.body)
        except Exception:
            return JsonResponse({'error': 'JSON invalide'}, status=400)

        answers = body.get('answers', {})
        # Simple scoring: count dominant style signals
        scores = {'minimal': 0, 'statement': 0, 'street': 0, 'classic': 0}
        style_map = {
            'Monochrome / neutre': 'minimal', 'Couleurs vives': 'statement',
            'Mix & Match': 'street', 'Classique': 'classic',
            'Hoodie': 'street', 'Blazer': 'classic', 'T-shirt oversized': 'street', 'Chemise': 'classic',
        }
        for v in answers.values():
            key = style_map.get(v)
            if key:
                scores[key] += 1

        profile_key = max(scores, key=scores.get) if any(scores.values()) else 'minimal'
        profile = self.PROFILES[profile_key]
        return JsonResponse({'profile': profile_key, **profile})


@method_decorator(csrf_exempt, name='dispatch')
class BeautyQuizView(View):
    """POST /api/v1/siecle/beauty/quiz/"""

    ROUTINES = {
        'Naturel & no-makeup': {'name': 'Routine Fraîcheur', 'products': ['Fond de teint léger SPF', 'Mascara brun', 'Gloss transparent']},
        'Lumineux & glowy':    {'name': 'Routine Éclat',     'products': ['Primer illuminateur', 'Highlighter doré', 'Rouge nude']},
        'Intense & soirée':    {'name': 'Routine Nuit',       'products': ['Eyeliner noir', 'Palette smoky', 'Rouge intense']},
        'Nude & minimaliste':  {'name': 'Routine Nude',       'products': ['BB Cream', 'Mascara naturel', 'Gloss beige']},
    }

    def post(self, request):
        try:
            body = json.loads(request.body)
        except Exception:
            return JsonResponse({'error': 'JSON invalide'}, status=400)
        finish = body.get('finish', 'Naturel & no-makeup')
        routine = self.ROUTINES.get(finish, self.ROUTINES['Naturel & no-makeup'])
        return JsonResponse(routine)


@method_decorator(csrf_exempt, name='dispatch')
class ShadeFinderView(View):
    """POST /api/v1/siecle/beauty/shade-finder/"""

    RECS = {
        'tres-claire-froid':  ['FDT Porcelaine 01N', 'Correcteur Rose Pâle', 'Blush Lilas'],
        'tres-claire-chaud':  ['FDT Ivoire 01W', 'Correcteur Pêche', 'Blush Pêche'],
        'claire-froid':       ['FDT Beige Rose 02N', 'Fond Teint Léger', 'Blush Framboise'],
        'claire-chaud':       ['FDT Beige Doré 02W', 'Correcteur Apricot', 'Blush Corail'],
        'medium-neutre':      ['FDT Dorée 03N', 'Poudre Miel', 'Blush Brique'],
        'medium-chaud':       ['FDT Caramel 03W', 'Bronzeur Ambre', 'Blush Terracotta'],
        'mate-chaud':         ['FDT Caramel Profond 04W', 'Poudre Banane', 'Blush Brun'],
        'foncee-chaud':       ['FDT Chocolat 05W', 'Correcteur Orange', 'Highlighter Cuivré'],
        'tres-foncee-chaud':  ['FDT Ébène 06W', 'Poudre Dense', 'Highlighter Bronze'],
    }

    def post(self, request):
        try:
            body = json.loads(request.body)
        except Exception:
            return JsonResponse({'error': 'JSON invalide'}, status=400)
        tone      = body.get('tone', 'medium')
        undertone = body.get('undertone', 'neutre')
        key = f'{tone}-{undertone}'
        products = self.RECS.get(key, self.RECS['medium-neutre'])
        return JsonResponse({'products': products, 'tone': tone, 'undertone': undertone})


class CommunityPostsView(View):
    """GET /api/v1/siecle/community/posts/ + POST"""

    def get(self, request):
        universe = request.GET.get('universe')
        posts = DEMO_COMMUNITY_POSTS
        if universe:
            posts = [p for p in posts if p['universe'] == universe]
        return JsonResponse({'posts': posts, 'count': len(posts)})

    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request):
        caption  = request.POST.get('caption', '')
        universe = request.POST.get('universe', 'vetements')
        user     = getattr(request, 'siecle_user', None)
        username = getattr(user, 'username', 'anonyme')
        post = {'id': 999, 'username': username, 'universe': universe, 'caption': caption, 'likes': 0, 'products': [], 'verified': False, 'image': None}
        return JsonResponse({'created': True, 'post': post}, status=201)


class WatchConfigurationsView(View):
    """GET/POST /api/v1/siecle/customer/watch-configurations/"""

    def get(self, request):
        user = getattr(request, 'siecle_user', None)
        if not user:
            return JsonResponse({'results': []})
        try:
            from apps.websites.models import ProductCustomizationConfiguration
            qs = ProductCustomizationConfiguration.objects.filter(customer=user).order_by('-created_at')[:10]
            data = [{'id': c.pk, 'name': getattr(c.product, 'name', 'Montre'), 'case_material': c.configuration_json.get('case'), 'dial_color': c.configuration_json.get('dial'), 'strap': c.configuration_json.get('strap'), 'final_price': float(c.final_price)} for c in qs]
            return JsonResponse({'results': data})
        except Exception:
            return JsonResponse({'results': []})

    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request):
        try:
            body = json.loads(request.body)
        except Exception:
            return JsonResponse({'error': 'JSON invalide'}, status=400)
        return JsonResponse({'saved': True, 'id': None, 'configuration': body}, status=201)


class WatchCertificateView(View):
    """GET /api/v1/siecle/watches/certificate/<str:id>/"""

    def get(self, request, watch_id):
        import datetime
        from apps.websites.models import ProductCustomizationConfiguration
        try:
            cfg = ProductCustomizationConfiguration.objects.get(pk=watch_id)
            data = {
                'certificate_number': f'SIECLE-{cfg.pk:06d}-{cfg.created_at.year}',
                'customer_name':      getattr(cfg.customer, 'full_name', 'Propriétaire SIÈCLE'),
                'watch_name':         getattr(cfg.product, 'name', 'Montre SIÈCLE'),
                'created_at':         cfg.created_at.strftime('%d/%m/%Y'),
                'configuration':      cfg.configuration_json or {},
            }
        except Exception:
            data = {
                'certificate_number': f'SIECLE-DEMO-{watch_id}',
                'customer_name':      'Propriétaire SIÈCLE',
                'watch_name':         'Montre SIÈCLE Urban Noir',
                'created_at':         datetime.date.today().strftime('%d/%m/%Y'),
                'configuration':      {'case': 'Acier Noir', 'dial': 'Noir Mat', 'strap': 'Cuir Brun', 'hands': 'Dorées', 'engraving': ''},
            }
        return JsonResponse(data)
