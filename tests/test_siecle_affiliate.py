"""
Tests for SIÈCLE affiliate/referral system.
Covers: AffiliateCode generation, format, referral creation, API endpoints.
"""
import json
from decimal import Decimal
from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from apps.core.models import Company
from apps.websites.models import (
    Website, WebsiteTheme,
    AffiliateProgram, AffiliateCode, AffiliateReferral,
    SiecleCustomerToken,
)

User = get_user_model()
STATIC = 'django.contrib.staticfiles.storage.StaticFilesStorage'


def _make_site(company):
    theme = WebsiteTheme.objects.create(
        name='T', primary_color='#000', secondary_color='#fff', font_primary='Inter',
    )
    return Website.objects.create(
        company=company, name='SIECLE', slug='siecle',
        site_type='ecommerce', is_active=True, theme=theme,
    )


class AffiliateProgramModelTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='Co', slug='co-aff')
        _make_site(self.company)

    def test_create_affiliate_program(self):
        prog = AffiliateProgram.objects.create(
            company=self.company,
            is_active=True,
            referrer_reward_value=Decimal('100'),
            referred_reward_value=Decimal('10'),
        )
        self.assertTrue(prog.is_active)
        self.assertEqual(prog.referrer_reward_value, Decimal('100'))

    def test_affiliate_program_is_unique_per_company(self):
        AffiliateProgram.objects.create(company=self.company, is_active=True)
        with self.assertRaises(Exception):
            AffiliateProgram.objects.create(company=self.company, is_active=False)


class AffiliateCodeModelTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='Co', slug='co-aff-code')
        _make_site(self.company)
        self.user = User.objects.create_user(username='aff1', email='aff1@t.fr', password='pass')

    def test_create_affiliate_code(self):
        code = AffiliateCode.objects.create(
            company=self.company, customer=self.user,
            customer_email='aff1@t.fr', code='SCL-TESTCODE',
        )
        self.assertEqual(code.code, 'SCL-TESTCODE')
        self.assertEqual(code.clicks, 0)
        self.assertEqual(code.signups, 0)
        self.assertEqual(code.orders, 0)

    def test_affiliate_code_is_unique(self):
        AffiliateCode.objects.create(company=self.company, code='SCL-UNIQUE01')
        with self.assertRaises(Exception):
            AffiliateCode.objects.create(company=self.company, code='SCL-UNIQUE01')


class AffiliateReferralModelTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='Co', slug='co-aff-ref')
        _make_site(self.company)
        self.user = User.objects.create_user(username='referrer', email='ref@t.fr', password='pass')
        self.code = AffiliateCode.objects.create(
            company=self.company, customer=self.user,
            customer_email='ref@t.fr', code='SCL-REFTEST',
        )

    def test_create_referral_pending(self):
        ref = AffiliateReferral.objects.create(
            company=self.company,
            referrer_email='ref@t.fr',
            referred_email='new@t.fr',
            affiliate_code=self.code,
            status='pending',
        )
        self.assertEqual(ref.status, 'pending')

    def test_validate_referral_updates_status(self):
        ref = AffiliateReferral.objects.create(
            company=self.company,
            referrer_email='ref@t.fr',
            referred_email='new2@t.fr',
            affiliate_code=self.code,
            status='pending',
        )
        ref.status = 'validated'
        ref.save()
        ref.refresh_from_db()
        self.assertEqual(ref.status, 'validated')


@override_settings(STATICFILES_STORAGE=STATIC)
class AffiliateAPITest(TestCase):
    def setUp(self):
        self.client = Client()
        self.company = Company.objects.create(name='Co', slug='co-aff-api')
        _make_site(self.company)
        self.user = User.objects.create_user(username='affapi', email='affapi@t.fr', password='pass')
        # generate() returns the token key string
        self.token_key = SiecleCustomerToken.generate(self.user)
        AffiliateProgram.objects.create(
            company=self.company, is_active=True,
            referrer_reward_value=Decimal('100'), referred_reward_value=Decimal('10'),
        )

    def _auth(self):
        return {'HTTP_AUTHORIZATION': f'Token {self.token_key}'}

    def test_get_affiliate_unauthenticated(self):
        resp = self.client.get('/api/v1/siecle/customer/affiliate/')
        self.assertEqual(resp.status_code, 401)

    def test_get_affiliate_no_code_yet(self):
        resp = self.client.get('/api/v1/siecle/customer/affiliate/', **self._auth())
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsNone(data.get('code'))

    def test_create_affiliate_code(self):
        resp = self.client.post(
            '/api/v1/siecle/customer/affiliate/create-code/',
            content_type='application/json',
            **self._auth(),
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertIn('code', data)
        code = data['code']
        self.assertTrue(code.startswith('SCL-'), f"Code should start with SCL-, got: {code}")
        self.assertEqual(len(code), 12, f"Code should be 12 chars (SCL-XXXXXXXX), got: {code}")

    def test_create_second_code_returns_conflict(self):
        """Creating a code twice returns 409 (not idempotent by API design)."""
        resp1 = self.client.post('/api/v1/siecle/customer/affiliate/create-code/', **self._auth())
        self.assertEqual(resp1.status_code, 201)
        resp2 = self.client.post('/api/v1/siecle/customer/affiliate/create-code/', **self._auth())
        self.assertEqual(resp2.status_code, 409)

    def test_affiliate_code_format_sclxxxxxxxx(self):
        resp = self.client.post(
            '/api/v1/siecle/customer/affiliate/create-code/',
            content_type='application/json',
            **self._auth(),
        )
        code = resp.json()['code']
        import re
        self.assertRegex(code, r'^SCL-[A-Z0-9]{8}$')

    def test_get_affiliate_after_code_creation(self):
        self.client.post('/api/v1/siecle/customer/affiliate/create-code/', **self._auth())
        resp = self.client.get('/api/v1/siecle/customer/affiliate/', **self._auth())
        self.assertEqual(resp.status_code, 200)
        self.assertIsNotNone(resp.json().get('code'))
