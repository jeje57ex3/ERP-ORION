"""
apps/configurator/services/engine.py — Orchestration : c'est le SEUL point
d'entrée que les vues publiques doivent appeler. Compose diagnostic.py,
pricing.py et crm_sync.py ; décide ce qui est renvoyé au client (jamais la
marge, le coût de revient, ni les hypothèses de diagnostic détaillées —
voir §18 vs §19 du cahier des charges) et ce qui reste interne
(ConfiguratorSubmission).
"""
from decimal import Decimal

from django.utils import timezone

from apps.btp.models import GuidedQuoteRequest, GuidedQuoteEstimate, GuidedQuoteEstimateItem, BTPQuote, BTPQuoteLine
from apps.configurator.models import ServiceDomain, ServiceCategory, ConfiguratorSubmission, ConfiguratorSession
from .diagnostic import get_visible_questions
from .pricing import compute_estimate
from .crm_sync import sync_crm_lead
from .confidence import missing_info_from_answers

VALID_PROPERTY_TYPES = {'apartment', 'house', 'commercial', 'office', 'workshop', 'building', 'other'}


def get_domains(company):
    return ServiceDomain.objects.filter(company=company, is_active=True).order_by('order')


def get_services(company, domain_code):
    domain = ServiceDomain.objects.filter(company=company, code=domain_code, is_active=True).first()
    if not domain:
        return None, []
    return domain, list(domain.categories.filter(is_active=True).order_by('order'))


def get_service(company, service_code):
    return ServiceCategory.objects.filter(
        domain__company=company, code=service_code, is_active=True, domain__is_active=True,
    ).select_related('domain').first()


def get_questions_payload(service, answers):
    """Questions actuellement visibles compte tenu des réponses déjà
    données (le client peut en révéler d'autres au fur et à mesure)."""
    questions = get_visible_questions(service, answers or {})
    return [
        {
            'identifier': q.identifier,
            'label': q.label,
            'help_text': q.help_text,
            'type': q.question_type,
            'required': q.is_required,
            'allow_dont_know': q.allow_dont_know,
            'options': [{'value': o.value, 'label': o.label} for o in q.options.all()],
        }
        for q in questions
    ]


def _public_estimate_payload(estimate):
    """Ne renvoie QUE ce que le client doit voir — jamais costs/margin brut."""
    payload = {
        'confidence_level': estimate['confidence_level'],
        'visit_necessity': estimate['visit_necessity'],
        'requires_diagnostic': estimate['requires_diagnostic'],
        'danger_detected': estimate['danger_detected'],
        'duration': estimate['duration'],
    }
    if estimate['danger_detected'] and estimate.get('safety_message'):
        payload['safety_message'] = estimate['safety_message']
    if estimate['requires_diagnostic']:
        payload['diagnostic_price_from'] = estimate.get('diagnostic_price_from')
        payload['intervention_estimate'] = {
            'min': estimate['price']['min'], 'max': estimate['price']['max'],
        }
    else:
        payload['price'] = estimate['price']
    return payload


def estimate_preview(company, service_code, answers, urgency='normal'):
    """Estimation live, sans créer de demande — pour l'aperçu progressif
    côté configurateur (§28)."""
    service = get_service(company, service_code)
    if not service:
        return None
    estimate = compute_estimate(company, service, answers or {}, urgency)
    return _public_estimate_payload(estimate)


def _create_estimate_items(estimate_obj, estimate, hourly_rate, travel_amount):
    order = 0
    if travel_amount:
        GuidedQuoteEstimateItem.objects.create(
            estimate=estimate_obj, description='Frais de déplacement', quantity=Decimal('1'),
            unit='forfait', unit_price_avg=Decimal(str(round(travel_amount, 2))), order=order,
        )
        order += 1
    if estimate['costs']['labor_avg']:
        GuidedQuoteEstimateItem.objects.create(
            estimate=estimate_obj, description="Main-d'œuvre", quantity=Decimal(str(estimate['duration']['avg'])),
            unit='h', unit_price_avg=Decimal(str(hourly_rate)), order=order,
        )
        order += 1
    for line in estimate['material_lines']:
        item = line['price_item']
        GuidedQuoteEstimateItem.objects.create(
            estimate=estimate_obj, price_item=item, description=item.name,
            quantity=Decimal(str(line['qty'])), unit=item.unit,
            unit_price_avg=item.price_avg, order=order,
        )
        order += 1


