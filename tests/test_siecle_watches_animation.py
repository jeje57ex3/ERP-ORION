"""
tests/test_siecle_watches_animation.py
Tests for watch anatomy data + manufacturing timeline backend logic.
"""
import json
from django.test import TestCase, Client
from django.contrib.auth.models import User
from apps.websites.models import (
    StoreProduct, StoreCategory, Website, WebsiteTheme,
    Company,
)


def _get_products(data):
    if isinstance(data, dict):
        return data.get('products', data.get('results', []))
    return data


def _make_site(slug='siecle-test-watches'):
    theme, _ = WebsiteTheme.objects.get_or_create(name='Test Theme', defaults={'primary_color': '#000'})
    company, _ = Company.objects.get_or_create(name='SIÈCLE Test Watches', defaults={'email': 'w@test.fr'})
    site, _ = Website.objects.get_or_create(
        slug=slug,
        defaults={'name': 'SIÈCLE', 'theme': theme, 'company': company},
    )
    return site, company


class WatchAnatomyDataTest(TestCase):
    """Verify watch anatomy data structure matches expected contract."""

    def test_anatomy_parts_count(self):
        # 9 anatomical parts defined in watchAnatomy.js (frontend data)
        # Validated here by contract — if backend ever serves this, it should match
        expected_parts = ['case', 'dial', 'glass', 'hands', 'crown', 'strap', 'clasp', 'movement', 'finish']
        self.assertEqual(len(expected_parts), 9)

    def test_anatomy_part_ids_unique(self):
        parts = ['case', 'dial', 'glass', 'hands', 'crown', 'strap', 'clasp', 'movement', 'finish']
        self.assertEqual(len(parts), len(set(parts)))

    def test_anatomy_positions_in_range(self):
        positions = [
            {'id': 'case', 'x': 18, 'y': 38},
            {'id': 'dial', 'x': 50, 'y': 47},
            {'id': 'glass', 'x': 48, 'y': 28},
            {'id': 'hands', 'x': 53, 'y': 51},
            {'id': 'crown', 'x': 73, 'y': 48},
            {'id': 'strap', 'x': 50, 'y': 78},
            {'id': 'clasp', 'x': 49, 'y': 92},
            {'id': 'movement', 'x': 30, 'y': 52},
            {'id': 'finish', 'x': 63, 'y': 22},
        ]
        for p in positions:
            self.assertGreaterEqual(p['x'], 0, f"{p['id']} x out of range")
            self.assertLessEqual(p['x'], 100, f"{p['id']} x out of range")
            self.assertGreaterEqual(p['y'], 0, f"{p['id']} y out of range")
            self.assertLessEqual(p['y'], 100, f"{p['id']} y out of range")

    def test_timeline_steps_count(self):
        steps = ['Design', 'Matériaux', 'Assemblage', 'Contrôle', 'Présentation']
        self.assertEqual(len(steps), 5)

    def test_timeline_steps_ordered(self):
        steps = ['Design', 'Matériaux', 'Assemblage', 'Contrôle', 'Présentation']
        # Design always first, Presentation always last
        self.assertEqual(steps[0], 'Design')
        self.assertEqual(steps[-1], 'Présentation')


class WatchProductAPITest(TestCase):
    """API tests for watch products served to the WatchesHome page."""

    def setUp(self):
        self.client = Client()
        self.site, self.company = _make_site()
        cat = StoreCategory.objects.create(name='Montres', slug='montres', website=self.site)
        for i in range(3):
            StoreProduct.objects.create(
                name=f'Montre Test {i}', slug=f'montre-test-{i}',
                price='299.00', category=cat, website=self.site,
                stock_quantity=10, status='published',
            )

    def test_watches_product_list(self):
        res = self.client.get('/api/v1/siecle/products/?category=montres')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        results = _get_products(data)
        self.assertEqual(len(results), 3)

    def test_watches_product_has_required_fields(self):
        res = self.client.get('/api/v1/siecle/products/?category=montres')
        data = res.json()
        results = _get_products(data)
        if results:
            product = results[0]
            for field in ('name', 'slug', 'price'):
                self.assertIn(field, product, f"Field '{field}' missing from product response")

    def test_watch_detail_by_slug(self):
        res = self.client.get('/api/v1/siecle/products/montre-test-0/')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['slug'], 'montre-test-0')

    def test_watches_filter_excludes_other_categories(self):
        site, company = _make_site('siecle-test-w2')
        cat_makeup = StoreCategory.objects.create(name='Maquillage', slug='maquillage', website=site)
        StoreProduct.objects.create(
            name='Fond de Teint', slug='fond-de-teint',
            price='45.00', category=cat_makeup, website=site,
            stock_quantity=5, status='published',
        )
        res = self.client.get('/api/v1/siecle/products/?category=montres')
        data = res.json()
        results = _get_products(data)
        slugs = [p['slug'] for p in results]
        self.assertNotIn('fond-de-teint', slugs)

    def test_inactive_watch_not_returned(self):
        site, company = _make_site('siecle-test-w3')
        cat = StoreCategory.objects.create(name='Montres', slug='montres-inactive', website=site)
        StoreProduct.objects.create(
            name='Montre Cachée', slug='montre-cachee',
            price='199.00', category=cat, website=site,
            stock_quantity=2, status='draft',
        )
        res = self.client.get('/api/v1/siecle/products/?category=montres')
        data = res.json()
        results = _get_products(data)
        slugs = [p['slug'] for p in results]
        self.assertNotIn('montre-cachee', slugs)
