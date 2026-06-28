from django.db import models
from django.conf import settings
from apps.core.models import Company


PRIORITY_CHOICES = [
    ('critical', 'Critique'),
    ('high', 'Important'),
    ('normal', 'Normal'),
    ('info', 'Information'),
]

STATUS_CHOICES = [
    ('open', 'Ouverte'),
    ('acknowledged', 'Vue'),
    ('resolved', 'Résolue'),
    ('ignored', 'Ignorée'),
]


class SmartAlert(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='smart_alerts')
    brand_key = models.CharField(max_length=40, blank=True)
    title = models.CharField(max_length=180)
    message = models.TextField(blank=True)
    source_module = models.CharField(max_length=80)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='normal')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    related_object_type = models.CharField(max_length=80, blank=True)
    related_object_id = models.CharField(max_length=80, blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='assigned_alerts',
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='resolved_alerts',
    )
    metadata = models.JSONField(default=dict, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'smart_alerts'
        verbose_name = 'Alerte'
        verbose_name_plural = 'Alertes'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'status', 'priority']),
            models.Index(fields=['company', 'source_module']),
        ]

    def __str__(self):
        return f'[{self.get_priority_display()}] {self.title}'

    @property
    def is_open(self):
        return self.status == 'open'

    @property
    def is_critical(self):
        return self.priority == 'critical'
