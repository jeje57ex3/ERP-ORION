"""
Tests for the SIÈCLE e-commerce public API.
Covers: product listing, filtering, detail, collections, cart validation.
"""
import json
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.websites.models import (
    Website, WebsiteTheme, StoreProduct, StoreCategory,
    StoreOrder, StoreOrderItem,
)
from apps.core.models import Company

User = get_user_model()

STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'


class SiecleAPISetupMixin:
    """Creates test site + products shared across API test cases."""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name='Test SIECLE Co', slug='test-siecle')

        cls.theme = WebsiteTheme.objects.create(
            name='Dark Test',
            primary_color='#000',
            secondary_color='#fff',
            font_primary='Inter',
        )
        cls.site = Website.objects.create(
            company=cls.company,
            name='SIECLE Test',
            slug='siecle',
            site_type='ecommerce',
            is_active=True,
            theme=cls.theme,
        )
        cls.cat_vt = StoreCategory.objects.create(
            website=cls.site, name='Vetements', slug='vetements',
        )
        cls.cat_mo = StoreCategory.objects.create(
            website=cls.site, name='Montres', slug='montres',
        )

        cls.product_hoodie = StoreProduct.objects.create(
            website=cls.site,
            category=cls.cat_vt,
            name='Hoodie Test',
            slug='hoodie-test',
            price=Decimal('89.00'),
            stock_quantity=20,
            status='published',
            is_popular=True,
            available_sizes=['S', 'M', 'L', 'XL'],
        )
        cls.product_montre = StoreProduct.objects.create(
            website=cls.site,
            category=cls.cat_mo,
            name='Montre Test',
            slug='montre-test',
            price=Decimal('299.00'),
            stock_quantity=5,
            status='published',
            is_popular=False,
            available_sizes=[],
        )
        cls.product_draft = StoreProduct.objects.create(
            website=cls.site,
            name='Draft Product',
            slug='draft-product',
            price=Decimal('50.00'),
            stock_quantity=10,
            status='draft',
        )

        cls.client = Client()


@override_settings(STATICFILES_STORAGE=STATICFILES_STORAGE)
class ProductListViewTest(SiecleAPISetupMixin, TestCase):

    def test_returns_published_products(self):
        resp = self.client.get('/api/v1/siecle/products/', {'site': 'siecle'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('products', data)
        slugs = [p['slug'] for p in data['products']]
        self.assertIn('hoodie-test', slugs)
        self.assertIn('montre-test', slugs)
        self.assertNotIn('draft-product', slugs)

    def test_count_field(self):
        resp = self.client.get('/api/v1/siecle/products/', {'site': 'siecle'})
        data = resp.json()
        self.assertEqual(data['count'], 2)

    def test_filter_by_category(self):
        resp = self.client.get('/api/v1/siecle/products/', {'site': 'siecle', 'category': 'vetements'})
        self.assertEqual(resp.status_code, 200)
        slugs = [p['slug'] for p in resp.json()['products']]
        self.assertIn('hoodie-test', slugs)
        self.assertNotIn('montre-test', slugs)

    def test_filter_popular(self):
        resp = self.client.get('/api/v1/siecle/products/', {'site': 'siecle', 'popular': 'true'})
        data = resp.json()
        slugs = [p['slug'] for p in data['products']]
        self.assertIn('hoodie-test', slugs)
        self.assertNotIn('montre-test', slugs)

    def test_unknown_site_returns_200(self):
        resp = self.client.get('/api/v1/siecle/products/', {'site': 'nonexistent'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('products', data)
        self.assertIn('count', data)

    def test_product_fields(self):
        resp = self.client.get('/api/v1/siecle/products/', {'site': 'siecle'})
        product = next(p for p in resp.json()['products'] if p['slug'] == 'hoodie-test')
        self.assertIn('id', product)
        self.assertIn('name', product)
        self.assertIn('slug', product)
        self.assertIn('price', product)
        self.assertIn('stock_quantity', product)
        self.assertIn('is_popular', product)
        self.assertIn('sizes', product)
        self.assertEqual(product['sizes'], ['S', 'M', 'L', 'XL'])
        self.assertTrue(product['is_popular'])


@override_settings(STATICFILES_STORAGE=STATICFILES_STORAGE)
class ProductDetailViewTest(SiecleAPISetupMixin, TestCase):

    def test_returns_product_data(self):
        resp = self.client.get('/api/v1/siecle/products/hoodie-test/', {'site': 'siecle'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['slug'], 'hoodie-test')
        self.assertEqual(data['name'], 'Hoodie Test')
        self.assertIn('description', data)
        self.assertIn('gallery', data)

    def test_404_for_draft(self):
        resp = self.client.get('/api/v1/siecle/products/draft-product/', {'site': 'siecle'})
        self.assertEqual(resp.status_code, 404)

    def test_404_for_unknown_slug(self):
        resp = self.client.get('/api/v1/siecle/products/does-not-exist/', {'site': 'siecle'})
        self.assertEqual(resp.status_code, 404)


@override_settings(STATICFILES_STORAGE=STATICFILES_STORAGE)
class CollectionListViewTest(SiecleAPISetupMixin, TestCase):

    def test_returns_collections(self):
        resp = self.client.get('/api/v1/siecle/collections/', {'site': 'siecle'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('collections', data)
        slugs = [c['slug'] for c in data['collections']]
        self.assertIn('vetements', slugs)
        self.assertIn('montres', slugs)

    def test_returns_200_for_unknown_site(self):
        resp = self.client.get('/api/v1/siecle/collections/', {'site': 'ghost'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('collections', resp.json())


@override_settings(STATICFILES_STORAGE=STATICFILES_STORAGE)
class CartValidateViewTest(SiecleAPISetupMixin, TestCase):

    def _post(self, items):
        return self.client.post(
            '/api/v1/siecle/cart/validate/',
            data=json.dumps({'items': items, 'site': 'siecle'}),
            content_type='application/json',
            HTTP_X_SITE_SLUG='siecle',
        )

    def test_valid_cart(self):
        resp = self._post([{'slug': 'hoodie-test', 'quantity': 2, 'size': 'M'}])
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['valid'])

    def test_invalid_slug(self):
        resp = self._post([{'slug': 'fake-slug', 'quantity': 1}])
        self.assertEqual(resp.status_code, 422)
        self.assertFalse(resp.json()['valid'])

    def test_insufficient_stock(self):
        resp = self._post([{'slug': 'hoodie-test', 'quantity': 9999}])
        self.assertEqual(resp.status_code, 422)
        self.assertFalse(resp.json()['valid'])

    def test_empty_cart(self):
        resp = self._post([])
        self.assertIn(resp.status_code, [400, 422])

    def test_draft_product_rejected(self):
        resp = self._post([{'slug': 'draft-product', 'quantity': 1}])
        self.assertEqual(resp.status_code, 422)
        self.assertFalse(resp.json()['valid'])
