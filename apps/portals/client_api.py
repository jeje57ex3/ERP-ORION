"""
apps/portals/client_api.py — API JSON de l'espace client NÉOSTRUCTURA (React).

Authentification par token (voir ClientPortalToken), pas par session Django :
le frontend React tourne sur un port séparé en développement (et reste un
processus distinct de Django en production), donc l'auth par cookie de
session + CSRF de apps.portals.client_views n'est pas directement
réutilisable ici. Même principe que SiecleCustomerToken
(apps.ecommerce.api.customer_api), déjà éprouvé dans ce dépôt pour ce
scénario exact.
"""
import json

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from apps.btp.models import BTPProject, ClientNotification, GuidedQuoteRequest
from apps.core.models import Company
from .models import ClientPortalToken


def _get_neostructura_company():
    return Company.objects.filter(slug='neostructura').first()


def _get_token_key(request):
    auth = request.META.get('HTTP_AUTHORIZATION', '')
    if auth.startswith('Token '):
        return auth[6:].strip()
    return request.COOKIES.get('neo_client_token', '')


def _get_account(request):
    """Résout le ClientPortalAccount à partir du token — ou None si invalide."""
    key = _get_token_key(request)
    if not key:
        return None
    token = ClientPortalToken.objects.select_related('user').filter(key=key).first()
    if token is None:
        return None
    return getattr(token.user, 'portal_account', None)


@csrf_exempt
@require_POST
def portal_login(request):
    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Requête invalide.'}, status=400)

    email = (data.get('email') or '').strip()
    password = data.get('password') or ''
    if not email or not password:
        return JsonResponse({'error': 'Email et mot de passe requis.'}, status=400)

    try:
        user_obj = User.objects.get(email=email)
    except User.DoesNotExist:
        return JsonResponse({'error': 'Identifiants incorrects.'}, status=401)

    user = authenticate(request, username=user_obj.username, password=password)
    if not user or not hasattr(user, 'portal_account'):
        return JsonResponse({'error': 'Identifiants incorrects ou compte non autorisé.'}, status=401)

    account = user.portal_account
    account.last_login = timezone.now()
    account.save(update_fields=['last_login'])

    key = ClientPortalToken.generate(user)
    resp = JsonResponse({
        'success': True,
        'token': key,
        'account': {
            'first_name': account.first_name,
            'last_name': account.last_name,
            'email': account.email,
        },
    })
    resp.set_cookie('neo_client_token', key, httponly=True, samesite='Lax', max_age=86400 * 30)
    return resp


@csrf_exempt
@require_POST
def portal_logout(request):
    key = _get_token_key(request)
    if key:
        ClientPortalToken.objects.filter(key=key).delete()
    resp = JsonResponse({'success': True})
    resp.delete_cookie('neo_client_token')
    return resp


@require_GET
def portal_me(request):
    account = _get_account(request)
    if account is None:
        return JsonResponse({'error': 'Non authentifié.'}, status=401)
    return JsonResponse({
        'first_name': account.first_name,
        'last_name': account.last_name,
        'email': account.email,
    })


@require_GET
def portal_dashboard(request):
    account = _get_account(request)
    if account is None:
        return JsonResponse({'error': 'Non authentifié.'}, status=401)

    company = _get_neostructura_company()

    projects = BTPProject.objects.filter(
        company=company, customer__email=account.email,
    ).exclude(status__in=['lost', 'cancelled']).order_by('-start_date')

    requests_qs = GuidedQuoteRequest.objects.filter(
        company=company, client_email=account.email,
    ).order_by('-created_at')[:10]

    notifications = ClientNotification.objects.filter(
        client_email=account.email, is_read=False,
    ).order_by('-created_at')[:10]

    return JsonResponse({
        'account': {'first_name': account.first_name, 'last_name': account.last_name},
        'projects': [
            {
                'id': p.pk, 'name': p.name, 'status': p.status,
                'status_label': p.get_status_display(),
                'city': p.city, 'start_date': p.start_date.isoformat() if p.start_date else None,
                'end_date': p.end_date.isoformat() if p.end_date else None,
            }
            for p in projects
        ],
        'requests': [
            {
                'reference': r.reference, 'status': r.status,
                'status_label': r.get_status_display(),
                'request_type_label': r.get_request_type_display(),
                'created_at': r.created_at.isoformat(),
            }
            for r in requests_qs
        ],
        'notifications': [
            {'id': n.pk, 'title': n.title, 'message': n.message, 'created_at': n.created_at.isoformat()}
            for n in notifications
        ],
    })
