import json
import hashlib
import hmac
from django.utils import timezone
from .models import WebhookEndpoint, WebhookDelivery


def create_endpoint(company, name, url, events, *, raw_secret='', headers=None, created_by=None):
    endpoint = WebhookEndpoint(
        company=company, name=name, url=url,
        events=events, headers=headers or {}, created_by=created_by,
    )
    if raw_secret:
        endpoint.set_secret(raw_secret)
    endpoint.save()
    return endpoint


def deliver_webhook(company, endpoint, event_type, payload):
    return WebhookDelivery.objects.create(
        company=company, endpoint=endpoint,
        event_type=event_type, payload=payload,
        status='pending',
    )


def sign_payload(payload_bytes, secret):
    """HMAC-SHA256 signature for outgoing webhooks."""
    return hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()


def trigger_event(company, event_type, payload):
    """Fan-out an event to all matching active endpoints."""
    endpoints = WebhookEndpoint.objects.filter(
        company=company, is_active=True,
    )
    deliveries = []
    for ep in endpoints:
        if event_type in ep.events or '*' in ep.events:
            d = deliver_webhook(company, ep, event_type, payload)
            deliveries.append(d)
    return deliveries


def mark_delivery_success(delivery, response_code, response_body=''):
    delivery.status = 'success'
    delivery.response_code = response_code
    delivery.response_body = response_body[:4000]
    delivery.attempts += 1
    delivery.last_attempt_at = timezone.now()
    delivery.save(update_fields=['status', 'response_code', 'response_body', 'attempts', 'last_attempt_at'])
    return delivery


def mark_delivery_failed(delivery, response_code=None, response_body=''):
    delivery.status = 'failed'
    delivery.response_code = response_code
    delivery.response_body = response_body[:4000]
    delivery.attempts += 1
    delivery.last_attempt_at = timezone.now()
    delivery.save(update_fields=['status', 'response_code', 'response_body', 'attempts', 'last_attempt_at'])
    return delivery


def get_pending_deliveries(company, limit=100):
    return WebhookDelivery.objects.filter(
        company=company, status__in=('pending', 'retrying')
    ).select_related('endpoint').order_by('created_at')[:limit]


def get_webhook_stats(company):
    qs = WebhookDelivery.objects.filter(company=company)
    return {
        'total_endpoints': WebhookEndpoint.objects.filter(company=company).count(),
        'active_endpoints': WebhookEndpoint.objects.filter(company=company, is_active=True).count(),
        'total_deliveries': qs.count(),
        'success': qs.filter(status='success').count(),
        'failed': qs.filter(status='failed').count(),
        'pending': qs.filter(status__in=('pending', 'retrying')).count(),
    }
