"""
tests/test_travel_costs.py — Frais de déplacement du devis guidé.

Couvre le calcul distance × carburant, les replis quand le géocodage échoue
ou que les paramètres sont incomplets, et la mise en cache des coordonnées.
Le géocodage réseau (Nominatim) est systématiquement simulé : aucun test ne
doit dépendre d'un service tiers.
"""
from decimal import Decimal
from unittest.mock import patch

import pytest

from apps.btp.models import GuidedQuoteRequest
from apps.btp.travel_costs import compute_travel_cost, describe_travel
from apps.core.geocoding import geocode_detailed, haversine_km, road_distance_km

LISBOA = (38.7247512, -9.1497126)
PORTO = (41.1567862, -8.6045966)


@pytest.fixture
def company(db):
    from apps.core.models import Company
    # Le signal post_save de core crée déjà les CompanySettings associés.
    return Company.objects.create(
        name='Obras Lisboa Lda', slug='obras-lisboa', status='active', is_active=True,
        address='Avenida da Liberdade', zip_code='1250-096', city='Lisboa',
    )


@pytest.fixture
def travel_settings(company):
    settings_obj = company.settings
    settings_obj.travel_billing_enabled = True
    settings_obj.travel_country_code = 'pt'
    settings_obj.fuel_price_per_liter = Decimal('1.750')
    settings_obj.vehicle_consumption_l_per_100km = Decimal('8.00')
    settings_obj.travel_road_factor = Decimal('1.30')
    settings_obj.travel_base_latitude = Decimal(str(LISBOA[0]))
    settings_obj.travel_base_longitude = Decimal(str(LISBOA[1]))
    settings_obj.save()
    return settings_obj


def _request(company, **kwargs):
    defaults = dict(
        company=company, request_type='depannage',
        client_first_name='Ana', client_last_name='Silva', client_email='ana@example.pt',
        address='Rua de Santa Catarina', zip_code='4000-447', city='Porto',
    )
    defaults.update(kwargs)
    return GuidedQuoteRequest.objects.create(**defaults)


# ─── Géométrie ────────────────────────────────────────────────────────────────

def test_haversine_matches_known_distance():
    # Lisboa → Porto : ~274 km à vol d'oiseau.
    assert haversine_km(*LISBOA, *PORTO) == pytest.approx(274, abs=5)


def test_road_distance_applies_road_factor():
    straight = haversine_km(*LISBOA, *PORTO)
    assert road_distance_km(LISBOA, PORTO, 1.3) == pytest.approx(straight * 1.3, abs=0.5)


def test_road_distance_returns_none_without_coordinates():
    assert road_distance_km(None, PORTO, 1.3) is None
    assert road_distance_km(LISBOA, None, 1.3) is None


# ─── Géocodage : dégradation progressive de la précision ──────────────────────
#
# Beaucoup de rues ne sont pas cartographiées dans OpenStreetMap et les codes
# postaux portugais y sont très incomplets : une recherche en tout-ou-rien
# échouait sur des adresses pourtant valides (cas réel constaté à Nazaré).

@pytest.fixture(autouse=True)
def _clear_geocode_cache():
    from django.core.cache import cache
    cache.clear()
    yield
    cache.clear()


def test_geocode_prefers_street_level_match():
    with patch('apps.core.geocoding._query_nominatim',
               return_value=(38.7, -9.1, 'Avenida da Liberdade, Lisboa')) as mocked:
        result = geocode_detailed('Avenida da Liberdade', city='Lisboa', zip_code='1250-096')
    assert result['precision'] == 'street'
    assert mocked.call_count == 1  # premier essai suffisant


def test_geocode_falls_back_to_city_when_street_unknown():
    """Rue absente de la carte : on ne renvoie pas un échec, on dégrade."""
    def only_city(query, country_code):
        return (39.60, -9.07, 'Nazaré, Leiria, Portugal') if query == 'nazare' else None

    with patch('apps.core.geocoding._query_nominatim', side_effect=only_city):
        result = geocode_detailed('rua inexistante', city='nazare', zip_code='2450-169')

    assert result['precision'] == 'city'
    assert result['lat'] == pytest.approx(39.60)


def test_geocode_returns_none_when_nothing_matches():
    with patch('apps.core.geocoding._query_nominatim', return_value=None):
        assert geocode_detailed('rue inconnue', city='ville inconnue') is None


