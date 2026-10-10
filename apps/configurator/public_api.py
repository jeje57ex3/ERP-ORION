"""
apps/configurator/public_api.py — API publique du configurateur métier
NÉOSTRUCTURA (visiteur anonyme). Remplace apps.btp.public_configurator_api
(déplacé dans cette nouvelle app dédiée — cf. audit du 2026-09-12).

Sécurité : rate-limiting par IP (cache Django, pas de nouvelle dépendance),
validation/troncature des réponses libres, honeypot sur la soumission,
AUCUNE donnée interne (marge, coût de revient, hypothèses détaillées de
diagnostic) n'est jamais sérialisée — voir services/engine.py
(_public_estimate_payload) pour la frontière stricte public/interne.

Langue : le contenu dynamique (domaines, prestations, questions, options,
message de sécurité) est traduisible (§ demande utilisateur du
2026-09-12 : « traduit aussi le configurateur »). La langue voulue est
lue sur `?lang=` (GET) ou `lang` (corps JSON des POST), et normalisée via
services/i18n.normalize_language — jamais fait confiance telle quelle.
"""
import json

from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from apps.core.models import Company
from apps.websites.public_views import _get_ip
from .models import ConfiguratorSession, ConfiguratorSessionLot
from .services import engine
from .services.i18n import normalize_language

MAX_ANSWERS_KEYS = 60
MAX_ANSWER_STR_LEN = 2000
MAX_LIST_ITEMS = 50


def _get_neostructura_company():
    return Company.objects.filter(slug='neostructura').first()


def _rate_limited(request, key, limit, window_seconds=3600):
    ip = _get_ip(request)
    cache_key = f'configurator_rl:{key}:{ip}'
    count = cache.get(cache_key, 0)
    if count >= limit:
        return True
    cache.set(cache_key, count + 1, window_seconds)
    return False


def _sanitize_answers(raw):
    """Ne fait jamais confiance au client : borne tailles/types avant que
    quoi que ce soit n'atteigne le moteur de chiffrage."""
    if not isinstance(raw, dict):
        return {}
    clean = {}
    for k, v in list(raw.items())[:MAX_ANSWERS_KEYS]:
        if not isinstance(k, str) or len(k) > 60:
            continue
        if isinstance(v, str):
            clean[k] = v[:MAX_ANSWER_STR_LEN]
        elif isinstance(v, bool) or isinstance(v, (int, float)):
            clean[k] = v
        elif isinstance(v, list):
            clean[k] = [str(x)[:200] for x in v[:MAX_LIST_ITEMS] if isinstance(x, (str, int, float))]
        # dict / None / autres types silencieusement ignorés
    return clean


def _parse_json(request):
    try:
        return json.loads(request.body or '{}'), None
    except json.JSONDecodeError:
        return None, JsonResponse({'error': 'Requête invalide.'}, status=400)


@require_GET
def list_domains(request):
    company = _get_neostructura_company()
    if not company:
        return JsonResponse({'domains': []})
    language = normalize_language(request.GET.get('lang'))
    domains = engine.get_domains(company)
    return JsonResponse({'domains': [engine.domain_payload(d, language) for d in domains]})


@require_GET
def list_services(request, domain_code):
    company = _get_neostructura_company()
    if not company:
        return JsonResponse({'error': 'Configurateur indisponible.'}, status=503)
    language = normalize_language(request.GET.get('lang'))
    domain, services = engine.get_services(company, domain_code)
    if not domain:
        return JsonResponse({'error': 'Domaine introuvable.'}, status=404)
    return JsonResponse({'services': [engine.service_summary_payload(s, language) for s in services]})


@csrf_exempt
@require_POST
def service_questions(request, service_code):
    """POST plutôt que GET : les questions visibles dépendent des réponses
    déjà données (parcours adaptatif), il faut donc les transmettre."""
    company = _get_neostructura_company()
    if not company:
        return JsonResponse({'error': 'Configurateur indisponible.'}, status=503)
    service = engine.get_service(company, service_code)
    if not service:
        return JsonResponse({'error': 'Prestation introuvable.'}, status=404)
    data, error = _parse_json(request)
    if error:
        return error
    answers = _sanitize_answers(data.get('answers'))
    language = normalize_language(data.get('lang'))
    return JsonResponse({'questions': engine.get_questions_payload(service, answers, language)})


