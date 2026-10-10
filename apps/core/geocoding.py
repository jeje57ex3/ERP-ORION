"""
apps/core/geocoding.py — Géocodage d'adresses et calcul de distance.

Utilise Nominatim (OpenStreetMap) : gratuit, couverture mondiale (Portugal
inclus), sans clé API. Sa politique d'usage impose un User-Agent identifiant
l'application et au plus 1 requête/seconde — d'où le cache Django sur chaque
adresse normalisée (une adresse déjà vue ne repart jamais sur le réseau).

Toutes les fonctions sont « fail-safe » : une panne réseau, un timeout ou une
adresse introuvable renvoient None plutôt que de lever — un devis ne doit
jamais échouer parce qu'un service tiers est indisponible.
"""
import hashlib
import logging
import math

import requests
from django.core.cache import cache

logger = logging.getLogger(__name__)

NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search'
USER_AGENT = 'OrionERP/1.0 (ERP BTP - geocodage devis)'
CACHE_TTL = 60 * 60 * 24 * 30  # 30 jours : une adresse postale ne bouge pas
TIMEOUT_SECONDS = 6

EARTH_RADIUS_KM = 6371.0


def _cache_key(query, country_code):
    # Haché : une adresse contient espaces et accents, interdits comme clé
    # de cache par certains backends (memcached).
    digest = hashlib.sha1(f'{country_code}:{query.strip().lower()}'.encode('utf-8')).hexdigest()
    return f'geocode:{digest}'


def _query_nominatim(query, country_code):
    """Un appel Nominatim. Renvoie (lat, lon, nom_trouvé) ou None."""
    try:
        response = requests.get(
            NOMINATIM_URL,
            params={
                'q': query,
                'format': 'json',
                'limit': 1,
                'countrycodes': country_code or '',
            },
            headers={'User-Agent': USER_AGENT},
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        results = response.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning('Géocodage indisponible pour « %s » : %s', query, exc)
        return None

    if not results:
        return None
    try:
        return (float(results[0]['lat']), float(results[0]['lon']),
                results[0].get('display_name', ''))
    except (KeyError, TypeError, ValueError):
        return None


def geocode_detailed(address, city='', zip_code='', country_code='pt'):
    """Géocode une adresse en dégradant progressivement la précision.

    Beaucoup de rues ne sont pas cartographiées dans OpenStreetMap, et les
    codes postaux portugais y sont très incomplets : chercher uniquement
    l'adresse complète échouerait sur des adresses pourtant valides. On tente
    donc, dans l'ordre : rue + CP + ville, rue + ville, CP + ville, ville
    seule. Pour un frais de déplacement, une localisation à la ville reste
    largement exploitable.

    Renvoie un dict {lat, lon, precision, matched} ou None si rien n'est
    trouvé. `precision` vaut 'street', 'postcode' ou 'city'.
    """
    address = (address or '').strip()
    city = (city or '').strip()
    zip_code = (zip_code or '').strip()
    if not any((address, city, zip_code)):
        return None

    attempts = []
    if address and city:
        if zip_code:
            attempts.append(('street', f'{address}, {zip_code}, {city}'))
        attempts.append(('street', f'{address}, {city}'))
    elif address:
        attempts.append(('street', address))
    if zip_code and city:
        attempts.append(('postcode', f'{zip_code}, {city}'))
    elif zip_code:
        attempts.append(('postcode', zip_code))
    if city:
        attempts.append(('city', city))

    cache_key = _cache_key('|'.join(q for _, q in attempts), country_code)
    cached = cache.get(cache_key)
    if cached is not None:
        # '' = échec déjà constaté, on ne retente pas avant expiration du cache
        return cached or None

    for precision, query in attempts:
        found = _query_nominatim(query, country_code)
        if found:
            result = {'lat': found[0], 'lon': found[1],
                      'precision': precision, 'matched': found[2]}
            cache.set(cache_key, result, CACHE_TTL)
            return result

    cache.set(cache_key, '', CACHE_TTL)
    return None


def geocode(address, city='', zip_code='', country_code='pt'):
    """Convertit une adresse postale en (latitude, longitude), ou None.

    Enveloppe de `geocode_detailed` pour les appelants qui n'ont besoin que
    des coordonnées (calcul de distance).
    """
    result = geocode_detailed(address, city=city, zip_code=zip_code, country_code=country_code)
    return (result['lat'], result['lon']) if result else None


def haversine_km(lat1, lon1, lat2, lon2):
    """Distance orthodromique (à vol d'oiseau) entre deux points, en km."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def road_distance_km(origin, destination, road_factor=1.3):
    """Distance routière estimée entre deux couples (lat, lon).

    Nominatim ne fait que du géocodage, pas du calcul d'itinéraire : on
    applique un coefficient de sinuosité à la distance à vol d'oiseau
    (≈1.3 en zone mixte) plutôt que d'ajouter une dépendance à un moteur de
    routage. Le coefficient est paramétrable par entreprise.
    """
    if not origin or not destination:
        return None
    straight = haversine_km(origin[0], origin[1], destination[0], destination[1])
    return round(straight * float(road_factor), 1)
