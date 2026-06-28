from django.db import models
from django.conf import settings
from apps.core.models import Company


INCIDENT_TYPE_CHOICES = [
    ('site_incident', 'Incident chantier'), ('customer_return', 'Retour client'),
    ('defective_product', 'Produit défectueux'), ('invoice_error', 'Erreur facture'),
    ('delivery_delay', 'Retard livraison'), ('complaint', 'Réclamation'),
    ('non_conformity', 'Non-conformité'), ('other', 'Autre'),
]

SEVERITY_CHOICES = [
    ('critical', 'Critique'), ('high', 'Élevée'), ('normal', 'Normale'), ('low', 'Faible'),
]

STATUS_CHOICES = [
    ('open', 'Ouverte'), ('in_progress', 'En cours'),
    ('resolved', 'Résolue'), ('closed', 'Clôturée'),
]


class QualityIncident(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='quality_incidents')
    brand_key = models.CharField(max_length=40, blank=True)
    title = models.CharField(max_length=180)
    incident_type = models.CharField(max_length=80, choices=INCIDENT_TYPE_CHOICES)
    severity = models.CharField(max_length=30, choices=SEVERITY_CHOICES, default='normal')
    status = models.CharField(max_length=40, choices=STATUS_CHOICES, default='open')
    customer = models.ForeignKey(
        'crm.Customer', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='quality_incidents',
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_quality_incidents',
    )
    description = models.TextField(blank=True)
    cause = models.TextField(blank=True)
    corrective_action = models.TextField(blank=True)
    due_at = models.DateField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    related_object_type = models.CharField(max_length=80, blank=True)
    related_object_id = models.CharField(max_length=80, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_quality_incidents',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'quality_incidents'
        verbose_name = 'Incident qualité'
        verbose_name_plural = 'Incidents qualité'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['company', 'status', 'severity'])]

    def __str__(self):
        return f'[{self.get_severity_display()}] {self.title}'


class QualityIncidentComment(models.Model):
    incident = models.ForeignKey(QualityIncident, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'quality_incidents'
        verbose_name = 'Commentaire incident'
        ordering = ['created_at']
