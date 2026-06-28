import hashlib
import secrets
from django.db import models
from django.conf import settings
from apps.core.models import Company


class WebhookEndpoint(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='webhook_endpoints')
    name = models.CharField(max_length=180)
    url = models.URLField(max_length=500)
    secret_hash = models.CharField(max_length=128, blank=True)
    events = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    headers = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_webhooks',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'api_webhooks'
        verbose_name = 'Endpoint webhook'
        verbose_name_plural = 'Endpoints webhook'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} → {self.url}'

    def set_secret(self, raw_secret):
        self.secret_hash = hashlib.sha256(raw_secret.encode()).hexdigest()

    def verify_signature(self, payload_bytes, signature):
        if not self.secret_hash:
            return False
        expected = hashlib.sha256(payload_bytes).hexdigest()
        return secrets.compare_digest(expected, signature)


class WebhookDelivery(models.Model):
    STATUS_CHOICES = [
        ('pending', 'En attente'), ('success', 'Succès'),
        ('failed', 'Échec'), ('retrying', 'Nouvelle tentative'),
    ]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='webhook_deliveries')
    endpoint = models.ForeignKey(
        WebhookEndpoint, on_delete=models.SET_NULL, null=True, related_name='deliveries'
    )
    event_type = models.CharField(max_length=120)
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')
    response_code = models.PositiveIntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    attempts = models.PositiveIntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'api_webhooks'
        verbose_name = 'Livraison webhook'
        verbose_name_plural = 'Livraisons webhook'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['company', 'status', 'event_type'])]

    def __str__(self):
        return f'{self.event_type} → {self.endpoint} [{self.status}]'
