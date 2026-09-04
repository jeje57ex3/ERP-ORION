"""
apps/btp/public_configurator_api.py — API JSON publique du configurateur
NÉOSTRUCTURA (site React, visiteur anonyme).

Contrairement à apps.btp.guided_quote_views (qui dépend de
request.current_company, jamais résolu pour un visiteur anonyme), cette API
résout l'entreprise explicitement par slug — NÉOSTRUCTURA est actuellement
la seule entreprise servie par ce configurateur.

Le moteur de chiffrage reste volontairement simple (des lignes tarifées
piochées dans ElectricityPriceLibrary + main-d'œuvre + déplacement +
majoration urgence + gamme) : une V1 fonctionnelle branchée sur de vraies
données ERP, pas le moteur multi-produits/multi-fournisseurs détaillé du
cahier des charges complet (à construire dans une itération ultérieure).
"""
import json
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from apps.core.models import Company
from apps.crm.models import Customer, Opportunity, Prospect
from .models import GuidedQuoteRequest, GuidedQuoteEstimate, GuidedQuoteEstimateItem, ElectricityPriceLibrary


METIERS = [
    {'slug': 'electricite',   'label': 'Électricité générale'},
    {'slug': 'domotique',     'label': 'Domotique'},
    {'slug': 'etancheite',    'label': 'Étanchéité'},
    {'slug': 'informatique',  'label': 'Informatique & Réseaux'},
    {'slug': 'renovation',    'label': 'Rénovation'},
    {'slug': 'maintenance',   'label': 'Maintenance'},
]

INTERVENTIONS = [
    {'value': 'installation_neuve', 'label': 'Installation neuve'},
    {'value': 'renovation',         'label': 'Rénovation'},
    {'value': 'depannage',          'label': 'Dépannage'},
    {'value': 'mise_normes',        'label': 'Mise aux normes'},
    {'value': 'autre',              'label': "Ajout d'équipements"},
]

# Un métier -> les codes ElectricityPriceLibrary sélectionnables comme
# "matériel / équipement" dans le configurateur (voir
# apps/btp/management/commands/seed_neostructura_pricing.py). Le premier
# code de chaque liste sert de poste par défaut si le visiteur n'a rien
# précisé dans l'étape matériel (compatibilité + rapidité).
METIER_MATERIAL_CODES = {
    'electricite':  ['ELEC-INST', 'ELEC-TAB', 'ELEC-PRISE', 'ELEC-LUM', 'ELEC-NORM'],
    'domotique':    ['DOM-MOD', 'DOM-SEC', 'DOM-HUB'],
    'etancheite':   ['ETAN-TOIT', 'ETAN-REPAR', 'ETAN-ISOL'],
    'informatique': ['IT-RES', 'IT-WIFI', 'IT-BAIE', 'IT-CAM'],
    'renovation':   ['RENO-COMPL', 'RENO-SDB', 'RENO-CUISINE'],
    'maintenance':  ['MAINT-CONTRAT', 'MAINT-PONCT'],
}

QUALITY_LEVELS = [
    {'value': 'standard', 'label': 'Standard', 'desc': 'Matériel fiable, bon rapport qualité/prix', 'multiplier': 1.0},
    {'value': 'premium',  'label': 'Premium',  'desc': 'Marques reconnues, finitions soignées', 'multiplier': 1.25},
    {'value': 'luxe',     'label': 'Luxe / Haut de gamme', 'desc': 'Matériel haut de gamme, sur-mesure', 'multiplier': 1.6},
]
QUALITY_MULTIPLIERS = {q['value']: q['multiplier'] for q in QUALITY_LEVELS}


def _get_neostructura_company():
    return Company.objects.filter(slug='neostructura').first()


@require_GET
def configurator_options(request):
    """Options du configurateur : métiers, interventions, catalogue matériel par métier, gammes."""
    company = _get_neostructura_company()
    all_codes = [c for codes in METIER_MATERIAL_CODES.values() for c in codes]
    price_items = {}
    if company is not None:
        price_items = {
            p.code: p for p in ElectricityPriceLibrary.objects.filter(
                company=company, code__in=all_codes, is_active=True,
            )
        }

    materials = {}
    for slug, codes in METIER_MATERIAL_CODES.items():
        materials[slug] = [
            {
                'code': code,
                'name': price_items[code].name,
                'unit': price_items[code].unit,
                'unit_label': price_items[code].get_unit_display(),
                'price_min': float(price_items[code].price_min),
                'price_avg': float(price_items[code].price_avg),
                'price_max': float(price_items[code].price_max),
            }
            for code in codes if code in price_items
        ]

    return JsonResponse({
        'metiers': METIERS,
        'interventions': INTERVENTIONS,
        'materials': materials,
        'quality_levels': QUALITY_LEVELS,
    })


