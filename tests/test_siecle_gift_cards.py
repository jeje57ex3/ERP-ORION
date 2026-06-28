"""
Tests for SIÈCLE gift card system.
Covers: GiftCard model, is_valid property, check endpoint, apply endpoint.
"""
import json
from decimal import Decimal
from datetime import timedelta
from django.test import TestCase, Client, override_settings
from django.utils import timezone
from apps.core.models import Company
from apps.websites.models import (
    Website, WebsiteTheme, GiftCard, GiftCardRedemption,
    SiecleCustomerToken,
)
from django.contrib.auth import get_user_model

User = get_user_model()
STATIC = 'django.contrib.staticfiles.storage.StaticFilesStorage'


def _make_company():
    return Company.objects.create(name='GC Co', slug='gc-co-test')


def _make_site(company):
    theme = WebsiteTheme.objects.create(
        name='T', primary_color='#000', secondary_color='#fff', font_primary='Inter',
    )
    return Website.objects.create(
        company=company, name='SIECLE', slug='siecle',
        site_type='ecommerce', is_active=True, theme=theme,
    )


def _make_gc(company, code, initial, remaining=None, status='active', expires_at=None):
    return GiftCard.objects.create(
        company=company, code=code,
        initial_amount=initial,
        remaining_amount=remaining if remaining is not None else initial,
        status=status,
        expires_at=expires_at,
    )


class GiftCardModelTest(TestCase):
    def setUp(self):
        self.company = _make_company()

    def test_is_valid_active_card(self):
        gc = _make_gc(self.company, 'TEST-VALID-001', Decimal('50.00'))
        self.assertTrue(gc.is_valid)

    def test_is_valid_expired_card(self):
        past = (timezone.now() - timedelta(days=1)).date()
        gc = _make_gc(self.company, 'TEST-EXPIRED-001', Decimal('50.00'), expires_at=past)
        self.assertFalse(gc.is_valid)

    def test_is_valid_used_card(self):
        gc = _make_gc(self.company, 'TEST-USED-001', Decimal('50.00'), remaining=Decimal('0.00'), status='used')
        self.assertFalse(gc.is_valid)

    def test_is_valid_zero_balance(self):
        gc = _make_gc(self.company, 'TEST-ZERO-001', Decimal('50.00'), remaining=Decimal('0.00'))
        self.assertFalse(gc.is_valid)

    def test_is_valid_cancelled(self):
        gc = _make_gc(self.company, 'TEST-CANCELLED-001', Decimal('100.00'), status='cancelled')
        self.assertFalse(gc.is_valid)

    def test_partial_use_card_still_valid(self):
        gc = _make_gc(self.company, 'TEST-PARTIAL-001', Decimal('100.00'), remaining=Decimal('30.00'), status='partial')
        self.assertTrue(gc.is_valid)

    def test_gift_card_code_unique(self):
        _make_gc(self.company, 'UNIQUE-GC-001', Decimal('50.00'))
        with self.assertRaises(Exception):
            _make_gc(self.company, 'UNIQUE-GC-001', Decimal('50.00'))


@override_settings(STATICFILES_STORAGE=STATIC)
class GiftCardCheckAPITest(TestCase):
    def setUp(self):
        self.client = Client()
        self.company = _make_company()
        _make_site(self.company)

    def test_check_valid_gift_card_returns_200(self):
        _make_gc(self.company, 'VALID-CHECK-001', Decimal('50.00'))
        resp = self.client.get('/api/v1/siecle/gift-card/VALID-CHECK-001/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['valid'])
        self.assertEqual(Decimal(data['remaining_amount']), Decimal('50.00'))

    def test_check_used_gift_card_returns_422(self):
        _make_gc(self.company, 'USED-CHECK-001', Decimal('50.00'), remaining=Decimal('0.00'), status='used')
        resp = self.client.get('/api/v1/siecle/gift-card/USED-CHECK-001/')
        self.assertEqual(resp.status_code, 422)
        data = resp.json()
        self.assertFalse(data['valid'])

    def test_check_nonexistent_gift_card_returns_404(self):
        resp = self.client.get('/api/v1/siecle/gift-card/NONEXISTENT-999/')
        self.assertEqual(resp.status_code, 404)

    def test_check_expired_gift_card_returns_422(self):
        past = (timezone.now() - timedelta(days=5)).date()
        _make_gc(self.company, 'EXPIRED-CHECK-001', Decimal('100.00'), expires_at=past)
        resp = self.client.get('/api/v1/siecle/gift-card/EXPIRED-CHECK-001/')
        self.assertEqual(resp.status_code, 422)
        self.assertFalse(resp.json()['valid'])

    def test_check_cancelled_gift_card_returns_422(self):
        _make_gc(self.company, 'CANCELLED-001', Decimal('50.00'), status='cancelled')
        resp = self.client.get('/api/v1/siecle/gift-card/CANCELLED-001/')
        self.assertEqual(resp.status_code, 422)
        self.assertFalse(resp.json()['valid'])


@override_settings(STATICFILES_STORAGE=STATIC)
class GiftCardApplyAPITest(TestCase):
    def setUp(self):
        self.client = Client()
        self.company = _make_company()
        _make_site(self.company)

    def test_apply_gift_card_partial_amount(self):
        _make_gc(self.company, 'APPLY-FULL-001', Decimal('50.00'))
        resp = self.client.post(
            '/api/v1/siecle/cart/apply-gift-card/',
            data=json.dumps({'code': 'APPLY-FULL-001', 'cart_total': '120.00'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(Decimal(str(data['applied_amount'])), Decimal('50.00'))
        self.assertEqual(Decimal(str(data['new_total'])), Decimal('70.00'))

    def test_apply_gift_card_more_than_total(self):
        _make_gc(self.company, 'APPLY-OVER-001', Decimal('100.00'))
        resp = self.client.post(
            '/api/v1/siecle/cart/apply-gift-card/',
            data=json.dumps({'code': 'APPLY-OVER-001', 'cart_total': '30.00'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(Decimal(str(data['applied_amount'])), Decimal('30.00'))
        self.assertEqual(Decimal(str(data['new_total'])), Decimal('0.00'))

    def test_apply_nonexistent_code_returns_404(self):
        resp = self.client.post(
            '/api/v1/siecle/cart/apply-gift-card/',
            data=json.dumps({'code': 'INVALID-CODE-000', 'cart_total': '100.00'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 404)

    def test_apply_expired_gift_card_returns_422(self):
        past = (timezone.now() - timedelta(days=3)).date()
        _make_gc(self.company, 'APPLY-EXP-001', Decimal('50.00'), expires_at=past)
        resp = self.client.post(
            '/api/v1/siecle/cart/apply-gift-card/',
            data=json.dumps({'code': 'APPLY-EXP-001', 'cart_total': '80.00'}),
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [400, 422])

    def test_apply_missing_code_returns_400(self):
        resp = self.client.post(
            '/api/v1/siecle/cart/apply-gift-card/',
            data=json.dumps({'cart_total': '100.00'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)
