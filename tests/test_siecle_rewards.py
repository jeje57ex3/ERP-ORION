"""
Tests for SIÈCLE loyalty rewards system.
Covers: LoyaltyAccount creation, points, tier calculation, reward use, customer API.
"""
import json
from decimal import Decimal
from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from apps.core.models import Company
from apps.websites.models import (
    Website, WebsiteTheme, StoreProduct, StoreCategory,
    LoyaltyAccount, LoyaltyTransaction, SiecleCustomerToken,
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


# ── Model-level tests ──────────────────────────────────────────────────────────

class LoyaltyAccountModelTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='Co', slug='co-rewards')
        self.user = User.objects.create_user(username='u1', email='u1@t.fr', password='pass')
        self.account = LoyaltyAccount.objects.create(
            company=self.company, customer=self.user,
            customer_email='u1@t.fr', points_balance=0, lifetime_points=0,
        )

    def test_initial_tier_classic(self):
        self.assertEqual(self.account.tier, 'classic')

    def test_add_points_updates_balance(self):
        self.account.add_points(200, reason='Test achat')
        self.account.refresh_from_db()
        self.assertEqual(self.account.points_balance, 200)
        self.assertEqual(self.account.lifetime_points, 200)

    def test_tier_upgrade_to_silver(self):
        self.account.add_points(500, reason='Achat')
        self.account.refresh_from_db()
        self.assertEqual(self.account.tier, 'silver')

    def test_tier_upgrade_to_gold(self):
        self.account.add_points(1000, reason='Achat')
        self.account.refresh_from_db()
        self.assertEqual(self.account.tier, 'gold')

    def test_tier_upgrade_to_black(self):
        self.account.add_points(3000, reason='Achat')
        self.account.refresh_from_db()
        self.assertEqual(self.account.tier, 'black')

    def test_use_points_deducts_balance(self):
        self.account.add_points(300, reason='Achat')
        self.account.use_points(100, reason='Récompense 5€')
        self.account.refresh_from_db()
        self.assertEqual(self.account.points_balance, 200)

    def test_use_points_insufficient_raises(self):
        self.account.add_points(50, reason='Achat')
        with self.assertRaises(ValueError):
            self.account.use_points(100, reason='Récompense')

    def test_transaction_created_on_add(self):
        self.account.add_points(150, reason='Test')
        self.assertEqual(LoyaltyTransaction.objects.filter(loyalty_account=self.account).count(), 1)
        tx = LoyaltyTransaction.objects.get(loyalty_account=self.account)
        self.assertEqual(tx.points, 150)
        self.assertEqual(tx.transaction_type, 'gain')

    def test_transaction_created_on_use(self):
        self.account.add_points(200, reason='Achat')
        self.account.use_points(100, reason='Récompense')
        txs = LoyaltyTransaction.objects.filter(loyalty_account=self.account)
        self.assertEqual(txs.count(), 2)
        use_tx = txs.filter(transaction_type='utilisation').first()
        self.assertIsNotNone(use_tx)
        self.assertEqual(use_tx.points, -100)


# ── API tests ──────────────────────────────────────────────────────────────────

@override_settings(STATICFILES_STORAGE=STATIC)
class RewardsAPITest(TestCase):
    def setUp(self):
        self.client = Client()
        self.company = Company.objects.create(name='Co', slug='co-rewards-api')
        self.site = _make_site(self.company)
        self.user = User.objects.create_user(username='u2', email='u2@t.fr', password='pass')
        # generate() returns the token key string
        self.token_key = SiecleCustomerToken.generate(self.user)
        self.account = LoyaltyAccount.objects.create(
            company=self.company, customer=self.user,
            customer_email='u2@t.fr', points_balance=500, lifetime_points=500, tier='silver',
        )

    def _auth(self):
        return {'HTTP_AUTHORIZATION': f'Token {self.token_key}'}

    def test_get_rewards_authenticated(self):
        resp = self.client.get('/api/v1/siecle/customer/rewards/', **self._auth())
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('points_balance', data)
        self.assertEqual(data['points_balance'], 500)
        self.assertEqual(data['tier'], 'silver')

    def test_get_rewards_unauthenticated(self):
        resp = self.client.get('/api/v1/siecle/customer/rewards/')
        self.assertEqual(resp.status_code, 401)

    def test_use_reward_success(self):
        resp = self.client.post(
            '/api/v1/siecle/customer/rewards/use/',
            data=json.dumps({'reward_id': 'r100'}),
            content_type='application/json',
            **self._auth(),
        )
        self.assertEqual(resp.status_code, 200)
        self.account.refresh_from_db()
        self.assertEqual(self.account.points_balance, 400)

    def test_use_reward_insufficient_points(self):
        self.account.points_balance = 50
        self.account.save()
        resp = self.client.post(
            '/api/v1/siecle/customer/rewards/use/',
            data=json.dumps({'reward_id': 'r250'}),
            content_type='application/json',
            **self._auth(),
        )
        # API returns 422 when balance insufficient
        self.assertIn(resp.status_code, [400, 422])

    def test_use_reward_invalid_id(self):
        resp = self.client.post(
            '/api/v1/siecle/customer/rewards/use/',
            data=json.dumps({'reward_id': 'invalid'}),
            content_type='application/json',
            **self._auth(),
        )
        self.assertEqual(resp.status_code, 400)

    def test_apply_reward_points_endpoint(self):
        resp = self.client.post(
            '/api/v1/siecle/cart/apply-reward/',
            data=json.dumps({'reward_id': 'r100', 'cart_total': '120.00'}),
            content_type='application/json',
            **self._auth(),
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('discount', data)
        self.assertIn('new_total', data)


@override_settings(STATICFILES_STORAGE=STATIC)
class SiecleAuthAPITest(TestCase):
    def setUp(self):
        self.client = Client()
        self.company = Company.objects.create(name='Co', slug='co-auth-test')
        self.site = _make_site(self.company)

    def test_register_creates_user_and_token(self):
        resp = self.client.post(
            '/api/v1/siecle/auth/register/',
            data=json.dumps({'email': 'new@t.fr', 'password': 'password123', 'first_name': 'Test'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertIn('token', data)
        self.assertTrue(User.objects.filter(email='new@t.fr').exists())

    def test_login_returns_token(self):
        User.objects.create_user(username='logtest', email='logtest@t.fr', password='pass1234')
        resp = self.client.post(
            '/api/v1/siecle/auth/login/',
            data=json.dumps({'email': 'logtest@t.fr', 'password': 'pass1234'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn('token', resp.json())

    def test_login_wrong_password_401(self):
        User.objects.create_user(username='wrongpw', email='wrongpw@t.fr', password='correct')
        resp = self.client.post(
            '/api/v1/siecle/auth/login/',
            data=json.dumps({'email': 'wrongpw@t.fr', 'password': 'wrong'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 401)

    def test_me_unauthenticated_returns_not_authenticated(self):
        resp = self.client.get('/api/v1/siecle/auth/me/')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json().get('authenticated'))

    def test_me_authenticated(self):
        user = User.objects.create_user(username='metest', email='metest@t.fr', password='pass')
        token_key = SiecleCustomerToken.generate(user)
        resp = self.client.get('/api/v1/siecle/auth/me/', HTTP_AUTHORIZATION=f'Token {token_key}')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json().get('authenticated'))
