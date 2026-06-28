"""
tests/test_api_webhooks.py
Tests du module API & Webhooks.
"""
import pytest
from apps.core.models import Company
from apps.api_webhooks.models import WebhookEndpoint, WebhookDelivery
from apps.api_webhooks.services import (
    create_endpoint, deliver_webhook, trigger_event,
    mark_delivery_success, mark_delivery_failed,
    get_pending_deliveries, get_webhook_stats,
)


@pytest.fixture
def company(db):
    return Company.objects.create(name='Webhook SA', slug='webhook-sa', status='active', is_active=True)


@pytest.fixture
def user(db, django_user_model):
    return django_user_model.objects.create_user(username='wh_user', password='pass')


@pytest.fixture
def endpoint(db, company, user):
    return create_endpoint(company, 'Test EP', 'https://hook.example.com/recv',
                           ['invoice.created', 'customer.updated'],
                           raw_secret='mysecret', created_by=user)


class TestCreateEndpoint:
    def test_creates_endpoint(self, db, company, user):
        ep = create_endpoint(company, 'EP1', 'https://example.com/hook', ['*'])
        assert ep.pk is not None
        assert ep.is_active is True

    def test_secret_hashed(self, db, company, user):
        ep = create_endpoint(company, 'EP', 'https://example.com/', ['*'], raw_secret='secret123')
        assert ep.secret_hash != 'secret123'
        assert len(ep.secret_hash) == 64

    def test_no_secret_empty_hash(self, db, company, user):
        ep = create_endpoint(company, 'NoSecret', 'https://example.com/', ['order.created'])
        assert ep.secret_hash == ''

    def test_events_stored(self, db, company, user):
        ep = create_endpoint(company, 'EP', 'https://a.com/', ['a', 'b', 'c'])
        assert ep.events == ['a', 'b', 'c']


class TestTriggerEvent:
    def test_delivers_to_matching_endpoint(self, db, company, endpoint):
        deliveries = trigger_event(company, 'invoice.created', {'id': 1})
        assert len(deliveries) == 1
        assert deliveries[0].event_type == 'invoice.created'

    def test_skips_non_matching_event(self, db, company, endpoint):
        deliveries = trigger_event(company, 'order.created', {'id': 1})
        assert len(deliveries) == 0

    def test_wildcard_matches_all(self, db, company, user):
        ep = create_endpoint(company, 'WC', 'https://wc.example.com/', ['*'], created_by=user)
        deliveries = trigger_event(company, 'anything.happened', {'data': 'x'})
        ep_pks = [d.endpoint.pk for d in deliveries]
        assert ep.pk in ep_pks

    def test_skips_inactive_endpoint(self, db, company, endpoint):
        endpoint.is_active = False
        endpoint.save()
        deliveries = trigger_event(company, 'invoice.created', {})
        assert len(deliveries) == 0

    def test_company_isolation(self, db, company, endpoint, django_user_model):
        other_company = Company.objects.create(name='Other', slug='other', status='active', is_active=True)
        trigger_event(other_company, 'invoice.created', {})
        assert WebhookDelivery.objects.filter(company=other_company).count() == 0


class TestDeliveryLifecycle:
    def test_mark_success(self, db, company, endpoint):
        d = deliver_webhook(company, endpoint, 'test.event', {'x': 1})
        mark_delivery_success(d, 200, 'OK')
        d.refresh_from_db()
        assert d.status == 'success'
        assert d.response_code == 200
        assert d.attempts == 1

    def test_mark_failed(self, db, company, endpoint):
        d = deliver_webhook(company, endpoint, 'test.event', {})
        mark_delivery_failed(d, 500, 'Server Error')
        d.refresh_from_db()
        assert d.status == 'failed'
        assert d.attempts == 1


class TestGetPendingDeliveries:
    def test_returns_pending(self, db, company, endpoint):
        d = deliver_webhook(company, endpoint, 'ev', {})
        result = list(get_pending_deliveries(company))
        assert d in result

    def test_excludes_success(self, db, company, endpoint):
        d = deliver_webhook(company, endpoint, 'ev', {})
        mark_delivery_success(d, 200)
        result = list(get_pending_deliveries(company))
        assert d not in result


class TestWebhookStats:
    def test_stats_structure(self, db, company, endpoint):
        trigger_event(company, 'invoice.created', {})
        stats = get_webhook_stats(company)
        assert 'total_endpoints' in stats
        assert 'active_endpoints' in stats
        assert 'success' in stats
        assert 'failed' in stats
        assert stats['total_endpoints'] >= 1