@csrf_exempt
@require_POST
def estimate(request):
    """Aperçu live, sans créer de demande — pas de PII requise."""
    company = _get_neostructura_company()
    if not company:
        return JsonResponse({'error': 'Configurateur indisponible.'}, status=503)
    if _rate_limited(request, 'estimate', limit=60):
        return JsonResponse({'error': 'Trop de requêtes, réessayez plus tard.'}, status=429)
    data, error = _parse_json(request)
    if error:
        return error
    answers = _sanitize_answers(data.get('answers'))
    urgency = data.get('urgency') if data.get('urgency') in ('urgent', 'normal', 'flexible') else 'normal'
    language = normalize_language(data.get('lang'))
    result = engine.estimate_preview(company, data.get('service_code', ''), answers, urgency, language)
    if result is None:
        return JsonResponse({'error': 'Prestation introuvable.'}, status=404)
    return JsonResponse(result)


@csrf_exempt
@require_POST
def submit(request):
    company = _get_neostructura_company()
    if not company:
        return JsonResponse({'error': 'Configurateur indisponible.'}, status=503)
    if _rate_limited(request, 'submit', limit=10):
        return JsonResponse({'error': 'Trop de demandes envoyées depuis cette adresse, réessayez plus tard.'}, status=429)
    data, error = _parse_json(request)
    if error:
        return error
    if data.get('website_url_field'):  # honeypot
        return JsonResponse({'error': 'Requête refusée.'}, status=400)

    data['answers'] = _sanitize_answers(data.get('answers'))
    try:
        quote_request, public_estimate = engine.submit_configurator_request(company, data)
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)

    return JsonResponse({'success': True, 'reference': quote_request.reference, 'estimate': public_estimate})


@csrf_exempt
@require_POST
def session_start(request):
    """Crée un dossier de configuration résumable (§4/§50) : le client peut
    quitter et revenir sans compte tant qu'il garde la clé côté navigateur."""
    company = _get_neostructura_company()
    if not company:
        return JsonResponse({'error': 'Configurateur indisponible.'}, status=503)
    if _rate_limited(request, 'session_start', limit=30):
        return JsonResponse({'error': 'Trop de requêtes, réessayez plus tard.'}, status=429)
    data, _err = _parse_json(request)
    language = normalize_language((data or {}).get('lang'))
    session = engine.create_session(company)
    return JsonResponse(engine.session_payload(session, language))


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def session_detail(request, session_key):
    company = _get_neostructura_company()
    if not company:
        return JsonResponse({'error': 'Configurateur indisponible.'}, status=503)
    session = ConfiguratorSession.objects.filter(company=company, session_key=session_key).first()
    if not session:
        return JsonResponse({'error': 'Session introuvable.'}, status=404)

    if request.method == 'GET':
        language = normalize_language(request.GET.get('lang'))
        return JsonResponse(engine.session_payload(session, language))

    if _rate_limited(request, 'session_update', limit=120):
        return JsonResponse({'error': 'Trop de requêtes, réessayez plus tard.'}, status=429)
    data, error = _parse_json(request)
    if error:
        return error
    answers = _sanitize_answers(data.get('answers'))
    urgency = data.get('urgency') if data.get('urgency') in ('urgent', 'normal', 'flexible') else None
    language = normalize_language(data.get('lang'))
    session = engine.update_session(session, data.get('domain_code'), data.get('service_code'), urgency, answers, language)
    return JsonResponse(engine.session_payload(session, language))


@csrf_exempt
@require_POST
def session_lots(request, session_key):
    """Ajoute un lot au dossier (§12-13 : « mode projet », plusieurs besoins
    dans une même session — ex. prises + Wi-Fi + RJ45)."""
    company = _get_neostructura_company()
    if not company:
        return JsonResponse({'error': 'Configurateur indisponible.'}, status=503)
    session = ConfiguratorSession.objects.filter(company=company, session_key=session_key).first()
    if not session:
        return JsonResponse({'error': 'Session introuvable.'}, status=404)
    if _rate_limited(request, 'session_lot_add', limit=40):
        return JsonResponse({'error': 'Trop de requêtes, réessayez plus tard.'}, status=429)
    data, error = _parse_json(request)
    if error:
        return error
    answers = _sanitize_answers(data.get('answers'))
    urgency = data.get('urgency') if data.get('urgency') in ('urgent', 'normal', 'flexible') else 'normal'
    label = (data.get('label') or '')[:150]
    language = normalize_language(data.get('lang'))
    engine.add_lot(session, data.get('domain_code'), data.get('service_code'), urgency, answers, label=label, language=language)
    return JsonResponse(engine.session_payload(session, language), status=201)


