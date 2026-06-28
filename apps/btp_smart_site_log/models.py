from django.db import models
from django.conf import settings
from apps.core.models import Company

LOG_TYPE_CHOICES = [
    ('daily_report', 'Rapport journalier'), ('incident', 'Incident'),
    ('delivery', 'Livraison matériaux'), ('inspection', 'Inspection'),
    ('milestone', 'Jalon'), ('weather_stop', 'Arrêt météo'),
    ('visit', 'Visite chantier'), ('photo_report', 'Rapport photo'),
    ('safety', 'Sécurité'), ('other', 'Autre'),
]

WEATHER_CHOICES = [
    ('sunny', 'Ensoleillé'), ('cloudy', 'Nuageux'), ('rainy', 'Pluvieux'),
    ('windy', 'Venteux'), ('stormy', 'Orageux'), ('snowy', 'Neigeux'),
    ('hot', 'Très chaud'), ('unknown', 'Inconnu'),
]

SEVERITY_CHOICES = [
    ('low', 'Faible'), ('medium', 'Moyen'), ('high', 'Élevé'), ('critical', 'Critique'),
]

INCIDENT_TYPE_CHOICES = [
    ('safety_accident', 'Accident sécurité'), ('material_damage', 'Dommage matériel'),
    ('delay', 'Retard'), ('quality_issue', 'Problème qualité'),
    ('theft', 'Vol'), ('other', 'Autre'),
]


class SiteLog(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='btp_site_logs')
    brand_key = models.CharField(max_length=40, blank=True)
    project_id = models.CharField(max_length=80)
    project_name = models.CharField(max_length=180, blank=True)
    log_type = models.CharField(max_length=40, choices=LOG_TYPE_CHOICES)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    photos = models.JSONField(default=list, blank=True)
    documents = models.JSONField(default=list, blank=True)
    workers_count = models.PositiveIntegerField(default=0)
    weather = models.CharField(max_length=30, choices=WEATHER_CHOICES, default='unknown')
    temperature_celsius = models.IntegerField(null=True, blank=True)
    gps_lat = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    gps_lng = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    location_label = models.CharField(max_length=255, blank=True)
    progress_percent = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)
    logged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='btp_site_logs',
    )
    logged_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'btp_smart_site_log'
        verbose_name = 'Journal chantier'
        verbose_name_plural = 'Journaux chantier'
        ordering = ['-logged_at']
        indexes = [
            models.Index(fields=['company', 'project_id', 'logged_at']),
            models.Index(fields=['company', 'log_type', 'logged_at']),
        ]

    def __str__(self):
        return f'[{self.project_id}] {self.title} — {self.logged_at:%d/%m/%Y}'


class SiteLogIncident(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='btp_site_incidents')
    site_log = models.ForeignKey(SiteLog, on_delete=models.CASCADE, related_name='incidents')
    incident_type = models.CharField(max_length=80, choices=INCIDENT_TYPE_CHOICES)
    severity = models.CharField(max_length=30, choices=SEVERITY_CHOICES, default='medium')
    description = models.TextField()
    corrective_action = models.TextField(blank=True)
    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'btp_smart_site_log'
        verbose_name = 'Incident chantier'
        verbose_name_plural = 'Incidents chantier'
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.get_severity_display()}] {self.get_incident_type_display()} — {self.site_log}'
