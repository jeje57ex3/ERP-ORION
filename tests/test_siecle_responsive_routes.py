"""
tests/test_siecle_responsive_routes.py
Tests for API route availability and response shapes.
Verifies all critical endpoints are reachable with correct HTTP methods.
"""
import json
from django.test import TestCase, Client
from django.contrib.auth.models import User
from apps.websites.models import (
    StoreProduct, StoreCategory, Website, WebsiteTheme, Company,
    SiecleCustomerToken,
)


def _get_products(data):
    if isinstance(data, dict):
        return data.get('products', data.get('results', []))
    return data


def _make_auth_site(slug='siecle-routes'):
    theme, _ = WebsiteTheme.objects.get_or_create(name='Routes Theme', defaults={'primary_color': '#000'})
    company, _ = Company.objects.get_or_create(name='SIÈCLE Routes', defaults={'email': f'{slug}@test.fr'})
    site, _ = Website.objects.get_or_create(
        slug=slug,
        defaults={'name': 'SIÈCLE Routes', 'theme': theme, 'company': company},
    )
    return site, company


class PublicEndpointAvailabilityTest(TestCase):
    """All public endpoints return expected status codes without auth."""

    def setUp(self):
        self.client = Client()
        site, company = _make_auth_site()
        cat = StoreCategory.objects.create(name='Test', slug='test-cat-routes', website=site)
        StoreProduct.objects.create(
            name='Test Prod', slug='test-prod-routes',
            price='10.00', category=cat, website=site,
            stock_quantity=5, status='published',
        )

    def test_products_list_get(self):
        res = self.client.get('/api/v1/siecle/products/')
        self.assertEqual(res.status_code, 200)

    def test_product_detail_get(self):
        res = self.client.get('/api/v1/siecle/products/test-prod-routes/')
        self.assertEqual(res.status_code, 200)

    def test_collections_list_get(self):
        res = self.client.get('/api/v1/siecle/collections/')
        self.assertEqual(res.status_code, 200)

    def test_newsletter_post_available(self):
        res = self.client.post(
            '/api/v1/siecle/newsletter/',
            data=json.dumps({'email': 'route-test@example.com'}),
            content_type='application/json',
        )
        self.assertIn(res.status_code, [200, 201])

    def test_newsletter_get_not_allowed(self):
        res = self.client.get('/api/v1/siecle/newsletter/')
        self.assertIn(res.status_code, [404, 405])

    def test_auth_register_post_available(self):
        res = self.client.post(
            '/api/v1/siecle/auth/register/',
            data=json.dumps({'email': 'new-route@example.com', 'password': 'pass1234!', 'first_name': 'Test'}),
            content_type='application/json',
        )
        self.assertIn(res.status_code, [200, 201, 400])

    def test_me_without_auth_returns_unauthenticated(self):
        res = self.client.get('/api/v1/siecle/auth/me/')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertFalse(data.get('authenticated', True))

    def test_gift_card_unknown_returns_404(self):
        res = self.client.get('/api/v1/siecle/gift-card/UNKNOWN-CODE-XXXX/')
        self.assertEqual(res.status_code, 404)


class AuthEndpointTest(TestCase):
    """Protected endpoints require authentication token."""

    def setUp(self):
        self.client = Client()
        _make_auth_site('siecle-auth-routes')
        self.user = User.objects.create_user(
            username='auth-route@test.fr',
            email='auth-route@test.fr',
            password='testpass1234!',
        )
        self.token = SiecleCustomerToken.generate(self.user)

    def _auth_headers(self):
        return {'HTTP_AUTHORIZATION': f'Token {self.token}'}

    def test_me_with_token_returns_user(self):
        res = self.client.get('/api/v1/siecle/auth/me/', **self._auth_headers())
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get('authenticated'))

    def test_customer_account_requires_auth(self):
        res = self.client.get('/api/v1/siecle/customer/account/')
        self.assertEqual(res.status_code, 401)

    def test_customer_account_with_auth(self):
        res = self.client.get('/api/v1/siecle/customer/account/', **self._auth_headers())
        self.assertEqual(res.status_code, 200)

    def test_customer_rewards_with_auth(self):
        res = self.client.get('/api/v1/siecle/customer/rewards/', **self._auth_headers())
        self.assertEqual(res.status_code, 200)

    def test_customer_affiliate_with_auth(self):
        res = self.client.get('/api/v1/siecle/customer/affiliate/', **self._auth_headers())
        self.assertEqual(res.status_code, 200)


class MethodNotAllowedTest(TestCase):
    """Endpoints reject incorrect HTTP methods gracefully."""

    def setUp(self):
        self.client = Client()

    def test_products_list_post_not_allowed(self):
        res = self.client.post('/api/v1/siecle/products/', data='{}', content_type='application/json')
        self.assertIn(res.status_code, [405, 404])

    def test_collections_post_not_allowed(self):
        res = self.client.post('/api/v1/siecle/collections/', data='{}', content_type='application/json')
        self.assertIn(res.status_code, [405, 404])
