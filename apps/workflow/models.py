from django.db import models
from django.contrib.auth.models import User
from apps.core.models import Company


class WorkflowStep(models.Model):
    OBJECT_TYPES = [
        ('quote', 'Devis'), ('invoice', 'Facture'), ('purchase_order', 'Commande achat'),
        ('leave_request', 'Congé'), ('expense_report', 'Note de frais'),
        ('situation', 'Situation de travaux'), ('document', 'Document'),
    ]
    STATUS_CHOICES = [
        ('pending', 'En attente'), ('approved', 'Approuvé'), ('rejected', 'Rejeté'), ('cancelled', 'Annulé'),
    ]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='workflow_steps')
    object_type = models.CharField(max_length=30, choices=OBJECT_TYPES)
    object_id = models.PositiveIntegerField()
    step_number = models.PositiveIntegerField(default=1)
    validator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='validation_steps')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    comment = models.TextField(blank=True)
    validated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Étape workflow'

    def __str__(self):
        return f'{self.object_type} #{self.object_id} - Étape {self.step_number}'
