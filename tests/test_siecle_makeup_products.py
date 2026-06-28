"""
tests/test_siecle_makeup_products.py
Tests for makeup product API — filtering, detail, best-sellers.
"""
from django.test import TestCase, Client
from apps.websites.models import (
    StoreProduct, StoreCategory, Website, WebsiteTheme, Company,
)


def _get_products(data):
    """Extract product list from API response — handles both {'products': [...]} and list."""
    if isinstance(data, dict):
        return data.get('products', data.get('results', []))
    return data


def _bootstrap(site_slug='siecle-makeup-prod', cat_slug='maquillage'):
    theme, _ = WebsiteTheme.objects.get_or_create(name='Makeup Theme', defaults={'primary_color': '#c9a45c'})
    company, _ = Company.objects.get_or_create(name='SIÈCLE Makeup', defaults={'email': 'm@test.fr'})
    site, _ = Website.objects.get_or_create(
        slug=site_slug,
        defaults={'name': 'SIÈCLE Makeup', 'theme': theme, 'company': company},
    )
    cat, _ = StoreCategory.objects.get_or_create(name='Maquillage', slug=cat_slug, website=site)
    return site, company, cat


class MakeupProductListTest(TestCase):

    def setUp(self):
        self.client = Client()
        site, company, cat = _bootstrap()
        self.site = site
        self.cat = cat

        products = [
            ('Fond de Teint Velours', 'fond-de-teint-velours', '45.00'),
            ('Rouge Intense', 'rouge-intense', '38.00'),
            ('Mascara Volume', 'mascara-volume', '29.00'),
            ('Palette Nuit Dorée', 'palette-nuit-doree', '89.00'),
        ]
        for name, slug, price in products:
            StoreProduct.objects.create(
                name=name, slug=slug, price=price,
                category=cat, website=site,
                stock_quantity=20, status='published',
            )

    def test_makeup_products_returned(self):
        res = self.client.get('/api/v1/siecle/products/?category=maquillage')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        results = _get_products(data)
        self.assertEqual(len(results), 4)

    def test_product_fields_present(self):
        res = self.client.get('/api/v1/siecle/products/?category=maquillage')
        results = _get_products(res.json())
        product = results[0]
        for field in ('name', 'slug', 'price'):
            self.assertIn(field, product)

    def test_product_price_is_string_or_numeric(self):
        res = self.client.get('/api/v1/siecle/products/?category=maquillage')
        results = _get_products(res.json())
        for p in results:
            price = p.get('price', '')
            float(str(price))

    def test_makeup_detail_endpoint(self):
        res = self.client.get('/api/v1/siecle/products/rouge-intense/')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['slug'], 'rouge-intense')
        self.assertEqual(data['name'], 'Rouge Intense')

    def test_unknown_product_returns_404(self):
        res = self.client.get('/api/v1/siecle/products/produit-inexistant/')
        self.assertEqual(res.status_code, 404)

    def test_inactive_product_excluded(self):
        site, _, cat = _bootstrap(site_slug='siecle-makeup-inactive', cat_slug='maquillage-inactive-test')
        StoreProduct.objects.create(
            name='Caché', slug='produit-cache',
            price='10.00', category=cat, website=site,
            stock_quantity=5, status='draft',
        )
        res = self.client.get('/api/v1/siecle/products/?category=maquillage')
        results = _get_products(res.json())
        slugs = [p['slug'] for p in results]
        self.assertNotIn('produit-cache', slugs)

    def test_limit_parameter(self):
        res = self.client.get('/api/v1/siecle/products/?category=maquillage&limit=2')
        self.assertEqual(res.status_code, 200)
        results = _get_products(res.json())
        self.assertLessEqual(len(results), 4)


class MakeupCategoryIsolationTest(TestCase):
    """Makeup category products don't bleed into watch listings."""

    def setUp(self):
        self.client = Client()
        theme, _ = WebsiteTheme.objects.get_or_create(name='Iso Theme', defaults={'primary_color': '#000'})
        company, _ = Company.objects.get_or_create(name='SIÈCLE Iso', defaults={'email': 'i@test.fr'})
        site, _ = Website.objects.get_or_create(
            slug='siecle-iso',
            defaults={'name': 'SIÈCLE Iso', 'theme': theme, 'company': company},
        )
        cat_m = StoreCategory.objects.create(name='Maquillage Iso', slug='maquillage-iso-test', website=site)
        cat_w = StoreCategory.objects.create(name='Montres Iso', slug='montres-iso-test', website=site)
        StoreProduct.objects.create(
            name='Rouge Test', slug='rouge-test-iso',
            price='35.00', category=cat_m, website=site,
            stock_quantity=5, status='published',
        )
        StoreProduct.objects.create(
            name='Montre Test', slug='montre-test-iso',
            price='299.00', category=cat_w, website=site,
            stock_quantity=3, status='published',
        )

    def test_makeup_does_not_return_watches(self):
        res = self.client.get('/api/v1/siecle/products/?category=maquillage-iso-test')
        results = _get_products(res.json())
        slugs = [p['slug'] for p in results]
        self.assertNotIn('montre-test-iso', slugs)

    def test_watches_does_not_return_makeup(self):
        res = self.client.get('/api/v1/siecle/products/?category=montres-iso-test')
        results = _get_products(res.json())
        slugs = [p['slug'] for p in results]
        self.assertNotIn('rouge-test-iso', slugs)