def _create_draft_quote(company, quote_request, estimate_obj):
    if not quote_request.crm_customer_id:
        return None
    from apps.core.numbering import next_number
    quote = BTPQuote.objects.create(
        company=company, customer_id=quote_request.crm_customer_id,
        number=next_number(company, 'quote') or '',
        subject=f'Devis suite demande {quote_request.reference}',
        status='draft', validity_date=timezone.now().date(),
        notes=f'Généré automatiquement depuis le configurateur ({quote_request.reference}). '
              f'Confiance suffisante pour un brouillon direct — à vérifier avant envoi.',
    )
    for order, item in enumerate(estimate_obj.items.all().order_by('order')):
        BTPQuoteLine.objects.create(
            quote=quote, description=item.description, unit=item.unit,
            quantity=item.quantity, unit_price=item.unit_price_avg,
            total_ht=item.total_avg, order=order,
        )
    quote.total_ht = estimate_obj.amount_avg_ht
    quote.total_tva = round(float(estimate_obj.amount_avg_ht) * 0.20, 2)
    quote.total_ttc = estimate_obj.total_ttc
    quote.save(update_fields=['total_ht', 'total_tva', 'total_ttc'])
    quote_request.btp_quote = quote
    quote_request.status = 'quote_created'
    quote_request.save(update_fields=['btp_quote', 'status'])
    return quote


def submit_configurator_request(company, payload):
    """Point d'entrée unique appelé par la vue publique. `payload` :
    {domain_code, service_code, urgency, answers, contact{}, building{}, notes}
    Retourne (quote_request, public_estimate_dict) ou lève ValueError si les
    données sont invalides (la vue traduit en 400)."""
    service = get_service(company, payload.get('service_code', ''))
    if not service:
        raise ValueError('Prestation introuvable.')

    contact = payload.get('contact') or {}
    for field in ('first_name', 'last_name', 'email'):
        if not (contact.get(field) or '').strip():
            raise ValueError('Nom, prénom et email sont requis.')

    answers = payload.get('answers') or {}
    if not isinstance(answers, dict):
        raise ValueError('Réponses invalides.')
    urgency = payload.get('urgency') if payload.get('urgency') in ('urgent', 'normal', 'flexible') else 'normal'
    building = payload.get('building') or {}
    property_type = building.get('property_type') if building.get('property_type') in VALID_PROPERTY_TYPES else ''

    estimate = compute_estimate(company, service, answers, urgency)

    quote_request = GuidedQuoteRequest.objects.create(
        company=company,
        request_type=service.intervention_type,
        urgency=urgency,
        client_first_name=contact.get('first_name', '').strip()[:100],
        client_last_name=contact.get('last_name', '').strip()[:100],
        client_email=contact.get('email', '').strip()[:254],
        client_phone=contact.get('phone', '').strip()[:20],
        address=(building.get('address') or '').strip()[:200],
        zip_code=(building.get('zip_code') or '').strip()[:10],
        city=(building.get('city') or '').strip()[:100],
        property_type=property_type,
        surface=str(answers.get('surface') or ''),
        quality_level=answers.get('gamme') if answers.get('gamme') in ('standard', 'premium', 'luxe') else 'standard',
        answers={'domain': service.domain.code, 'service': service.code, **answers},
        client_notes=(payload.get('notes') or '').strip(),
    )

    estimate_obj = GuidedQuoteEstimate.objects.create(
        request=quote_request,
        amount_min_ht=Decimal(str(estimate['price']['min'])),
        amount_avg_ht=Decimal(str(estimate['price']['avg'])),
        amount_max_ht=Decimal(str(estimate['price']['max'])),
        labor_amount=Decimal(str(estimate['costs']['labor_avg'])),
        materials_amount=Decimal(str(estimate['costs']['material_avg'])),
        travel_amount=Decimal(str(estimate['costs']['travel'])),
        urgency_surcharge=Decimal('0'),
        vat_rate=Decimal('20'),
        total_ttc=Decimal(str(estimate['price']['total_ttc_avg'])),
        duration_min_days=round(max(estimate['duration']['min'] / 7, 0.5), 1),
        duration_max_days=round(max(estimate['duration']['max'] / 4, 1), 1),
        complexity_level='complex' if service.requires_diagnostic else 'medium',
    )
    hourly_rate = estimate['costs']['labor_avg'] / estimate['duration']['avg'] if estimate['duration']['avg'] else 0
    _create_estimate_items(estimate_obj, estimate, hourly_rate, estimate['costs']['travel'])

    human_validation_required = (
        estimate['confidence_level'] in ('low', 'diagnostic_required')
        or estimate['danger_detected']
        or estimate['visit_necessity'] == 'obligatoire'
    )
    submission = ConfiguratorSubmission.objects.create(
        request=quote_request, domain=service.domain, service=service,
        confidence_level=estimate['confidence_level'], confidence_score=estimate['confidence_score'],
        visit_necessity=estimate['visit_necessity'],
        diagnostic_required=estimate['requires_diagnostic'],
        hypotheses=estimate['hypotheses'], danger_detected=estimate['danger_detected'],
        missing_info=missing_info_from_answers(service, answers),
        human_validation_required=human_validation_required,
        cost_material=Decimal(str(estimate['costs']['material_avg'])),
        cost_labor=Decimal(str(estimate['costs']['labor_avg'])),
        cost_travel=Decimal(str(estimate['costs']['travel'])),
        cost_price=Decimal(str(estimate['costs']['cost_avg'])),
        margin_percent_applied=Decimal(str(estimate['costs']['margin_percent'])),
        margin_amount=Decimal(str(round(estimate['price']['avg'] - estimate['costs']['cost_avg'], 2))),
        recommended_price=Decimal(str(estimate['price']['avg'])),
        raw_answers_snapshot=answers,
    )

    sync_crm_lead(company, quote_request)

    if not human_validation_required:
        _create_draft_quote(company, quote_request, estimate_obj)
    else:
        quote_request.status = 'to_analyze'
        quote_request.internal_notes = (
            f"Validation humaine requise ({submission.get_confidence_level_display()})."
            + (' Danger détecté.' if estimate['danger_detected'] else '')
        )
        quote_request.save(update_fields=['status', 'internal_notes'])

    session_key = payload.get('session_key')
    if session_key:
        session = ConfiguratorSession.objects.filter(company=company, session_key=session_key).first()
        if session:
            session.submission = submission
            session.status = 'submitted'
            session.save(update_fields=['submission', 'status', 'last_activity_at'])

    return quote_request, _public_estimate_payload(estimate)


