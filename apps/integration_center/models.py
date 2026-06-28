from django.db import models
from django.conf import settings
from apps.core.models import Company


INTEGRATION_TYPE_CHOICES = [
    ('stripe', 'Stripe Paiements'), ('paypal', 'PayPal'),
    ('google_calendar', 'Google Calendar'), ('microsoft_365', 'Microsoft 365'),
    ('slack', 'Slack'), ('sendgrid', 'SendGrid'),
    ('twilio', 'Twilio SMS'), ('shopify', 'Shopify'),
    ('woocommerce', 'WooCommerce'), ('quickbooks', 'QuickBooks'),
    ('dolibarr', 'Dolibarr'), ('custom', 'Personnalisé'),
]

SYNC_STATUS_CHOICES = [
    ('pending', 'En attente'), ('running', 'En cours'),
    ('success', 'Succès'), ('partial', 'Partiel'), ('failed', 'Échec'),
]


class IntegrationConfig(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='integration_configs')
    integration_type = models.CharField(max_length=80, choices=INTEGRATION_TYPE_CHOICES)
    name = models.CharField(max_length=180)
    config = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    sync_interval_minutes = models.PositiveIntegerField(default=60)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_integrations',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'integration_center'
        verbose_name = 'Configuration intégration'
        verbose_name_plural = 'Configurations intégrations'
        ordering = ['-created_at']
        unique_together = [('company', 'integration_type', 'name')]

    def __str__(self):
        return f'{self.name} ({self.get_integration_type_display()})'


class IntegrationSyncLog(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='integration_sync_logs')
    integration = models.ForeignKey(
        IntegrationConfig, on_delete=models.SET_NULL, null=True, related_name='sync_logs'
    )
    status = models.CharField(max_length=30, choices=SYNC_STATUS_CHOICES, default='pending')
    records_synced = models.PositiveIntegerField(default=0)
    records_failed = models.PositiveIntegerField(default=0)
    errors = models.JSONField(default=list, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'integration_center'
        verbose_name = 'Journal synchronisation'
        verbose_name_plural = 'Journaux synchronisation'
        ordering = ['-started_at']
        indexes = [models.Index(fields=['company', 'integration', 'status'])]

    def __str__(self):
        return f'{self.integration} — {self.get_status_display()} ({self.started_at:%d/%m/%Y})'

    @property
    def duration_seconds(self):
        if self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None