def test_geocode_without_any_address_part_does_not_call_network():
    with patch('apps.core.geocoding._query_nominatim') as mocked:
        assert geocode_detailed('', city='', zip_code='') is None
        mocked.assert_not_called()


# ─── Calcul du coût ───────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_travel_cost_uses_distance_fuel_and_consumption(company, travel_settings):
    quote = _request(company, site_latitude=Decimal(str(PORTO[0])), site_longitude=Decimal(str(PORTO[1])))
    distance, amount = compute_travel_cost(company, quote)

    # Aller-retour × (8 L/100 km) × 1.75 €/L
    expected = (distance * 2) * (Decimal('8.00') / Decimal('100')) * Decimal('1.750')
    assert amount == expected.quantize(Decimal('0.01'))
    assert distance > 300  # Lisboa → Porto avec coefficient routier


@pytest.mark.django_db
def test_travel_cost_is_zero_when_billing_disabled(company, travel_settings):
    travel_settings.travel_billing_enabled = False
    travel_settings.save()
    quote = _request(company, site_latitude=Decimal(str(PORTO[0])), site_longitude=Decimal(str(PORTO[1])))
    assert compute_travel_cost(company, quote) == (Decimal('0'), Decimal('0'))


@pytest.mark.django_db
def test_travel_cost_is_zero_when_fuel_parameters_missing(company, travel_settings):
    travel_settings.fuel_price_per_liter = Decimal('0')
    travel_settings.save()
    quote = _request(company, site_latitude=Decimal(str(PORTO[0])), site_longitude=Decimal(str(PORTO[1])))
    assert compute_travel_cost(company, quote) == (Decimal('0'), Decimal('0'))


@pytest.mark.django_db
def test_travel_cost_falls_back_to_zero_when_geocoding_unavailable(company, travel_settings):
    """Une panne du service de géocodage ne doit jamais casser l'estimation."""
    quote = _request(company)  # pas de coordonnées en cache
    with patch('apps.btp.travel_costs.geocode', return_value=None):
        distance, amount = compute_travel_cost(company, quote)
    assert (distance, amount) == (Decimal('0'), Decimal('0'))


@pytest.mark.django_db
def test_site_coordinates_are_cached_on_the_request(company, travel_settings):
    quote = _request(company)
    with patch('apps.btp.travel_costs.geocode', return_value=PORTO) as mocked:
        compute_travel_cost(company, quote)
        quote.refresh_from_db()
        assert quote.site_latitude is not None
        # Deuxième calcul : les coordonnées viennent du cache, pas du réseau.
        mocked.reset_mock()
        compute_travel_cost(company, quote)
        mocked.assert_not_called()


@pytest.mark.django_db
def test_company_base_coordinates_are_geocoded_once_then_cached(company):
    settings_obj = company.settings
    settings_obj.fuel_price_per_liter = Decimal('1.750')
    settings_obj.vehicle_consumption_l_per_100km = Decimal('8.00')
    settings_obj.save()
    quote = _request(company, site_latitude=Decimal(str(PORTO[0])), site_longitude=Decimal(str(PORTO[1])))

    with patch('apps.btp.travel_costs.geocode', return_value=LISBOA) as mocked:
        compute_travel_cost(company, quote)
        assert mocked.call_count == 1
        settings_obj.refresh_from_db()
        assert settings_obj.travel_base_latitude is not None


def test_describe_travel_mentions_round_trip():
    assert '2 ×' in describe_travel(Decimal('18.4'), None)
    assert describe_travel(0, None) == 'Déplacement'


# ─── Intégration au devis guidé ───────────────────────────────────────────────

@pytest.mark.django_db
def test_guided_estimate_includes_travel_line_and_distance(company, travel_settings):
    from apps.btp.guided_quote_views import _calculate_estimate
    quote = _request(company, site_latitude=Decimal(str(PORTO[0])), site_longitude=Decimal(str(PORTO[1])))

    estimate = _calculate_estimate(company, quote)

    assert estimate.travel_amount > 0
    assert estimate.travel_distance_km > 0
    travel_lines = [i for i in estimate.items.all() if 'placement' in i.description]
    assert travel_lines, 'une ligne de déplacement doit figurer dans le détail'
    assert travel_lines[0].price_item is None  # calculé, pas issu du catalogue
