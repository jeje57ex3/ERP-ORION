from django.db import models
from django.conf import settings
from apps.core.models import Company


CHECK_TYPE_CHOICES = [
    ('database', 'Base de données'), ('cache', 'Cache'),
    ('storage', 'Stockage'), ('email', 'E-mail'),
    ('external_api', 'API externe'), ('queue', 'File de tâches'),
    ('disk_space', 'Espace disque'), ('memory', 'Mémoire'),
    ('cpu', 'CPU'), ('custom', 'Personnalisé'),
]

HEALTH_STATUS_CHOICES = [
    ('ok', 'OK'), ('warning', 'Avertissement'),
    ('critical', 'Critique'), ('unknown', 'Inconnu'),
]

ALERT_SEVERITY_CHOICES = [
    ('info', 'Info'), ('warning', 'Avertissement'),
    ('critical', 'Critique'), ('emergency', 'Urgence'),
]


class SystemHealthCheck(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='health_checks')
    check_type = models.CharField(max_length=80, choices=CHECK_TYPE_CHOICES)
    status = models.CharField(max_length=30, choices=HEALTH_STATUS_CHOICES, default='unknown')
    message = models.TextField(blank=True)
    response_time_ms = models.PositiveIntegerField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    checked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'system_observability'
        verbose_name = 'Vérification santé système'
        verbose_name_plural = 'Vérifications santé système'
        ordering = ['-checked_at']
        indexes = [models.Index(fields=['company', 'check_type', 'checked_at'])]

    def __str__(self):
        return f'[{self.get_status_display()}] {self.get_check_type_display()} — {self.checked_at:%d/%m %H:%M}'


class SystemAlertRule(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='system_alert_rules')
    name = models.CharField(max_length=180)
    check_type = models.CharField(max_length=80, choices=CHECK_TYPE_CHOICES)
    trigger_status = models.CharField(max_length=30, choices=HEALTH_STATUS_CHOICES, default='critical')
    notify_emails = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'system_observability'
        verbose_name = 'Règle alerte système'
        verbose_name_plural = 'Règles alertes système'

    def __str__(self):
        return self.name


class SystemObservabilityAlert(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='system_obs_alerts')
    alert_type = models.CharField(max_length=80, choices=CHECK_TYPE_CHOICES)
    severity = models.CharField(max_length=30, choices=ALERT_SEVERITY_CHOICES, default='warning')
    title = models.CharField(max_length=180)
    message = models.TextField()
    is_acknowledged = models.BooleanField(default=False)
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='acknowledged_sys_alerts',
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'system_observability'
        verbose_name = 'Alerte système'
        verbose_name_plural = 'Alertes système'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['company', 'severity', 'is_acknowledged'])]

    def __str__(self):
        return f'[{self.get_severity_display()}] {self.title}'
