import json
from django.core.mail import mail_admins
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import WaitlistSubscriber, ContactMessage


def _parse_json(request):
    try:
        return json.loads(request.body.decode('utf-8'))
    except Exception:
        return {}


@csrf_exempt
@require_POST
def waitlist_subscribe(request):
    payload = _parse_json(request)

    email = payload.get('email', '').strip().lower()
    brand_key = payload.get('brand_key', '').strip()
    feature_key = payload.get('feature_key', 'general').strip() or 'general'

    if not email or brand_key not in ('siecle', 'lunea'):
        return JsonResponse({'error': 'invalid_payload'}, status=400)

    _, created = WaitlistSubscriber.objects.get_or_create(
        brand_key=brand_key,
        feature_key=feature_key,
        email=email,
        defaults={
            'ip_address': request.META.get('REMOTE_ADDR'),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
        },
    )

    return JsonResponse({'ok': True, 'created': created})


@csrf_exempt
@require_POST
def contact_submit(request):
    payload = _parse_json(request)

    # Honeypot anti-spam
    if payload.get('website', ''):
        return JsonResponse({'ok': True})

    brand_key = payload.get('brand_key', '').strip()
    name = payload.get('name', '').strip()[:180]
    email = payload.get('email', '').strip().lower()
    subject = payload.get('subject', '').strip()[:180]
    message = payload.get('message', '').strip()

    if not all([brand_key, name, email, subject, message]):
        return JsonResponse({'error': 'missing_fields'}, status=400)

    if brand_key not in ('siecle', 'lunea'):
        return JsonResponse({'error': 'invalid_brand'}, status=400)

    msg = ContactMessage.objects.create(
        brand_key=brand_key,
        name=name,
        email=email,
        subject=subject,
        message=message,
        ip_address=request.META.get('REMOTE_ADDR'),
    )

    try:
        brand_label = 'LUNEA' if brand_key == 'lunea' else 'SIÈCLE'
        mail_admins(
            subject=f'[{brand_label}] Nouveau message : {subject}',
            message=f'De : {name} <{email}>\n\n{message}',
            fail_silently=True,
        )
    except Exception:
        pass

    return JsonResponse({'ok': True, 'id': msg.pk})