# ─── SESSION PERSISTANTE (§4/§50 : reprise du parcours sans compte) ────────────

def create_session(company):
    return ConfiguratorSession.objects.create(company=company)


def session_payload(session):
    """État complet de la session — usage interne à la reprise du parcours
    (jamais de coût/marge, seul `estimate` public est inclus)."""
    payload = {
        'session_key': str(session.session_key),
        'status': session.status,
        'domain_code': session.domain.code if session.domain_id else None,
        'service_code': session.service.code if session.service_id else None,
        'urgency': session.urgency,
        'answers': session.answers,
        'visit_necessity': session.visit_necessity,
        'estimate': None,
    }
    if session.service_id:
        estimate = compute_estimate(session.company, session.service, session.answers or {}, session.urgency or 'normal')
        payload['estimate'] = _public_estimate_payload(estimate)
    return payload


def update_session(session, domain_code, service_code, urgency, answers):
    """Fusionne les nouvelles réponses dans la session et recalcule le score
    de confiance / la nécessité de visite en continu (§36 : ré-estimation
    en temps réel dès qu'une réponse change)."""
    if domain_code:
        domain = ServiceDomain.objects.filter(company=session.company, code=domain_code, is_active=True).first()
        if domain:
            session.domain = domain
    if service_code:
        service = get_service(session.company, service_code)
        if service:
            session.service = service
            if not domain_code:
                session.domain = service.domain
    if urgency in ('urgent', 'normal', 'flexible'):
        session.urgency = urgency
    if answers:
        merged = dict(session.answers or {})
        merged.update(answers)
        session.answers = merged

    if session.service_id:
        estimate = compute_estimate(session.company, session.service, session.answers or {}, session.urgency or 'normal')
        session.confidence_score = estimate['confidence_score']
        session.visit_necessity = estimate['visit_necessity']
        session.missing_info = missing_info_from_answers(session.service, session.answers or {})

    session.save()
    return session