def _valid_qty(raw_qty):
    try:
        return float(raw_qty) > 0
    except (TypeError, ValueError):
        return False


def _clamp_qty(unit, raw_qty, surface_m2):
    if unit == 'forfait':
        return 1
    try:
        qty = float(raw_qty)
    except (TypeError, ValueError):
        qty = float(surface_m2) if (unit == 'm2' and surface_m2) else 1
    if unit == 'm2':
        return max(1.0, min(qty, 1000.0))
    return max(1, min(round(qty), 100))


def _build_estimate(company, quote_request, metiers, surface_m2, materials, quality_level):
    """Calcule un pré-devis détaillé à partir des métiers, du matériel choisi et
    de la gamme. Voir docstring module."""
    multiplier = QUALITY_MULTIPLIERS.get(quality_level, 1.0)
    items = []
    total_min = total_avg = total_max = 0.0
    duration_hours = 0.0

    all_material_codes = {c for m in metiers for c in METIER_MATERIAL_CODES.get(m, [])}
    codes = ['DEPL', 'MO'] + sorted(all_material_codes)
    price_items = {
        p.code: p for p in ElectricityPriceLibrary.objects.filter(company=company, code__in=codes, is_active=True)
    }

    def add_item(price_item, qty, apply_gamme):
        nonlocal total_min, total_avg, total_max, duration_hours
        mult = multiplier if apply_gamme else 1.0
        pmin, pavg, pmax = float(price_item.price_min) * mult, float(price_item.price_avg) * mult, float(price_item.price_max) * mult
        items.append({'item': price_item, 'qty': qty, 'unit_price_avg': pavg})
        total_min += pmin * qty
        total_avg += pavg * qty
        total_max += pmax * qty
        duration_hours += float(price_item.duration_hours) * qty

    for code in ('DEPL', 'MO'):
        p = price_items.get(code)
        if p:
            add_item(p, 1, apply_gamme=False)

    for m in metiers:
        metier_codes = METIER_MATERIAL_CODES.get(m, [])
        chosen = [c for c in metier_codes if _valid_qty(materials.get(c))]
        if not chosen:
            fallback_code = metier_codes[0] if metier_codes else None
            p = price_items.get(fallback_code) if fallback_code else None
            if p:
                qty = float(surface_m2) if (p.unit == 'm2' and surface_m2) else 1
                add_item(p, qty, apply_gamme=True)
            continue
        for code in chosen:
            p = price_items.get(code)
            if not p:
                continue
            qty = _clamp_qty(p.unit, materials.get(code), surface_m2)
            add_item(p, qty, apply_gamme=True)

    if quote_request.urgency == 'urgent':
        surcharge = round(total_avg * 0.25, 2)
        total_min += surcharge * 0.6
        total_avg += surcharge
        total_max += surcharge * 1.4
    else:
        surcharge = 0

    estimate = GuidedQuoteEstimate.objects.create(
        request=quote_request,
        amount_min_ht=round(total_min, 2),
        amount_avg_ht=round(total_avg, 2),
        amount_max_ht=round(total_max, 2),
        labor_amount=round(total_avg * 0.6, 2),
        materials_amount=round(total_avg * 0.4, 2),
        travel_amount=float(price_items['DEPL'].price_avg) if 'DEPL' in price_items else 0,
        urgency_surcharge=surcharge,
        vat_rate=20,
        total_ttc=round(total_avg * 1.20, 2),
        duration_min_days=round(max(duration_hours / 7, 0.5), 1),
        duration_max_days=round(max(duration_hours / 4, 1), 1),
    )
    for order, it in enumerate(items):
        GuidedQuoteEstimateItem.objects.create(
            estimate=estimate, price_item=it['item'], description=it['item'].name,
            quantity=Decimal(str(it['qty'])), unit=it['item'].unit,
            unit_price_avg=Decimal(str(round(it['unit_price_avg'], 2))), order=order,
        )
    return estimate


