"""
tests/test_siecle_watch_customizer_cart.py
Tests for POST /api/v1/siecle/cart/add-custom-watch/
Two different configurations must create two independent saved records.
"""
import json
from django.test import TestCase, Client
from apps.websites.models import (
    StoreProduct, StoreCategory, Website, WebsiteTheme, Company,
    ProductCustomizationConfiguration,
)

BASE_CONFIG = {
    'case':  'case_black_steel',
    'dial':  'dial_black',
    'hands': 'hands_silver',
    'strap': 'strap_black_leather',
}
BASE_LABELS = {
    'case': 'Acier noir', 'dial': 'Noir profond',
    'hands': 'Argent', 'strap': 'Cuir noir',
}


def _setup(slug='siecle-conf-cart'):
    theme, _ = WebsiteTheme.objects.get_or_create(name='Cart Theme', defaults={'primary_color': '#000'})
    company, _ = Company.objects.get_or_create(name='SIÈCLE Cart', defaults={'email': 'cart@test.fr'})
    site, _ = Website.objects.get_or_create(
        slug=slug,
        defaults={'name': 'SIÈCLE', 'theme': theme, 'company': company},
    )
    cat, _ = StoreCategory.objects.get_or_create(name='Montres', slug=f'montres-cart-{slug}', website=site)
    product, _ = StoreProduct.objects.get_or_create(
        slug=f'watch-cart-{slug}', website=site,
        defaults={
            'name': 'Montre Cart Test',
            'category': cat,
            'price': '199.00',
            'stock_quantity': 20,
            'status': 'published',
            'is_customizable': True,
        },
    )
    return site, company, product


URL = '/api/v1/siecle/cart/add-custom-watch/'


class AddCustomWatchToCartTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.site, self.company, self.product = _setup()

    def _post(self, payload):
        return self.client.post(URL, data=json.dumps(payload), content_type='application/json')

    def _base_payload(self, **overrides):
        payload = {
            'product_id':            self.product.pk,
            'customization':         BASE_CONFIG,
            'customization_labels':  BASE_LABELS,
            'base_price':            199,
            'options_price':         0,
            'final_price':           199,
        }
        payload.update(overrides)
        return payload

    def test_add_custom_watch_returns_201(self):
        res = self._post(self._base_payload())
        self.assertEqual(res.status_code, 201)

    def test_add_custom_watch_returns_saved_true(self):
        res = self._post(self._base_payload())
        data = res.json()
        self.assertTrue(data.get('saved'))

    def test_add_custom_watch_returns_configuration_id(self):
        res = self._post(self._base_payload())
        data = res.json()
        self.assertIsNotNone(data.get('configuration_id'))

    def test_add_custom_watch_returns_final_price(self):
        res = self._post(self._base_payload(options_price=35, final_price=234))
        data = res.json()
        self.assertIn('final_price', data)

    def test_configuration_saved_to_db(self):
        before = ProductCustomizationConfiguration.objects.count()
        self._post(self._base_payload())
        after = ProductCustomizationConfiguration.objects.count()
        self.assertGreater(after, before)

    def test_two_different_configs_create_two_records(self):
        config_a = {**BASE_CONFIG, 'case': 'case_gold'}
        config_b = {**BASE_CONFIG, 'case': 'case_silver'}

        self._post(self._base_payload(customization=config_a, final_price=234))
        self._post(self._base_payload(customization=config_b, final_price=219))

        configs = ProductCustomizationConfiguration.objects.filter(product=self.product)
        case_values = [c.configuration_json.get('case') for c in configs]
        self.assertIn('case_gold', case_values)
        self.assertIn('case_silver', case_values)

    def test_same_config_submitted_twice_creates_two_records(self):
        before = ProductCustomizationConfiguration.objects.filter(product=self.product).count()
        self._post(self._base_payload())
        self._post(self._base_payload())
        after = ProductCustomizationConfiguration.objects.filter(product=self.product).count()
        self.assertEqual(after, before + 2)

    def test_missing_product_id_returns_400(self):
        payload = {'customization': BASE_CONFIG, 'base_price': 199, 'final_price': 199}
        res = self._post(payload)
        self.assertEqual(res.status_code, 400)

    def test_unknown_product_id_returns_404(self):
        payload = self._base_payload(product_id=99999)
        res = self._post(payload)
        self.assertEqual(res.status_code, 404)

    def test_non_customizable_product_returns_400(self):
        _, _, nc = _setup('siecle-nc-cart')
        nc.is_customizable = False
        nc.save(update_fields=['is_customizable'])
        payload = self._base_payload(product_id=nc.pk)
        res = self._post(payload)
        self.assertEqual(res.status_code, 400)

    def test_out_of_stock_returns_422(self):
        _, _, oos = _setup('siecle-oos-cart')
        oos.stock_quantity = 0
        oos.save(update_fields=['stock_quantity'])
        payload = self._base_payload(product_id=oos.pk)
        res = self._post(payload)
        self.assertEqual(res.status_code, 422)

    def test_configuration_json_stored_correctly(self):
        config = {'case': 'case_gold', 'dial': 'dial_champagne', 'hands': 'hands_gold', 'strap': 'strap_steel'}
        self._post(self._base_payload(customization=config))
        saved = ProductCustomizationConfiguration.objects.filter(product=self.product).last()
        self.assertIsNotNone(saved)
        self.assertEqual(saved.configuration_json, config)

    def test_labels_json_stored_correctly(self):
        labels = {'case': 'Doré champagne', 'dial': 'Champagne', 'hands': 'Doré', 'strap': 'Maille acier'}
        self._post(self._base_payload(customization_labels=labels))
        saved = ProductCustomizationConfiguration.objects.filter(product=self.product).last()
        self.assertIsNotNone(saved)
        self.assertEqual(saved.configuration_labels_json, labels)

    def test_final_price_stored_correctly(self):
        self._post(self._base_payload(options_price=70, final_price=269))
        saved = ProductCustomizationConfiguration.objects.filter(product=self.product).last()
        self.assertEqual(float(saved.final_price), 269.0)
