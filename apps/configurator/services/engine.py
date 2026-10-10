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
from apps.configurator.models import (
    ServiceDomain, ServiceCategory, ConfiguratorSubmission, ConfiguratorSession, ConfiguratorSessionLot,
)
from .diagnostic import get_visible_questions
from .pricing import compute_estimate
from .crm_sync import sync_crm_lead
from .confidence import missing_info_from_answers
from .i18n import overlay, normalize_language

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


def domain_payload(domain, language='fr'):
    tr = overlay(domain, language, ['name', 'description'])
    return {'code': domain.code, 'name': tr['name'], 'icon': domain.icon, 'description': tr['description']}


def service_summary_payload(service, language='fr'):
    tr = overlay(service, language, ['name', 'short_description'])
    return {
        'code': service.code, 'name': tr['name'], 'short_description': tr['short_description'],
        'requires_diagnostic': service.requires_diagnostic,
    }


def get_questions_payload(service, answers, language='fr'):
    """Questions actuellement visibles compte tenu des réponses déjà
    données (le client peut en révéler d'autres au fur et à mesure).
    `language` traduit label/help_text/options — voir services/i18n.py."""
    questions = get_visible_questions(service, answers or {})
    payload = []
    for q in questions:
        tr = overlay(q, language, ['label', 'help_text'])
        payload.append({
            'identifier': q.identifier,
            'label': tr['label'],
            'help_text': tr['help_text'],
            'type': q.question_type,
            'required': q.is_required,
            'allow_dont_know': q.allow_dont_know,
            'options': [
                {'value': o.value, 'label': overlay(o, language, ['label'])['label']}
                for o in q.options.all()
            ],
        })
    return payload


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


def estimate_preview(company, service_code, answers, urgency='normal', language='fr'):
    """Estimation live, sans créer de demande — pour l'aperçu progressif
    côté configurateur (§28)."""
    service = get_service(company, service_code)
    if not service:
        return None
    estimate = compute_estimate(company, service, answers or {}, urgency, language=language)
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


def _process_submission(company, service, answers, urgency, contact, building, notes, session=None, language='fr'):
    """Cœur partagé de la soumission : chiffrage, création de la demande
    BTP, du résumé interne, synchronisation CRM et devis brouillon éventuel.
    Utilisé aussi bien par une soumission simple (`submit_configurator_request`)
    que par chaque lot d'un dossier « mode projet » (`submit_configurator_project`)
    — §12-14 : un même moteur pour les deux, pas de logique dupliquée par lot."""
    estimate = compute_estimate(company, service, answers, urgency, language=language)
    property_type = building.get('property_type') if building.get('property_type') in VALID_PROPERTY_TYPES else ''

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
        client_notes=notes.strip(),
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
        request=quote_request, domain=service.domain, service=service, session=session,
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
        calculation_log=estimate['calculation_log'],
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

    return quote_request, submission, estimate


