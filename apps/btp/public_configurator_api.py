"""
apps/btp/public_configurator_api.py — API JSON publique du configurateur
NÉOSTRUCTURA (site React, visiteur anonyme).

Contrairement à apps.btp.guided_quote_views (qui dépend de
request.current_company, jamais résolu pour un visiteur anonyme), cette API
résout l'entreprise explicitement par slug — NÉOSTRUCTURA est actuellement
la seule entreprise servie par ce configurateur.

Le moteur de chiffrage est volontairement simple (une ligne représentative
par métier sélectionné + main-d'œuvre + déplacement + majoration urgence) :
une V1 fonctionnelle branchée sur de vraies données ERP (ElectricityPriceLibrary),
pas le moteur multi-produits/multi-gammes détaillé du cahier des charges
complet (à construire dans une itération ultérieure).
"""
import json

from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from apps.core.models import Company
from apps.websites.public_views import _get_ip
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

# Un métier -> les codes ElectricityPriceLibrary représentatifs (voir
# apps/btp/management/commands/seed_neostructura_pricing.py).
METIER_ITEM_CODES = {
    'electricite':  ['ELEC-INST'],
    'domotique':    ['DOM-MOD'],
    'etancheite':   ['ETAN-TOIT'],
    'informatique': ['IT-RES'],
    'renovation':   ['RENO-COMPL'],
    'maintenance':  ['MAINT-CONTRAT'],
}


def _get_neostructura_company():
    return Company.objects.filter(slug='neostructura').first()


@require_GET
def configurator_options(request):
    """Options statiques du configurateur (métiers, types d'intervention)."""
    return JsonResponse({'metiers': METIERS, 'interventions': INTERVENTIONS})


def _build_estimate(company, quote_request, metiers, surface_m2):
    """Calcule un pré-devis à partir des métiers sélectionnés. Voir docstring module."""
    items = []
    total_min = total_avg = total_max = 0.0
    duration_hours = 0.0

    codes = ['DEPL', 'MO']
    for m in metiers:
        codes += METIER_ITEM_CODES.get(m, [])

    price_items = {
        p.code: p for p in ElectricityPriceLibrary.objects.filter(company=company, code__in=codes, is_active=True)
    }

    for code in codes:
        p = price_items.get(code)
        if not p:
            continue
        # Les postes tarifés au m² sont mis à l'échelle par la surface renseignée.
        qty = float(surface_m2) if (p.unit == 'm2' and surface_m2) else 1
        items.append({'item': p, 'qty': qty})
        total_min += float(p.price_min) * qty
        total_avg += float(p.price_avg) * qty
        total_max += float(p.price_max) * qty
        duration_hours += float(p.duration_hours) * qty

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
            quantity=it['qty'], unit=it['item'].unit, unit_price_avg=it['item'].price_avg, order=order,
        )
    return estimate


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

    metiers = [m for m in (data.get('metiers') or []) if m in METIER_ITEM_CODES]
    intervention = data.get('intervention') or 'autre'
    if intervention not in {c['value'] for c in INTERVENTIONS}:
        intervention = 'autre'
    urgency = data.get('urgency') if data.get('urgency') in ('urgent', 'normal', 'flexible') else 'normal'

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
        answers={'metiers': metiers, 'surface_m2': surface_m2},
        client_notes=(data.get('notes') or '').strip(),
    )

    try:
        estimate = _build_estimate(company, quote_request, metiers, surface_m2)
    except ValidationError:
        estimate = None

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
        } if estimate else None,
    })
