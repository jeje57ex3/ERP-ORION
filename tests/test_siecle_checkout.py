"""
Tests for SIÈCLE Stripe Checkout integration.
Mocks Stripe to avoid real API calls.
"""
import json
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase, Client, override_settings

from apps.websites.models import Website, WebsiteTheme, StoreProduct, StoreCategory, StoreOrder, StoreOrderItem
from apps.core.models import Company

STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'


class CheckoutSetupMixin:
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name='Test Checkout Co', slug='test-checkout')
        cls.theme = WebsiteTheme.objects.create(
            name='Test Theme', primary_color='#000', secondary_color='#fff', font_primary='Inter',
        )
        cls.site = Website.objects.create(
            company=cls.company, name='SIECLE Checkout Test', slug='siecle-checkout',
            site_type='ecommerce', is_active=True, theme=cls.theme,
        )
        cls.cat = StoreCategory.objects.create(website=cls.site, name='Test Cat', slug='test-cat')
        cls.product = StoreProduct.objects.create(
            website=cls.site, category=cls.cat,
            name='Test Hoodie', slug='test-hoodie',
            price=Decimal('89.00'), stock_quantity=10, status='published',
            available_sizes=['S', 'M', 'L'],
        )
        cls.client = Client()

    def _checkout_payload(self, qty=1, size='M', email='test@example.com'):
        return json.dumps({
            'site':     'siecle-checkout',
            'email':    email,
            'items':    [{'slug': 'test-hoodie', 'quantity': qty, 'size': size}],
            'success_url': 'http://localhost:5173/checkout/success?session_id={CHECKOUT_SESSION_ID}',
            'cancel_url':  'http://localhost:5173/checkout/cancel',
        })


@override_settings(
    STATICFILES_STORAGE=STATICFILES_STORAGE,
    STRIPE_SECRET_KEY='sk_test_fake_key_for_tests',
)
class CreateCheckoutSessionTest(CheckoutSetupMixin, TestCase):

    @patch('apps.ecommerce.api.siecle_api.stripe')
    def test_creates_checkout_session(self, mock_stripe):
        mock_session = MagicMock()
        mock_session.url = 'https://checkout.stripe.com/pay/test_session'
        mock_session.id  = 'cs_test_abc123'
        mock_stripe.checkout.Session.create.return_value = mock_session
        mock_stripe.api_key = ''

        resp = self.client.post(
            '/api/v1/siecle/create-checkout-session/',
            data=self._checkout_payload(),
            content_type='application/json',
            HTTP_X_SITE_SLUG='siecle-checkout',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('checkout_url', data)
        self.assertEqual(data['checkout_url'], 'https://checkout.stripe.com/pay/test_session')
        self.assertIn('session_id', data)

    @patch('apps.ecommerce.api.siecle_api.stripe')
    def test_order_created_in_checkout_started_status(self, mock_stripe):
        mock_session = MagicMock()
        mock_session.url = 'https://checkout.stripe.com/pay/cs_test_xyz'
        mock_session.id  = 'cs_test_xyz'
        mock_stripe.checkout.Session.create.return_value = mock_session
        mock_stripe.api_key = ''

        before_count = StoreOrder.objects.count()
        self.client.post(
            '/api/v1/siecle/create-checkout-session/',
            data=self._checkout_payload(qty=2),
            content_type='application/json',
        )
        self.assertEqual(StoreOrder.objects.count(), before_count + 1)
        order = StoreOrder.objects.latest('created_at')
        self.assertEqual(order.status, 'checkout_started')
        self.assertEqual(order.stripe_session_id, 'cs_test_xyz')

    @patch('apps.ecommerce.api.siecle_api.stripe')
    def test_insufficient_stock_rejected(self, mock_stripe):
        mock_stripe.api_key = ''
        resp = self.client.post(
            '/api/v1/siecle/create-checkout-session/',
            data=json.dumps({
                'site': 'siecle-checkout',
                'items': [{'slug': 'test-hoodie', 'quantity': 9999, 'size': 'M'}],
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 422)

    @patch('apps.ecommerce.api.siecle_api.stripe')
    def test_empty_items_rejected(self, mock_stripe):
        mock_stripe.api_key = ''
        resp = self.client.post(
            '/api/v1/siecle/create-checkout-session/',
            data=json.dumps({'site': 'siecle-checkout', 'items': []}),
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [400, 422])


@override_settings(
    STATICFILES_STORAGE=STATICFILES_STORAGE,
    STRIPE_WEBHOOK_SECRET='whsec_test_fake',
)
class StripeWebhookTest(CheckoutSetupMixin, TestCase):
    """
    Webhook tests patch only stripe.Webhook.construct_event so that
    stripe.SignatureVerificationError remains the real exception class.
    The webhook view uses event['type'] dict-style access, so events
    must be dicts (or dict-like).
    Orders are looked up by pk from session['metadata']['order_id'].
    """

    def _make_order(self, extra_fields=None):
        kw = dict(
            website=self.site, company=self.company,
            status='checkout_started',
            order_number='SCL-TEST001',
            subtotal='89.00', grand_total='89.00',
            payment_method='stripe',
        )
        if extra_fields:
            kw.update(extra_fields)
        order = StoreOrder.objects.create(**kw)
        StoreOrderItem.objects.create(
            order=order, product=self.product, product_name=self.product.name,
            quantity=1, unit_price=self.product.price, total_price=self.product.price,
        )
        return order

    def _post_webhook(self, event_dict):
        with patch('apps.ecommerce.api.siecle_api.stripe.Webhook.construct_event', return_value=event_dict):
            return self.client.post(
                '/api/v1/siecle/stripe/webhook/',
                data=json.dumps(event_dict),
                content_type='application/json',
                HTTP_STRIPE_SIGNATURE='test_sig',
            )

    def test_webhook_checkout_completed_marks_confirmed(self):
        order = self._make_order()
        event = {
            'type': 'checkout.session.completed',
            'data': {
                'object': {
                    'id': 'cs_test_001',
                    'payment_intent': 'pi_test_001',
                    'metadata': {'order_id': str(order.pk), 'order_number': order.order_number},
                }
            },
        }
        resp = self._post_webhook(event)
        self.assertEqual(resp.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, 'confirmed')
        self.assertEqual(order.payment_status, 'paid')

    def test_webhook_session_expired_cancels_order(self):
        order = self._make_order()
        event = {
            'type': 'checkout.session.expired',
            'data': {
                'object': {
                    'id': 'cs_test_exp',
                    'metadata': {'order_id': str(order.pk)},
                }
            },
        }
        resp = self._post_webhook(event)
        self.assertEqual(resp.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, 'cancelled')

    def test_webhook_invalid_signature_returns_400(self):
        import stripe as real_stripe
        with patch('apps.ecommerce.api.siecle_api.stripe.Webhook.construct_event',
                   side_effect=real_stripe.SignatureVerificationError('Bad sig', sig_header='x')):
            resp = self.client.post(
                '/api/v1/siecle/stripe/webhook/',
                data='{}', content_type='application/json',
                HTTP_STRIPE_SIGNATURE='bad_sig',
            )
        self.assertEqual(resp.status_code, 400)
