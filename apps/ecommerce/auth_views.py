"""
E-commerce Customer Auth API — login, password reset, brand-aware.
"""
import json
import secrets
from datetime import timedelta
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.http import JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from apps.core.models import Company
from .models import CustomerStoreAccount, CustomerBrandProfile


from django.conf import settings as _settings

def _brand_reset_base(brand_key):
    env_key = f'BRAND_RESET_URL_{brand_key.upper()}'
    default = 'http://localhost:5173/siecle' if brand_key == 'siecle' else 'http://localhost:5174/lunea'
    return getattr(_settings, env_key, default)

BRAND_EMAIL_SUBJECTS = {
    'siecle': 'SIÈCLE — Réinitialisation de votre mot de passe',
    'lunea': 'LUNEA — Réinitialisation de votre mot de passe',
}


def _json(request):
    try:
        return json.loads(request.body)
    except Exception:
        return {}


def _get_company(request):
    return getattr(request, 'current_company', None) or Company.objects.filter(is_active=True).first()


@method_decorator(csrf_exempt, name='dispatch')
class CustomerLoginView(View):
    def post(self, request):
        data = _json(request)
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        brand_key = data.get('brand_key') or getattr(request, 'brand_key', 'siecle')
        remember_me = data.get('remember_me', False)
        company = _get_company(request)

        if not email or not password:
            return JsonResponse({'error': 'Email et mot de passe requis.'}, status=400)

        try:
            account = CustomerStoreAccount.objects.get(company=company, email=email)
        except CustomerStoreAccount.DoesNotExist:
            return JsonResponse({'error': 'Identifiants incorrects.'}, status=401)

        if not account.user:
            return JsonResponse({'error': 'Compte non activé.'}, status=403)

        user = authenticate(request, username=account.user.username, password=password)
        if not user:
            return JsonResponse({'error': 'Identifiants incorrects.'}, status=401)

        login(request, user)

        if not remember_me:
            request.session.set_expiry(0)

        account.last_login = timezone.now()
        account.save(update_fields=['last_login'])

        brand_profile = CustomerBrandProfile.get_or_create_for(account, brand_key)

        redirect_path = f'/{brand_key}/compte/'

        return JsonResponse({
            'status': 'ok',
            'customer': {
                'email': account.email,
                'first_name': account.first_name,
                'last_name': account.last_name,
                'brand_key': brand_key,
            },
            'theme': brand_profile.preferred_theme,
            'language': brand_profile.preferred_language,
            'redirect': redirect_path,
        })

    def delete(self, request):
        logout(request)
        brand_key = getattr(request, 'brand_key', 'siecle')
        return JsonResponse({'status': 'ok', 'redirect': f'/{brand_key}/'})


@method_decorator(csrf_exempt, name='dispatch')
class CustomerPasswordResetRequestView(View):
    def post(self, request):
        data = _json(request)
        email = data.get('email', '').strip().lower()
        brand_key = data.get('brand_key') or getattr(request, 'brand_key', 'siecle')
        company = _get_company(request)

        # Always return 200 to not reveal if email exists
        response_msg = 'Si un compte existe avec cet email, vous recevrez un lien de réinitialisation.'

        try:
            account = CustomerStoreAccount.objects.get(company=company, email=email)
            if account.user:
                token = secrets.token_urlsafe(32)
                # Store token in session-like field (simple approach)
                account.user.password_reset_tokens if hasattr(account.user, 'password_reset_tokens') else None

                # Use Django's built-in token via cache or a simple model
                from django.core.cache import cache
                cache_key = f'pwd_reset:{token}'
                cache.set(cache_key, {'user_id': account.user.pk, 'brand_key': brand_key}, timeout=3600)

                base_url = _brand_reset_base(brand_key)
                reset_link = f'{base_url}/reset-password/{token}/'
                subject = BRAND_EMAIL_SUBJECTS.get(brand_key, 'Réinitialisation de mot de passe')

                brand_display = 'SIÈCLE' if brand_key == 'siecle' else 'LUNEA'
                send_mail(
                    subject=subject,
                    message=f'{brand_display} — Réinitialisation\n\nCliquez ici : {reset_link}\nCe lien expire dans 1 heure.',
                    from_email=f'no-reply@{brand_key}.fr',
                    recipient_list=[email],
                    fail_silently=True,
                )
        except CustomerStoreAccount.DoesNotExist:
            pass

        return JsonResponse({'status': 'ok', 'message': response_msg})


@method_decorator(csrf_exempt, name='dispatch')
class CustomerPasswordResetConfirmView(View):
    def post(self, request):
        data = _json(request)
        token = data.get('token', '')
        password = data.get('password', '')
        brand_key = data.get('brand_key') or getattr(request, 'brand_key', 'siecle')

        if not token or not password or len(password) < 8:
            return JsonResponse({'error': 'Token ou mot de passe invalide.'}, status=400)

        from django.core.cache import cache
        cache_key = f'pwd_reset:{token}'
        cached = cache.get(cache_key)

        if not cached:
            return JsonResponse({'error': 'Lien expiré ou invalide.'}, status=400)

        try:
            user = User.objects.get(pk=cached['user_id'])
            user.set_password(password)
            user.save()
            cache.delete(cache_key)
            return JsonResponse({'status': 'ok', 'redirect': f'/{brand_key}/login/'})
        except User.DoesNotExist:
            return JsonResponse({'error': 'Compte introuvable.'}, status=400)


@method_decorator(csrf_exempt, name='dispatch')
class CustomerBrandProfileView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Non authentifié.'}, status=401)

        brand_key = request.GET.get('brand') or getattr(request, 'brand_key', 'siecle')
        company = _get_company(request)

        try:
            account = CustomerStoreAccount.objects.get(company=company, user=request.user)
            profile = CustomerBrandProfile.get_or_create_for(account, brand_key)
            return JsonResponse({
                'brand_key': profile.brand_key,
                'preferred_theme': profile.preferred_theme,
                'preferred_language': profile.preferred_language,
                'animations_enabled': profile.animations_enabled,
                'display_density': profile.display_density,
                'newsletter_optin': profile.newsletter_optin,
                'marketing_optin': profile.marketing_optin,
            })
        except CustomerStoreAccount.DoesNotExist:
            return JsonResponse({'error': 'Compte introuvable.'}, status=404)

    def patch(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Non authentifié.'}, status=401)

        data = _json(request)
        brand_key = data.get('brand_key') or request.GET.get('brand') or getattr(request, 'brand_key', 'siecle')
        company = _get_company(request)

        try:
            account = CustomerStoreAccount.objects.get(company=company, user=request.user)
            profile = CustomerBrandProfile.get_or_create_for(account, brand_key)

            allowed = ['preferred_theme', 'preferred_language', 'animations_enabled',
                       'display_density', 'newsletter_optin', 'marketing_optin']
            for field in allowed:
                if field in data:
                    setattr(profile, field, data[field])
            profile.save()

            return JsonResponse({'status': 'ok', 'preferred_theme': profile.preferred_theme})
        except CustomerStoreAccount.DoesNotExist:
            return JsonResponse({'error': 'Compte introuvable.'}, status=404)
