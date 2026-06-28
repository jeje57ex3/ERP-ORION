"""
apps/ecommerce/api/customer_api.py — Espace client SIÈCLE

Endpoints :
  POST /api/v1/siecle/auth/register/
  POST /api/v1/siecle/auth/login/
  POST /api/v1/siecle/auth/logout/
  GET  /api/v1/siecle/auth/me/
  GET  /api/v1/siecle/customer/account/
  GET  /api/v1/siecle/customer/orders/
  GET  /api/v1/siecle/customer/rewards/
  POST /api/v1/siecle/customer/rewards/use/
  GET  /api/v1/siecle/customer/affiliate/
  POST /api/v1/siecle/customer/affiliate/create-code/
  GET  /api/v1/siecle/gift-card/<code>/
  POST /api/v1/siecle/cart/apply-gift-card/
"""
import json
import secrets
import logging

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)

SITE_SLUG_PARAM = 'site'


def _token_from_request(request):
    auth = request.META.get('HTTP_AUTHORIZATION', '')
    if auth.startswith('Token '):
        return auth[6:].strip()
    return request.COOKIES.get('siecle_token', '')


def _get_customer(request):
    from apps.websites.models import SiecleCustomerToken
    token_key = _token_from_request(request)
    if not token_key:
        return None
    try:
        token = SiecleCustomerToken.objects.select_related('user').get(key=token_key)
        return token.user
    except SiecleCustomerToken.DoesNotExist:
        return None


def _require_auth(func):
    def wrapper(self, request, *args, **kwargs):
        user = _get_customer(request)
        if not user:
            return JsonResponse({'error': 'Authentification requise'}, status=401)
        request.siecle_user = user
        return func(self, request, *args, **kwargs)
    return wrapper


def _get_or_create_loyalty(company, email, user=None):
    from apps.websites.models import LoyaltyAccount
    acc, _ = LoyaltyAccount.objects.get_or_create(
        company=company, customer_email=email,
        defaults={'customer': user},
    )
    if user and not acc.customer:
        acc.customer = user
        acc.save(update_fields=['customer'])
    return acc


# ── Auth ──────────────────────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name='dispatch')
class RegisterView(View):
    def post(self, request):
        from apps.websites.models import SiecleCustomerToken
        try:
            data = json.loads(request.body)
        except Exception:
            return JsonResponse({'error': 'JSON invalide'}, status=400)

        email     = (data.get('email') or '').strip().lower()
        password  = data.get('password', '')
        first_name = data.get('first_name', '')
        last_name  = data.get('last_name', '')

        if not email or not password:
            return JsonResponse({'error': 'Email et mot de passe requis'}, status=400)
        if len(password) < 6:
            return JsonResponse({'error': 'Mot de passe trop court (min 6 caractères)'}, status=400)
        if User.objects.filter(email=email).exists():
            return JsonResponse({'error': 'Un compte existe déjà avec cet email'}, status=409)

        user = User.objects.create_user(
            username=email, email=email, password=password,
            first_name=first_name, last_name=last_name,
        )
        token_key = SiecleCustomerToken.generate(user)

        resp = JsonResponse({
            'token': token_key,
            'user': {'email': email, 'first_name': first_name, 'last_name': last_name},
        }, status=201)
        resp.set_cookie('siecle_token', token_key, httponly=True, samesite='Lax', max_age=86400 * 30)
        return resp


@method_decorator(csrf_exempt, name='dispatch')
class LoginView(View):
    def post(self, request):
        from apps.websites.models import SiecleCustomerToken
        try:
            data = json.loads(request.body)
        except Exception:
            return JsonResponse({'error': 'JSON invalide'}, status=400)

        email    = (data.get('email') or '').strip().lower()
        password = data.get('password', '')

        user = authenticate(request, username=email, password=password)
        if not user:
            # Tenter avec email→username lookup
            try:
                u = User.objects.get(email=email)
                user = authenticate(request, username=u.username, password=password)
            except User.DoesNotExist:
                pass

        if not user:
            return JsonResponse({'error': 'Email ou mot de passe incorrect'}, status=401)

        token_key = SiecleCustomerToken.generate(user)
        resp = JsonResponse({
            'token': token_key,
            'user': {
                'email':      user.email,
                'first_name': user.first_name,
                'last_name':  user.last_name,
            },
        })
        resp.set_cookie('siecle_token', token_key, httponly=True, samesite='Lax', max_age=86400 * 30)
        return resp


@method_decorator(csrf_exempt, name='dispatch')
class LogoutView(View):
    def post(self, request):
        from apps.websites.models import SiecleCustomerToken
        token_key = _token_from_request(request)
        if token_key:
            SiecleCustomerToken.objects.filter(key=token_key).delete()
        resp = JsonResponse({'ok': True})
        resp.delete_cookie('siecle_token')
        return resp


class MeView(View):
    def get(self, request):
        user = _get_customer(request)
        if not user:
            return JsonResponse({'authenticated': False}, status=200)
        return JsonResponse({
            'authenticated': True,
            'user': {
                'email':      user.email,
                'first_name': user.first_name,
                'last_name':  user.last_name,
            },
        })


