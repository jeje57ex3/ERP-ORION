"""
apps/btp/travel_costs.py — Frais de déplacement du devis guidé.

Remplace le forfait codé en dur (50 € pour un dépannage, 0 € sinon) par un
calcul réel : distance entreprise → chantier × 2 (aller-retour) × consommation
du véhicule × prix du carburant, tout paramétré par entreprise
(CompanySettings, page « Frais de déplacement » de l'ERP).

Fail-safe : si le géocodage échoue (réseau coupé, adresse introuvable) ou si
les paramètres sont incomplets, on renvoie une distance et un montant nuls —
l'estimation reste produite, le déplacement sera simplement chiffré à la main.
"""
from decimal import Decimal

from apps.core.geocoding import geocode, road_distance_km


def _settings_for(company):
    return getattr(company, 'settings', None)


def _base_coordinates(company, settings_obj):
    """Coordonnées du point de départ, géocodées puis mises en cache sur les
    paramètres de l'entreprise (une seule résolution réseau par adresse)."""
    if settings_obj.travel_base_latitude is not None and settings_obj.travel_base_longitude is not None:
        return (float(settings_obj.travel_base_latitude), float(settings_obj.travel_base_longitude))

    address = settings_obj.travel_base_address or company.address or ''
    zip_code = settings_obj.travel_base_zip_code or company.zip_code or ''
    city = settings_obj.travel_base_city or company.city or ''

    coords = geocode(address, city=city, zip_code=zip_code,
                     country_code=settings_obj.travel_country_code)
    if not coords:
        return None

    settings_obj.travel_base_latitude = Decimal(str(round(coords[0], 6)))
    settings_obj.travel_base_longitude = Decimal(str(round(coords[1], 6)))
    settings_obj.save(update_fields=['travel_base_latitude', 'travel_base_longitude'])
    return coords


def _site_coordinates(quote_request, country_code):
    """Coordonnées du chantier, mises en cache sur la demande elle-même."""
    if quote_request.site_latitude is not None and quote_request.site_longitude is not None:
        return (float(quote_request.site_latitude), float(quote_request.site_longitude))

    coords = geocode(quote_request.address, city=quote_request.city,
                     zip_code=quote_request.zip_code, country_code=country_code)
    if not coords:
        return None

    quote_request.site_latitude = Decimal(str(round(coords[0], 6)))
    quote_request.site_longitude = Decimal(str(round(coords[1], 6)))
    quote_request.save(update_fields=['site_latitude', 'site_longitude'])
    return coords


def compute_travel_cost(company, quote_request):
    """Retourne (distance_aller_km, montant_ht) pour une demande.

    (0, 0) si le déplacement n'est pas facturé, si les paramètres carburant
    sont à zéro, ou si l'une des deux adresses n'a pas pu être localisée.
    """
    settings_obj = _settings_for(company)
    if not settings_obj or not settings_obj.travel_billing_enabled:
        return Decimal('0'), Decimal('0')

    fuel_price = Decimal(settings_obj.fuel_price_per_liter or 0)
    consumption = Decimal(settings_obj.vehicle_consumption_l_per_100km or 0)
    if fuel_price <= 0 or consumption <= 0:
        return Decimal('0'), Decimal('0')

    base = _base_coordinates(company, settings_obj)
    site = _site_coordinates(quote_request, settings_obj.travel_country_code)
    distance_km = road_distance_km(base, site, settings_obj.travel_road_factor)
    if not distance_km:
        return Decimal('0'), Decimal('0')

    distance = Decimal(str(distance_km))
    # Aller-retour : la consommation est exprimée pour 100 km.
    amount = (distance * 2) * (consumption / Decimal('100')) * fuel_price
    return distance.quantize(Decimal('0.1')), amount.quantize(Decimal('0.01'))


def describe_travel(distance_km, settings_obj):
    """Libellé lisible pour la ligne de devis, ex. « Déplacement (2 × 18.4 km) »."""
    if not distance_km:
        return 'Déplacement'
    return f'Déplacement (aller-retour, 2 × {distance_km} km)'
