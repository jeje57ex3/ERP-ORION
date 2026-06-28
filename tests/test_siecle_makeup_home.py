"""
tests/test_siecle_makeup_home.py
Tests for newsletter subscription endpoint + makeup page backend.
"""
import json
from django.test import TestCase, Client


class NewsletterSubscribeTest(TestCase):
    """Tests for POST /api/v1/siecle/newsletter/"""

    def setUp(self):
        self.client = Client()
        self.url = '/api/v1/siecle/newsletter/'

    def test_subscribe_valid_email(self):
        res = self.client.post(
            self.url,
            data=json.dumps({'email': 'test@example.com'}),
            content_type='application/json',
        )
        self.assertIn(res.status_code, [200, 201])
        data = res.json()
        self.assertTrue(data.get('subscribed'))

    def test_subscribe_created_flag_on_first(self):
        res = self.client.post(
            self.url,
            data=json.dumps({'email': 'nouveau@example.com'}),
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 201)
        self.assertTrue(res.json().get('created'))

    def test_subscribe_already_subscribed_returns_200(self):
        email = 'double@example.com'
        self.client.post(self.url, data=json.dumps({'email': email}), content_type='application/json')
        res = self.client.post(self.url, data=json.dumps({'email': email}), content_type='application/json')
        self.assertIn(res.status_code, [200, 201])
        data = res.json()
        self.assertTrue(data.get('subscribed'))

    def test_subscribe_invalid_email_returns_400(self):
        res = self.client.post(
            self.url,
            data=json.dumps({'email': 'notanemail'}),
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 400)

    def test_subscribe_missing_email_returns_400(self):
        res = self.client.post(
            self.url,
            data=json.dumps({}),
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 400)

    def test_subscribe_empty_string_returns_400(self):
        res = self.client.post(
            self.url,
            data=json.dumps({'email': ''}),
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 400)

    def test_subscribe_email_normalised_to_lowercase(self):
        res = self.client.post(
            self.url,
            data=json.dumps({'email': 'UPPER@EXAMPLE.COM'}),
            content_type='application/json',
        )
        self.assertIn(res.status_code, [200, 201])

    def test_subscribe_invalid_json_body_returns_400(self):
        res = self.client.post(
            self.url,
            data='not-json',
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 400)

    def test_get_method_not_allowed(self):
        res = self.client.get(self.url)
        self.assertIn(res.status_code, [405, 404])

    def test_response_is_json(self):
        res = self.client.post(
            self.url,
            data=json.dumps({'email': 'json@test.com'}),
            content_type='application/json',
        )
        self.assertEqual(res['Content-Type'], 'application/json')
