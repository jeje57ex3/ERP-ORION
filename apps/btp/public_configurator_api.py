"""
apps/btp/public_configurator_api.py — API JSON publique du configurateur
NÉOSTRUCTURA (site React, visiteur anonyme).

Contrairement à apps.btp.guided_quote_views (qui dépend de
request.current_company, jamais résolu pour un visiteur anonyme), cette API
résout l'entreprise explicitement par slug — NÉOSTRUCTURA est actuellement
la seule entreprise servie par ce configurateur.

Le catalogue "matériel" (étape 2 du configurateur) est lu dynamiquement dans
ElectricityPriceLibrary (champ `metier`, filtré par is_active) — il n'est
donc PAS codé en dur ici : un utilisateur ERP ajoute un nouveau produit ou
une nouvelle gamme (standard/premium/luxe) depuis Bâtiment > Bibliothèque
de prix, et il apparaît immédiatement dans le configurateur public, sans
déploiement. Plusieurs postes partageant le même `product_family` sont
proposés comme des gammes du même équipement (le visiteur choisit le
produit précis, avec son vrai prix — pas de majoration forfaitaire).
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
METIER_SLUGS = {m['slug'] for m in METIERS}

INTERVENTIONS = [
    {'value': 'installation_neuve', 'label': 'Installation neuve'},
    {'value': 'renovation',         'label': 'Rénovation'},
    {'value': 'depannage',          'label': 'Dépannage'},
    {'value': 'mise_normes',        'label': 'Mise aux normes'},
    {'value': 'autre',              'label': "Ajout d'équipements"},
]

QUALITY_LEVELS = [
    {'value': 'standard', 'label': 'Standard'},
    {'value': 'premium', 'label': 'Premium'},
    {'value': 'luxe', 'label': 'Luxe / Haut de gamme'},
]


def _get_neostructura_company():
    return Company.objects.filter(slug='neostructura').first()


def _material_catalog(company):
    """{metier_slug: [{family, options: [...]}]} construit depuis la bibliothèque
    de prix ERP — un même `product_family` regroupe plusieurs gammes."""
    items = ElectricityPriceLibrary.objects.filter(
        company=company, is_active=True, metier__in=METIER_SLUGS,
    ).order_by('metier', 'product_family', 'name', 'quality_level')

    catalog = {m['slug']: {} for m in METIERS}
    for it in items:
        family_key = it.product_family or it.name
        bucket = catalog[it.metier].setdefault(family_key, [])
        bucket.append({
            'code': it.code,
            'name': it.name,
            'unit': it.unit,
            'unit_label': it.get_unit_display(),
            'quality_level': it.quality_level,
            'brand': it.brand,
            'reference': it.reference,
            'price_min': float(it.price_min),
            'price_avg': float(it.price_avg),
            'price_max': float(it.price_max),
        })

    return {
        slug: [{'family': family, 'options': options} for family, options in families.items()]
        for slug, families in catalog.items()
    }


@require_GET
def configurator_options(request):
    """Options du configurateur : métiers, interventions, catalogue matériel (ERP), gammes."""
    company = _get_neostructura_company()
    materials = _material_catalog(company) if company is not None else {m['slug']: [] for m in METIERS}

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


def _build_estimate(company, quote_request, metiers, surface_m2, materials):
    """Calcule un pré-devis détaillé à partir des métiers et du matériel/gamme
    choisis — chaque produit porte son propre prix réel (ERP), il n'y a plus
    de majoration forfaitaire de gamme appliquée en aval. Voir docstring module."""
    catalog = _material_catalog(company)
    items = []
    total_min = total_avg = total_max = 0.0
    duration_hours = 0.0

    all_codes = {opt['code'] for m in metiers for family in catalog.get(m, []) for opt in family['options']}
    price_items = {
        p.code: p for p in ElectricityPriceLibrary.objects.filter(
            company=company, code__in=list(all_codes) + ['DEPL', 'MO'], is_active=True,
        )
    }

    def add_item(price_item, qty):
        nonlocal total_min, total_avg, total_max, duration_hours
        items.append({'item': price_item, 'qty': qty, 'unit_price_avg': float(price_item.price_avg)})
        total_min += float(price_item.price_min) * qty
        total_avg += float(price_item.price_avg) * qty
        total_max += float(price_item.price_max) * qty
        duration_hours += float(price_item.duration_hours) * qty

    for code in ('DEPL', 'MO'):
        p = price_items.get(code)
        if p:
            add_item(p, 1)

    for m in metiers:
        families = catalog.get(m, [])
        any_chosen = False
        for family in families:
            for opt in family['options']:
                if _valid_qty(materials.get(opt['code'])):
                    p = price_items.get(opt['code'])
                    if not p:
                        continue
                    qty = _clamp_qty(opt['unit'], materials.get(opt['code']), surface_m2)
                    add_item(p, qty)
                    any_chosen = True
        if not any_chosen and families:
            # Rien de précisé pour ce métier : poste par défaut (1er de la 1re famille).
            fallback = families[0]['options'][0]
            p = price_items.get(fallback['code'])
            if p:
                qty = float(surface_m2) if (p.unit == 'm2' and surface_m2) else 1
                add_item(p, qty)

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

    metiers = [m for m in (data.get('metiers') or []) if m in METIER_SLUGS]
    intervention = data.get('intervention') or 'autre'
    if intervention not in {c['value'] for c in INTERVENTIONS}:
        intervention = 'autre'
    urgency = data.get('urgency') if data.get('urgency') in ('urgent', 'normal', 'flexible') else 'normal'
    quality_level = data.get('quality_level') if data.get('quality_level') in {q['value'] for q in QUALITY_LEVELS} else 'standard'

    catalog = _material_catalog(company)
    allowed_material_codes = {
        opt['code'] for m in metiers for family in catalog.get(m, []) for opt in family['options']
    }
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
        estimate = _build_estimate(company, quote_request, metiers, surface_m2, materials)
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