# ── Compte client ─────────────────────────────────────────────────────────────

class CustomerAccountView(View):
    @_require_auth
    def get(self, request):
        from apps.websites.models import LoyaltyAccount, AffiliateCode, StoreOrder
        from apps.core.models import Company
        user = request.siecle_user

        company = Company.objects.filter(is_active=True).first()

        loyalty = None
        if company:
            loyalty = LoyaltyAccount.objects.filter(company=company, customer_email=user.email).first()

        affiliate = AffiliateCode.objects.filter(customer_email=user.email, is_active=True).first()

        orders_count = StoreOrder.objects.filter(customer_email=user.email).count()

        return JsonResponse({
            'user': {
                'email':      user.email,
                'first_name': user.first_name,
                'last_name':  user.last_name,
            },
            'loyalty': {
                'points_balance':  loyalty.points_balance  if loyalty else 0,
                'lifetime_points': loyalty.lifetime_points if loyalty else 0,
                'tier':            loyalty.tier            if loyalty else 'classic',
            },
            'affiliate': {
                'code':   affiliate.code   if affiliate else None,
                'orders': affiliate.orders if affiliate else 0,
                'clicks': affiliate.clicks if affiliate else 0,
            },
            'orders_count': orders_count,
        })


class CustomerOrdersView(View):
    @_require_auth
    def get(self, request):
        from apps.websites.models import StoreOrder, StoreOrderItem
        user = request.siecle_user
        qs = StoreOrder.objects.filter(customer_email=user.email).order_by('-created_at')[:20]
        orders = []
        for o in qs:
            items = list(o.items.values('product_name', 'quantity', 'unit_price', 'selected_size'))
            orders.append({
                'id':           o.pk,
                'order_number': o.order_number,
                'status':       o.status,
                'payment_status': o.payment_status,
                'grand_total':  str(o.grand_total),
                'created_at':   o.created_at.isoformat(),
                'items':        items,
            })
        return JsonResponse({'orders': orders})


# ── Récompenses ───────────────────────────────────────────────────────────────

REWARD_TIERS = [
    {'id': 'r100',  'points': 100,  'label': '5 € de réduction',   'value': 5,   'type': 'discount'},
    {'id': 'r250',  'points': 250,  'label': '15 € de réduction',  'value': 15,  'type': 'discount'},
    {'id': 'r500',  'points': 500,  'label': '40 € de réduction',  'value': 40,  'type': 'discount'},
    {'id': 'r1000', 'points': 1000, 'label': 'Accès drop privé',   'value': 0,   'type': 'premium'},
]


class CustomerRewardsView(View):
    @_require_auth
    def get(self, request):
        from apps.websites.models import LoyaltyAccount, LoyaltyTransaction
        from apps.core.models import Company
        user    = request.siecle_user
        company = Company.objects.filter(is_active=True).first()

        loyalty = None
        if company:
            loyalty = LoyaltyAccount.objects.filter(company=company, customer_email=user.email).first()

        balance  = loyalty.points_balance  if loyalty else 0
        lifetime = loyalty.lifetime_points if loyalty else 0
        tier     = loyalty.tier            if loyalty else 'classic'

        history = []
        if loyalty:
            for tx in LoyaltyTransaction.objects.filter(loyalty_account=loyalty)[:20]:
                history.append({
                    'points': tx.points,
                    'type':   tx.transaction_type,
                    'reason': tx.reason,
                    'date':   tx.created_at.isoformat(),
                })

        next_tier_pts = {'classic': 500, 'silver': 1000, 'gold': 3000, 'black': None}
        next_pt = next_tier_pts.get(tier)

        rewards = [{**r, 'unlocked': balance >= r['points']} for r in REWARD_TIERS]

        return JsonResponse({
            'points_balance':  balance,
            'lifetime_points': lifetime,
            'tier':            tier,
            'next_tier_at':    next_pt,
            'rewards':         rewards,
            'history':         history,
        })


@method_decorator(csrf_exempt, name='dispatch')
class UseRewardView(View):
    @_require_auth
    def post(self, request):
        from apps.websites.models import LoyaltyAccount
        from apps.core.models import Company
        try:
            data = json.loads(request.body)
        except Exception:
            return JsonResponse({'error': 'JSON invalide'}, status=400)

        reward_id = data.get('reward_id')
        reward    = next((r for r in REWARD_TIERS if r['id'] == reward_id), None)
        if not reward:
            return JsonResponse({'error': 'Récompense invalide'}, status=400)

        user    = request.siecle_user
        company = Company.objects.filter(is_active=True).first()
        if not company:
            return JsonResponse({'error': 'Entreprise non trouvée'}, status=400)

        loyalty = LoyaltyAccount.objects.filter(company=company, customer_email=user.email).first()
        if not loyalty or loyalty.points_balance < reward['points']:
            return JsonResponse({'error': 'Solde insuffisant'}, status=422)

        loyalty.use_points(reward['points'], reason=f"Récompense : {reward['label']}")
        return JsonResponse({
            'ok':              True,
            'reward':          reward,
            'points_balance':  loyalty.points_balance,
        })


