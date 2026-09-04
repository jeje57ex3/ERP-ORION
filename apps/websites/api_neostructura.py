"""
apps/websites/api_neostructura.py — API JSON publique du site NÉOSTRUCTURA (frontend React).
"""
import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import ContactMessage, Website
from .public_views import _get_ip


def _get_neostructura_site():
    return Website.objects.filter(
        company__slug='neostructura', is_active=True, site_type='btp'
    ).first()


@csrf_exempt
@require_POST
def contact(request):
    """Reçoit le formulaire de contact du site NÉOSTRUCTURA (React, cross-port en dev)."""
    site = _get_neostructura_site()
    if site is None:
        return JsonResponse({'error': 'Site introuvable.'}, status=404)

    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Requête invalide.'}, status=400)

    if data.get('website_url_field'):
        # Honeypot rempli par un bot : on répond succès sans rien enregistrer.
        return JsonResponse({'success': True})

    name = (data.get('name') or '').strip()[:200]
    email = (data.get('email') or '').strip()[:254]
    message = (data.get('message') or '').strip()

    if not name or not email or not message:
        return JsonResponse({'error': 'Nom, email et message sont requis.'}, status=400)

    ContactMessage.objects.create(
        website=site,
        name=name,
        email=email,
        phone=(data.get('phone') or '').strip()[:20],
        subject=(data.get('subject') or '').strip()[:200],
        message=message,
        ip_address=_get_ip(request),
    )
    return JsonResponse({'success': True})
