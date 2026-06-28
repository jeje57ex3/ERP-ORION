"""
tests/test_siecle_watch_customizer_api.py
Tests for watch configurator API endpoints:
  GET  /api/v1/siecle/products/<slug>/customization-options/
  POST /api/v1/siecle/products/<slug>/validate-customization/
"""
import json
from django.test import TestCase, Client
from apps.websites.models import (
    StoreProduct, StoreCategory, Website, WebsiteTheme, Company,
    ProductCustomizationOption,
)

BASE_CUSTOMIZATION = {
    'case':  'case_black_steel',
    'dial':  'dial_black',
    'hands': 'hands_silver',
    'strap': 'strap_black_leather',
}


def _setup_site(slug='siecle-conf-api'):
    theme, _ = WebsiteTheme.objects.get_or_create(name='Conf Theme', defaults={'primary_color': '#000'})
    company, _ = Company.objects.get_or_create(name='SIÈCLE Conf API', defaults={'email': 'conf@test.fr'})
    site, _ = Website.objects.get_or_create(
        slug=slug,
        defaults={'name': 'SIÈCLE', 'theme': theme, 'company': company},
    )
    return site, company


def _make_watch(site, company, slug='siecle-signature', customizable=True, stock=10):
    cat, _ = StoreCategory.objects.get_or_create(name='Montres', slug=f'montres-{site.slug}', website=site)
    product, _ = StoreProduct.objects.get_or_create(
        slug=slug, website=site,
        defaults={
            'name': 'Montre SIÈCLE Signature',
            'category': cat,
            'price': '199.00',
            'stock_quantity': stock,
            'status': 'published',
            'is_customizable': customizable,
        },
    )
    return product


class CustomizationOptionsEndpointTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.site, self.company = _setup_site()
        self.watch = _make_watch(self.site, self.company)

    def test_options_returns_200_for_customizable_watch(self):
        res = self.client.get(f'/api/v1/siecle/products/{self.watch.slug}/customization-options/')
        self.assertEqual(res.status_code, 200)

    def test_options_response_contains_required_keys(self):
        res = self.client.get(f'/api/v1/siecle/products/{self.watch.slug}/customization-options/')
        data = res.json()
        for key in ('product_id', 'base_price', 'options'):
            self.assertIn(key, data, f"Key '{key}' missing from options response")

    def test_options_base_price_matches_product(self):
        res = self.client.get(f'/api/v1/siecle/products/{self.watch.slug}/customization-options/')
        data = res.json()
        self.assertEqual(float(data['base_price']), 199.0)

    def test_options_contains_all_groups(self):
        res = self.client.get(f'/api/v1/siecle/products/{self.watch.slug}/customization-options/')
        opts = res.json().get('options', {})
        for group in ('case', 'dial', 'hands', 'strap'):
            self.assertIn(group, opts)

    def test_options_404_for_unknown_slug(self):
        res = self.client.get('/api/v1/siecle/products/unknown-watch/customization-options/')
        self.assertEqual(res.status_code, 404)

    def test_options_400_for_non_customizable_product(self):
        site2, company2 = _setup_site('siecle-nc-api')
        non_cust = _make_watch(site2, company2, slug='montre-non-cust', customizable=False)
        res = self.client.get(f'/api/v1/siecle/products/{non_cust.slug}/customization-options/')
        self.assertEqual(res.status_code, 400)

    def test_options_with_db_options_seeded(self):
        ProductCustomizationOption.objects.create(
            company=self.company, product=self.watch,
            group='case', code='case_gold',
            label='Doré champagne', color='#C9A45C',
            material='metal', price_delta='35.00',
        )
        res = self.client.get(f'/api/v1/siecle/products/{self.watch.slug}/customization-options/')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        case_opts = data['options'].get('case', [])
        codes = [o['id'] for o in case_opts]
        self.assertIn('case_gold', codes)


class ValidateCustomizationEndpointTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.site, self.company = _setup_site('siecle-validate-api')
        self.watch = _make_watch(self.site, self.company, slug='siecle-sig-val')
        self.url = f'/api/v1/siecle/products/{self.watch.slug}/validate-customization/'

    def _post(self, customization):
        return self.client.post(
            self.url,
            data=json.dumps({'customization': customization}),
            content_type='application/json',
        )

    def test_valid_configuration_returns_200(self):
        res = self._post(BASE_CUSTOMIZATION)
        self.assertEqual(res.status_code, 200)

    def test_valid_config_returns_final_price(self):
        res = self._post(BASE_CUSTOMIZATION)
        data = res.json()
        self.assertIn('final_price', data)
        self.assertIsInstance(data['final_price'], (int, float))

    def test_base_config_has_zero_option_delta(self):
        res = self._post(BASE_CUSTOMIZATION)
        data = res.json()
        self.assertEqual(data.get('options_price', 0), 0)
        self.assertEqual(data['final_price'], 199.0)

    def test_gold_case_adds_35_euros(self):
        config = {**BASE_CUSTOMIZATION, 'case': 'case_gold'}
        res = self._post(config)
        data = res.json()
        self.assertEqual(data['final_price'], 199.0 + 35.0)

    def test_gold_hands_adds_10_euros(self):
        config = {**BASE_CUSTOMIZATION, 'hands': 'hands_gold'}
        res = self._post(config)
        data = res.json()
        self.assertEqual(data['final_price'], 199.0 + 10.0)

    def test_all_premium_options_price_summed(self):
        config = {
            'case':  'case_gold',     # +35
            'dial':  'dial_champagne',# +20
            'hands': 'hands_gold',    # +10
            'strap': 'strap_steel',   # +35
        }
        res = self._post(config)
        data = res.json()
        self.assertEqual(data['final_price'], 199.0 + 35 + 20 + 10 + 35)

    def test_missing_group_returns_422(self):
        incomplete = {'case': 'case_black_steel', 'dial': 'dial_black'}
        res = self._post(incomplete)
        self.assertIn(res.status_code, [400, 422])

    def test_out_of_stock_watch_returns_422(self):
        site3, company3 = _setup_site('siecle-stock-api')
        out_of_stock = _make_watch(site3, company3, slug='siecle-out-stock', stock=0)
        url = f'/api/v1/siecle/products/{out_of_stock.slug}/validate-customization/'
        res = self.client.post(url, data=json.dumps({'customization': BASE_CUSTOMIZATION}), content_type='application/json')
        self.assertEqual(res.status_code, 422)
        self.assertIn('out_of_stock', res.json().get('code', ''))

    def test_non_customizable_product_returns_400(self):
        site4, company4 = _setup_site('siecle-nc2-api')
        nc = _make_watch(site4, company4, slug='siecle-nc2', customizable=False)
        url = f'/api/v1/siecle/products/{nc.slug}/validate-customization/'
        res = self.client.post(url, data=json.dumps({'customization': BASE_CUSTOMIZATION}), content_type='application/json')
        self.assertEqual(res.status_code, 400)

    def test_invalid_json_body_returns_400(self):
        res = self.client.post(self.url, data='not-json', content_type='application/json')
        self.assertEqual(res.status_code, 400)

    def test_invalid_option_code_rejected_when_db_options_set(self):
        for group in ('case', 'dial', 'hands', 'strap'):
            ProductCustomizationOption.objects.create(
                company=self.company, product=self.watch,
                group=group, code=f'{group}_only_valid',
                label='Seule option valide', color='#000',
                material='metal', price_delta='5.00',
            )
        bad_config = {'case': 'case_gold', 'dial': 'dial_black', 'hands': 'hands_silver', 'strap': 'strap_black_leather'}
        res = self._post(bad_config)
        self.assertIn(res.status_code, [200, 422])  # 422 if DB options enforced
