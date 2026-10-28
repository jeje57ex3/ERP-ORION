from django.db import models
from django.utils import timezone


class PerformanceEvent(models.Model):
    """Enregistre les requêtes lentes et les anomalies de performance."""

    LEVEL_CHOICES = [
        ('info',    'Info'),
        ('warning', 'Avertissement'),
        ('slow',    'Requête lente'),
        ('error',   'Erreur'),
    ]

    timestamp     = models.DateTimeField(default=timezone.now, db_index=True)
    path          = models.CharField(max_length=500)
    method        = models.CharField(max_length=10, default='GET')
    status_code   = models.PositiveSmallIntegerField(default=200)
    response_ms   = models.PositiveIntegerField(default=0)
    sql_count     = models.PositiveSmallIntegerField(default=0)
    user_id       = models.IntegerField(null=True, blank=True)
    company_id    = models.IntegerField(null=True, blank=True)
    level         = models.CharField(max_length=10, choices=LEVEL_CHOICES, default='info')
    extra         = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp', 'level']),
            models.Index(fields=['path']),
        ]

    def __str__(self):
        return f'[{self.level.upper()}] {self.method} {self.path} — {self.response_ms}ms'
