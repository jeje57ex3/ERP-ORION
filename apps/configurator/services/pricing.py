"""
apps/configurator/services/pricing.py — Moteur de chiffrage. Toute règle
financière vit ici (ou dans les modèles qu'il lit) — jamais dans le
frontend. Retourne un dict complet ; c'est l'appelant (engine.py) qui
décide quelle partie est publique et laquelle reste interne (marge, coût
de revient).

Convention légère et documentée plutôt qu'un nouveau modèle de mapping :
- une question d'identifiant "gamme" (valeurs standard/premium/luxe) fait
  basculer chaque matériel vers le produit de la même famille dans cette
  gamme, si elle existe (réutilise ElectricityPriceLibrary.product_family) ;
- une question booléenne dont l'identifiant correspond exactement au
  `code` d'un PricingCoefficient (type "difficulty") l'applique
  automatiquement si la réponse est vraie ;
- une question d'identifiant "zone_deplacement" (valeurs = TravelRule.zone_code)
  sélectionne la zone ; sans elle, la zone par défaut s'applique.
"""
from decimal import Decimal

from django.db.models import Q

from apps.btp.models import ElectricityPriceLibrary
from .conditions import condition_met
from .diagnostic import evaluate_diagnostic
from .confidence import compute_confidence_score, compute_visit_necessity


def resolve_material_lines(service, answers):
    lines = []
    gamme = answers.get('gamme')
    for req in service.material_requirements.select_related('price_item', 'quantity_answer').order_by('order'):
        if not condition_met(req.applies_when, answers):
            continue

        if req.quantity_source == 'fixed':
            qty = float(req.fixed_quantity)
        else:
            identifier = req.quantity_answer.identifier if req.quantity_answer else None
            raw = answers.get(identifier) if identifier else None
            try:
                qty = float(raw or 0) * float(req.quantity_multiplier)
            except (TypeError, ValueError):
                qty = 0
        qty = max(0.0, min(qty, 1000.0))
        if qty <= 0:
            continue

        price_item = req.price_item
        if gamme and price_item.product_family:
            sibling = ElectricityPriceLibrary.objects.filter(
                company=price_item.company, product_family=price_item.product_family,
                quality_level=gamme, is_active=True,
            ).first()
            if sibling:
                price_item = sibling

        lines.append({'price_item': price_item, 'qty': round(qty, 2)})
    return lines


def resolve_labor_rate(company, domain, urgency):
    from apps.configurator.models import LaborRule
    rate_type = 'urgent' if urgency == 'urgent' else 'normal'
    qs = LaborRule.objects.filter(company=company, rate_type=rate_type, is_active=True)
    return (
        qs.filter(domain=domain).first()
        or qs.filter(domain__isnull=True).first()
        or LaborRule.objects.filter(company=company, domain__isnull=True, rate_type='normal', is_active=True).first()
    )


def resolve_travel(company, zone_code, urgency):
    from apps.configurator.models import TravelRule
    qs = TravelRule.objects.filter(company=company, is_active=True)
    rule = qs.filter(zone_code=zone_code).first() if zone_code else None
    return rule or qs.filter(is_default=True).first() or qs.order_by('order').first()


def resolve_margin_percent(company, domain, category):
    from apps.configurator.models import MarginRule
    rule = (
        MarginRule.objects.filter(company=company, scope_type='category', category=category, is_active=True).first()
        or MarginRule.objects.filter(company=company, scope_type='domain', domain=domain, is_active=True).first()
        or MarginRule.objects.filter(company=company, scope_type='global', is_active=True).first()
    )
    if not rule:
        return Decimal('0'), 'aucune règle'
    return rule.margin_percent, str(rule)


def resolve_difficulty_multiplier(company, domain, answers):
    from apps.configurator.models import PricingCoefficient
    multiplier = Decimal('1')
    applied = []
    coefficients = PricingCoefficient.objects.filter(
        company=company, coefficient_type='difficulty', is_active=True,
    ).filter(Q(domain=domain) | Q(domain__isnull=True))
    for coef in coefficients:
        if answers.get(coef.code) in (True, 'true', 'True', 'on', '1', 1):
            multiplier *= coef.multiplier
            applied.append(coef)
    return multiplier, applied


def _build_calculation_log(lines, labor_rule, travel_rule, difficulty_coefs, margin_rule_label, margin_pct):
    """Journal de calcul (§42/§46) : trace lisible des règles appliquées,
    pour comprendre a posteriori pourquoi un prix a été calculé ainsi."""
    log = []
    for line in lines:
        item = line['price_item']
        log.append({'type': 'material', 'code': item.code, 'label': f'{item.name} × {line["qty"]}'})
    if labor_rule:
        log.append({'type': 'labor', 'code': labor_rule.rate_type, 'label': f'{labor_rule.get_rate_type_display()} — {labor_rule.hourly_rate} €/h'})
    if travel_rule:
        log.append({'type': 'travel', 'code': travel_rule.zone_code, 'label': f'{travel_rule.zone_label} — {travel_rule.flat_fee} €'})
    for coef in difficulty_coefs:
        log.append({'type': 'difficulty', 'code': coef.code, 'label': f'{coef.label} (×{coef.multiplier})'})
    log.append({'type': 'margin', 'code': margin_rule_label, 'label': f'Marge {margin_pct}% ({margin_rule_label})'})
    return log