def _create_crm_lead(company, quote_request):
    """Crée Customer (requis par BTPQuote) + Prospect/Opportunity (suivi commercial).

    Reprend le pattern déjà établi dans
    apps.websites.electricite_wizard_views._create_crm_lead_from_guided_quote —
    volontairement non bloquant (une erreur CRM ne doit jamais faire échouer
    la soumission publique du configurateur).
    """
    try:
        customer = Customer.objects.create(
            company=company, customer_type='individual',
            name=quote_request.client_full_name or quote_request.client_email,
            contact_name=quote_request.client_full_name,
            email=quote_request.client_email, phone=quote_request.client_phone,
            address=quote_request.address, city=quote_request.city, zip_code=quote_request.zip_code,
            notes=f'Créé automatiquement depuis le configurateur — {quote_request.reference}',
        )
        quote_request.crm_customer_id = customer.pk

        prospect = Prospect.objects.create(
            company=company, name=quote_request.client_full_name,
            contact_name=quote_request.client_full_name,
            email=quote_request.client_email, phone=quote_request.client_phone,
            city=quote_request.city, status='qualified', source='website_neostructura',
            notes=f'Demande {quote_request.get_request_type_display()} — {quote_request.client_notes}',
        )
        quote_request.crm_prospect = prospect

        Opportunity.objects.create(
            company=company, name=f'{quote_request.get_request_type_display()} — {quote_request.reference}',
            prospect=prospect, stage='prospecting', probability=20,
            notes=quote_request.client_notes,
        )
        quote_request.save(update_fields=['crm_customer_id', 'crm_prospect'])
    except Exception:
        pass


@csrf_exempt
@require_POST
def configurator_submit(request):
    """Reçoit le configurateur complet et crée la demande + le pré-devis chiffré."""
    company = _get_neostructura_company()
    if company is None:
        return JsonResponse({'error': 'Configurateur indisponible.'}, status=503)

    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Requête invalide.'}, status=400)

    if data.get('website_url_field'):
        return JsonResponse({'error': 'Requête refusée.'}, status=400)

    metiers = [m for m in (data.get('metiers') or []) if m in METIER_MATERIAL_CODES]
    intervention = data.get('intervention') or 'autre'
    if intervention not in {c['value'] for c in INTERVENTIONS}:
        intervention = 'autre'
    urgency = data.get('urgency') if data.get('urgency') in ('urgent', 'normal', 'flexible') else 'normal'
    quality_level = data.get('quality_level') if data.get('quality_level') in QUALITY_MULTIPLIERS else 'standard'

    allowed_material_codes = {c for m in metiers for c in METIER_MATERIAL_CODES.get(m, [])}
    raw_materials = data.get('materials') or {}
    materials = {
        code: qty for code, qty in raw_materials.items()
        if code in allowed_material_codes and _valid_qty(qty)
    }

    contact = data.get('contact') or {}
    for field in ('first_name', 'last_name', 'email'):
        if not (contact.get(field) or '').strip():
            return JsonResponse({'error': 'Nom, prénom et email sont requis.'}, status=400)

    if not metiers:
        return JsonResponse({'error': 'Sélectionnez au moins un métier.'}, status=400)

    building = data.get('building') or {}
    surface_raw = building.get('surface')
    try:
        surface_m2 = float(surface_raw) if surface_raw not in (None, '') else None
    except (TypeError, ValueError):
        surface_m2 = None

    quote_request = GuidedQuoteRequest.objects.create(
        company=company,
        request_type=intervention,
        urgency=urgency,
        quality_level=quality_level,
        client_first_name=contact.get('first_name', '').strip()[:100],
        client_last_name=contact.get('last_name', '').strip()[:100],
        client_email=contact.get('email', '').strip()[:254],
        client_phone=contact.get('phone', '').strip()[:20],
        address=(building.get('address') or '').strip()[:200],
        zip_code=(building.get('zip_code') or '').strip()[:10],
        city=(building.get('city') or '').strip()[:100],
        property_type=building.get('property_type', '') if building.get('property_type') in
            {'apartment', 'house', 'commercial', 'office', 'workshop', 'building', 'other'} else '',
        surface=str(surface_raw or ''),
        answers={'metiers': metiers, 'surface_m2': surface_m2, 'materials': materials, 'quality_level': quality_level},
        client_notes=(data.get('notes') or '').strip(),
    )

    try:
        estimate = _build_estimate(company, quote_request, metiers, surface_m2, materials, quality_level)
    except ValidationError:
        estimate = None

    _create_crm_lead(company, quote_request)

    return JsonResponse({
        'success': True,
        'reference': quote_request.reference,
        'estimate': {
            'min_ht': float(estimate.amount_min_ht),
            'avg_ht': float(estimate.amount_avg_ht),
            'max_ht': float(estimate.amount_max_ht),
            'total_ttc': float(estimate.total_ttc),
            'duration_min_days': float(estimate.duration_min_days),
            'duration_max_days': float(estimate.duration_max_days),
            'items': [
                {
                    'description': it.description,
                    'quantity': float(it.quantity),
                    'unit': it.unit,
                    'unit_price_avg': float(it.unit_price_avg),
                    'total_avg': float(it.total_avg),
                }
                for it in estimate.items.all()
            ],
        } if estimate else None,
    })