@csrf_exempt
@require_http_methods(['POST', 'DELETE'])
def session_lot_detail(request, session_key, lot_id):
    company = _get_neostructura_company()
    if not company:
        return JsonResponse({'error': 'Configurateur indisponible.'}, status=503)
    session = ConfiguratorSession.objects.filter(company=company, session_key=session_key).first()
    if not session:
        return JsonResponse({'error': 'Session introuvable.'}, status=404)
    lot = ConfiguratorSessionLot.objects.filter(session=session, pk=lot_id).first()
    if not lot:
        return JsonResponse({'error': 'Lot introuvable.'}, status=404)

    if request.method == 'DELETE':
        language = normalize_language(request.GET.get('lang'))
        engine.remove_lot(session, lot_id)
        return JsonResponse(engine.session_payload(session, language))

    if _rate_limited(request, 'session_lot_update', limit=120):
        return JsonResponse({'error': 'Trop de requêtes, réessayez plus tard.'}, status=429)
    data, error = _parse_json(request)
    if error:
        return error
    answers = _sanitize_answers(data.get('answers'))
    urgency = data.get('urgency') if data.get('urgency') in ('urgent', 'normal', 'flexible') else None
    label = data.get('label') if isinstance(data.get('label'), str) else None
    language = normalize_language(data.get('lang'))
    engine.update_lot(lot, data.get('domain_code'), data.get('service_code'), urgency, answers, label=label, language=language)
    return JsonResponse(engine.session_payload(session, language))


@csrf_exempt
@require_POST
def submit_project(request):
    """Soumet en une fois tous les lots d'un dossier « mode projet »."""
    company = _get_neostructura_company()
    if not company:
        return JsonResponse({'error': 'Configurateur indisponible.'}, status=503)
    if _rate_limited(request, 'submit_project', limit=10):
        return JsonResponse({'error': 'Trop de demandes envoyées depuis cette adresse, réessayez plus tard.'}, status=429)
    data, error = _parse_json(request)
    if error:
        return error
    if data.get('website_url_field'):  # honeypot
        return JsonResponse({'error': 'Requête refusée.'}, status=400)

    try:
        quote_requests, summary = engine.submit_configurator_project(company, data)
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)

    return JsonResponse({
        'success': True,
        'references': [qr.reference for qr in quote_requests],
        'project': summary,
    })


@csrf_exempt
@require_POST
def upload_photo(request, reference):
    company = _get_neostructura_company()
    if not company:
        return JsonResponse({'error': 'Configurateur indisponible.'}, status=503)
    if _rate_limited(request, 'upload', limit=20):
        return JsonResponse({'error': 'Trop de fichiers envoyés, réessayez plus tard.'}, status=429)

    from apps.btp.models import GuidedQuoteRequest, GuidedQuotePhoto
    quote_request = GuidedQuoteRequest.objects.filter(company=company, reference=reference).first()
    if not quote_request:
        return JsonResponse({'error': 'Demande introuvable.'}, status=404)

    files = request.FILES.getlist('photos')
    if not files:
        return JsonResponse({'error': 'Aucun fichier reçu.'}, status=400)

    allowed_types = {'image/jpeg', 'image/png', 'image/webp', 'image/heic'}
    max_size = 8 * 1024 * 1024
    saved = 0
    for f in files[:5]:
        if f.content_type not in allowed_types or f.size > max_size:
            continue
        GuidedQuotePhoto.objects.create(request=quote_request, photo=f)
        saved += 1

    if not saved:
        return JsonResponse({'error': 'Aucun fichier valide (JPEG/PNG/WEBP/HEIC, 8 Mo max).'}, status=400)
    return JsonResponse({'success': True, 'saved': saved})