def compute_estimate(company, service, answers, urgency='normal', photos_count=0):
    lines = resolve_material_lines(service, answers)
    material_min = sum(float(l['price_item'].price_min) * l['qty'] for l in lines)
    material_avg = sum(float(l['price_item'].price_avg) * l['qty'] for l in lines)
    material_max = sum(float(l['price_item'].price_max) * l['qty'] for l in lines)

    diag = evaluate_diagnostic(service, answers)

    duration_min = float(service.duration_min_hours)
    duration_avg = float(service.duration_avg_hours)
    duration_max = float(service.duration_max_hours)
    if diag['requires_diagnostic'] and diag['diagnostic_duration']:
        duration_min += diag['diagnostic_duration']['min']
        duration_avg += diag['diagnostic_duration']['avg']
        duration_max += diag['diagnostic_duration']['max']

    labor_rule = resolve_labor_rate(company, service.domain, urgency)
    hourly = float(labor_rule.hourly_rate) if labor_rule else 0
    labor_min, labor_avg, labor_max = duration_min * hourly, duration_avg * hourly, duration_max * hourly

    travel_rule = resolve_travel(company, answers.get('zone_deplacement'), urgency)
    travel = float(travel_rule.flat_fee) if travel_rule else 0
    if urgency == 'urgent' and travel_rule and travel_rule.urgency_surcharge_pct:
        travel *= (1 + float(travel_rule.urgency_surcharge_pct) / 100)

    difficulty_mult_dec, difficulty_coefs = resolve_difficulty_multiplier(company, service.domain, answers)
    difficulty_mult = float(difficulty_mult_dec)

    cost_min = (material_min + labor_min) * difficulty_mult + travel
    cost_avg = (material_avg + labor_avg) * difficulty_mult + travel
    cost_max = (material_max + labor_max) * difficulty_mult + travel

    margin_pct_dec, margin_rule_label = resolve_margin_percent(company, service.domain, service)
    margin_pct = float(margin_pct_dec)
    price_min = cost_min * (1 + margin_pct / 100)
    price_avg = cost_avg * (1 + margin_pct / 100)
    price_max = cost_max * (1 + margin_pct / 100)

    # Largeur supplémentaire selon la prévisibilité de la prestation
    # (estimate_width_pct, réglable par prestation depuis l'admin).
    width = float(service.estimate_width_pct) / 200
    price_min *= (1 - width)
    price_max *= (1 + width)

    confidence_score = compute_confidence_score(
        service, answers, photos_count=photos_count, danger_detected=diag['danger_detected'],
    )
    visit_necessity = compute_visit_necessity(service, confidence_score, diag['danger_detected'])
    calculation_log = _build_calculation_log(lines, labor_rule, travel_rule, difficulty_coefs, margin_rule_label, margin_pct)

    result = {
        'confidence_level': diag['confidence_level'],
        'confidence_score': confidence_score,
        'visit_necessity': visit_necessity,
        'requires_diagnostic': diag['requires_diagnostic'],
        'hypotheses': diag['hypotheses'],
        'danger_detected': diag['danger_detected'],
        'safety_message': diag.get('safety_message', ''),
        'duration': {'min': round(duration_min, 1), 'avg': round(duration_avg, 1), 'max': round(duration_max, 1)},
        'material_lines': lines,
        'calculation_log': calculation_log,
        'costs': {
            'material_avg': round(material_avg, 2), 'labor_avg': round(labor_avg, 2), 'travel': round(travel, 2),
            'cost_min': round(cost_min, 2), 'cost_avg': round(cost_avg, 2), 'cost_max': round(cost_max, 2),
            'margin_percent': margin_pct,
        },
        'price': {
            'min': round(max(price_min, 0), 2), 'avg': round(max(price_avg, 0), 2), 'max': round(max(price_max, 0), 2),
            'total_ttc_avg': round(max(price_avg, 0) * 1.20, 2),
        },
    }

    if diag['requires_diagnostic']:
        diag_hours = diag['diagnostic_duration']['avg'] if diag['diagnostic_duration'] else duration_avg
        diagnostic_price = (travel + diag_hours * hourly) * (1 + margin_pct / 100)
        result['diagnostic_price_from'] = round(max(diagnostic_price, 0), 2)

    return result