# ── Affiliation ───────────────────────────────────────────────────────────────

class CustomerAffiliateView(View):
    @_require_auth
    def get(self, request):
        from apps.websites.models import AffiliateCode, AffiliateReferral
        user = request.siecle_user
        code = AffiliateCode.objects.filter(customer_email=user.email, is_active=True).first()
        referrals = []
        if code:
            for r in AffiliateReferral.objects.filter(affiliate_code=code).order_by('-created_at')[:10]:
                referrals.append({
                    'referred_email': r.referred_email[:3] + '***',
                    'status':         r.status,
                    'points_reward':  r.points_reward,
                    'date':           r.created_at.isoformat(),
                })
        origin = request.build_absolute_uri('/').rstrip('/')
        referral_link = f'{origin}/?ref={code.code}' if code else None
        return JsonResponse({
            'has_code':      bool(code),
            'code':          code.code          if code else None,
            'clicks':        code.clicks        if code else 0,
            'signups':       code.signups        if code else 0,
            'orders':        code.orders        if code else 0,
            'total_commission': str(code.total_commission) if code else '0',
            'referral_link': referral_link,
            'referrals':     referrals,
        })


@method_decorator(csrf_exempt, name='dispatch')
class CreateAffiliateCodeView(View):
    @_require_auth
    def post(self, request):
        from apps.websites.models import AffiliateCode
        from apps.core.models import Company
        user    = request.siecle_user
        company = Company.objects.filter(is_active=True).first()

        if AffiliateCode.objects.filter(customer_email=user.email).exists():
            return JsonResponse({'error': 'Vous avez déjà un code affilié'}, status=409)

        # Génère code unique: SCL-XXXXXXXX
        for _ in range(10):
            code_str = 'SCL-' + secrets.token_hex(4).upper()
            if not AffiliateCode.objects.filter(code=code_str).exists():
                break

        code = AffiliateCode.objects.create(
            company=company,
            customer=user,
            customer_email=user.email,
            code=code_str,
        )
        return JsonResponse({'code': code.code}, status=201)


# ── Cartes cadeaux ────────────────────────────────────────────────────────────

class GiftCardCheckView(View):
    def get(self, request, code):
        from apps.websites.models import GiftCard
        from django.utils import timezone
        try:
            gc = GiftCard.objects.get(code=code.upper())
        except GiftCard.DoesNotExist:
            return JsonResponse({'valid': False, 'error': 'Code invalide'}, status=404)

        if gc.status == 'cancelled':
            return JsonResponse({'valid': False, 'error': 'Carte annulée'}, status=422)
        if gc.status == 'used' or gc.remaining_amount <= 0:
            return JsonResponse({'valid': False, 'error': 'Carte déjà utilisée'}, status=422)
        if gc.expires_at and gc.expires_at < timezone.now().date():
            return JsonResponse({'valid': False, 'error': 'Carte expirée'}, status=422)

        return JsonResponse({
            'valid':            True,
            'code':             gc.code,
            'remaining_amount': str(gc.remaining_amount),
            'currency':         gc.currency,
            'status':           gc.status,
        })


@method_decorator(csrf_exempt, name='dispatch')
class ApplyGiftCardView(View):
    def post(self, request):
        from apps.websites.models import GiftCard
        from django.utils import timezone
        try:
            data = json.loads(request.body)
        except Exception:
            return JsonResponse({'error': 'JSON invalide'}, status=400)

        code       = (data.get('code') or '').upper().strip()
        cart_total = float(data.get('cart_total', 0))

        if not code:
            return JsonResponse({'error': 'Code requis'}, status=400)

        try:
            gc = GiftCard.objects.get(code=code)
        except GiftCard.DoesNotExist:
            return JsonResponse({'valid': False, 'error': 'Code invalide'}, status=404)

        if not gc.is_valid:
            msg = 'Carte expirée' if (gc.expires_at and gc.expires_at < timezone.now().date()) else 'Carte non utilisable'
            return JsonResponse({'valid': False, 'error': msg}, status=422)

        applied = min(float(gc.remaining_amount), cart_total)
        return JsonResponse({
            'valid':            True,
            'code':             gc.code,
            'applied_amount':   applied,
            'remaining_after':  float(gc.remaining_amount) - applied,
            'new_total':        max(0, cart_total - applied),
        })


@method_decorator(csrf_exempt, name='dispatch')
class ApplyRewardPointsView(View):
    """Calcule la réduction si le client veut utiliser ses points au checkout."""
    def post(self, request):
        try:
            data = json.loads(request.body)
        except Exception:
            return JsonResponse({'error': 'JSON invalide'}, status=400)

        reward_id  = data.get('reward_id')
        cart_total = float(data.get('cart_total', 0))
        reward     = next((r for r in REWARD_TIERS if r['id'] == reward_id), None)
        if not reward:
            return JsonResponse({'error': 'Récompense invalide'}, status=400)

        discount    = float(reward.get('value', 0))
        new_total   = max(0, cart_total - discount)
        return JsonResponse({
            'reward_id':  reward_id,
            'discount':   discount,
            'new_total':  new_total,
            'points_used': reward['points'],
        })