def submit_configurator_request(company, payload):
    """Point d'entrée « mode rapide » (§15) appelé par la vue publique.
    `payload` : {service_code, urgency, answers, contact{}, building{}, notes}
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

    session_key = payload.get('session_key')
    session = ConfiguratorSession.objects.filter(company=company, session_key=session_key).first() if session_key else None
    language = normalize_language(payload.get('lang'))

    quote_request, submission, estimate = _process_submission(
        company, service, answers, urgency, contact, building, payload.get('notes') or '',
        session=session, language=language,
    )

    if session:
        session.status = 'submitted'
        session.save(update_fields=['status', 'last_activity_at'])

    return quote_request, _public_estimate_payload(estimate)


def submit_configurator_project(company, payload):
    """Point d'entrée « mode projet » (§12-14) : soumet TOUS les lots d'une
    session en une fois. `payload` : {session_key, contact{}, building{}, notes}
    Chaque lot produit sa propre `GuidedQuoteRequest`/`ConfiguratorSubmission`
    (on ne restructure pas ces modèles historiques pour porter du multi-lot,
    §7) mais toutes partagent `submission.session` — c'est ce qui permet de
    les retrouver comme un seul dossier côté CRM/BTP.
    Retourne (liste_de_quote_requests, résumé_public_agrégé)."""
    session_key = payload.get('session_key')
    session = ConfiguratorSession.objects.filter(company=company, session_key=session_key).first() if session_key else None
    if not session:
        raise ValueError('Session introuvable.')

    lots = list(session.lots.select_related('service', 'service__domain').all())
    lots = [lot for lot in lots if lot.service_id]
    if not lots:
        raise ValueError('Aucun lot à soumettre.')

    contact = payload.get('contact') or {}
    for field in ('first_name', 'last_name', 'email'):
        if not (contact.get(field) or '').strip():
            raise ValueError('Nom, prénom et email sont requis.')
    building = payload.get('building') or {}
    notes = payload.get('notes') or ''
    language = normalize_language(payload.get('lang'))

    quote_requests = []
    lot_summaries = []
    for lot in lots:
        quote_request, submission, estimate = _process_submission(
            company, lot.service, lot.answers or {}, lot.urgency or 'normal',
            contact, building, notes, session=session, language=language,
        )
        quote_requests.append(quote_request)
        lot_summaries.append({
            'label': lot.label or lot.service.name,
            'reference': quote_request.reference,
            'estimate': _public_estimate_payload(estimate),
        })

    session.status = 'submitted'
    session.save(update_fields=['status', 'last_activity_at'])

    return quote_requests, {'lots': lot_summaries, 'totals': _aggregate_public_totals(lot_summaries)}


# ─── SESSION PERSISTANTE (§4/§50 : reprise du parcours sans compte) ────────────

def create_session(company):
    return ConfiguratorSession.objects.create(company=company)


def session_payload(session, language='fr'):
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
        'lots': [],
        'totals': None,
    }
    if session.service_id:
        estimate = compute_estimate(session.company, session.service, session.answers or {}, session.urgency or 'normal', language=language)
        payload['estimate'] = _public_estimate_payload(estimate)

    lots = list(session.lots.select_related('domain', 'service').order_by('order', 'created_at'))
    payload['lots'] = [lot_payload(lot, language) for lot in lots]
    ready_lots = [lot for lot in payload['lots'] if lot['estimate'] is not None]
    if ready_lots:
        payload['totals'] = _aggregate_public_totals(ready_lots)
    return payload


def update_session(session, domain_code, service_code, urgency, answers, language='fr'):
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
        estimate = compute_estimate(session.company, session.service, session.answers or {}, session.urgency or 'normal', language=language)
        session.confidence_score = estimate['confidence_score']
        session.visit_necessity = estimate['visit_necessity']
        session.missing_info = missing_info_from_answers(session.service, session.answers or {})

    session.save()
    return session


# ─── LOTS (§12-13 : « mode projet », plusieurs besoins dans un même dossier) ───

def lot_payload(lot, language='fr'):
    payload = {
        'id': lot.id, 'label': lot.label,
        'domain_code': lot.domain.code if lot.domain_id else None,
        'service_code': lot.service.code if lot.service_id else None,
        'urgency': lot.urgency, 'answers': lot.answers,
        'visit_necessity': lot.visit_necessity,
        'estimate': None,
    }
    if lot.service_id:
        estimate = compute_estimate(lot.session.company, lot.service, lot.answers or {}, lot.urgency or 'normal', language=language)
        payload['estimate'] = _public_estimate_payload(estimate)
    return payload


def update_lot(lot, domain_code, service_code, urgency, answers, label=None, language='fr'):
    if label is not None:
        lot.label = label[:150]
    if domain_code:
        domain = ServiceDomain.objects.filter(company=lot.session.company, code=domain_code, is_active=True).first()
        if domain:
            lot.domain = domain
    if service_code:
        service = get_service(lot.session.company, service_code)
        if service:
            lot.service = service
            if not domain_code:
                lot.domain = service.domain
    if urgency in ('urgent', 'normal', 'flexible'):
        lot.urgency = urgency
    if answers:
        merged = dict(lot.answers or {})
        merged.update(answers)
        lot.answers = merged

    if lot.service_id:
        estimate = compute_estimate(lot.session.company, lot.service, lot.answers or {}, lot.urgency or 'normal', language=language)
        lot.confidence_score = estimate['confidence_score']
        lot.visit_necessity = estimate['visit_necessity']
        lot.missing_info = missing_info_from_answers(lot.service, lot.answers or {})

    lot.save()
    return lot


def add_lot(session, domain_code, service_code, urgency, answers, label='', language='fr'):
    next_order = session.lots.count()
    lot = ConfiguratorSessionLot.objects.create(session=session, order=next_order)
    return update_lot(lot, domain_code, service_code, urgency, answers, label=label, language=language)


def remove_lot(session, lot_id):
    ConfiguratorSessionLot.objects.filter(session=session, pk=lot_id).delete()


def _aggregate_public_totals(lot_payloads):
    """Agrège les estimations publiques de plusieurs lots en un total global
    (§13). Un seul lot en diagnostic obligatoire suffit à rendre le total
    non ferme ; la nécessité de visite globale est la plus stricte des lots."""
    visit_rank = {'non_necessaire': 0, 'recommandee': 1, 'obligatoire': 2}
    total_min = total_max = total_ttc_avg = duration_min = duration_max = 0.0
    any_diagnostic = False
    worst_visit = 'non_necessaire'

    for entry in lot_payloads:
        est = entry['estimate']
        if est.get('requires_diagnostic'):
            any_diagnostic = True
            total_min += est.get('diagnostic_price_from') or 0
            total_max += (est.get('intervention_estimate') or {}).get('max', 0)
        else:
            price = est.get('price') or {}
            total_min += price.get('min', 0)
            total_max += price.get('max', 0)
            total_ttc_avg += price.get('total_ttc_avg', 0)
        duration = est.get('duration') or {}
        duration_min += duration.get('min', 0)
        duration_max += duration.get('max', 0)
        visit = est.get('visit_necessity', 'non_necessaire')
        if visit_rank.get(visit, 0) > visit_rank.get(worst_visit, 0):
            worst_visit = visit

    return {
        'price_min': round(total_min, 2), 'price_max': round(total_max, 2),
        'total_ttc_avg': round(total_ttc_avg, 2),
        'duration_min': round(duration_min, 1), 'duration_max': round(duration_max, 1),
        'any_diagnostic_required': any_diagnostic,
        'visit_necessity': worst_visit,
    }
