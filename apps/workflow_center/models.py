from django.db import models
from django.conf import settings
from apps.core.models import Company


class WorkflowTemplate(models.Model):
    OBJECT_TYPE_CHOICES = [
        ('quote', 'Devis'), ('invoice', 'Facture'), ('purchase_order', 'Commande achat'),
        ('leave_request', 'Congé'), ('expense_report', 'Note de frais'),
        ('refund', 'Remboursement'), ('website_publish', 'Publication site'),
        ('customer_review', 'Avis client'), ('portal_signup', 'Inscription portail'),
        ('document', 'Document'), ('custom', 'Personnalisé'),
    ]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='workflow_templates')
    name = models.CharField(max_length=180)
    code = models.CharField(max_length=100)
    object_type = models.CharField(max_length=80, choices=OBJECT_TYPE_CHOICES)
    steps = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'workflow_center'
        verbose_name = 'Modèle de workflow'
        verbose_name_plural = 'Modèles de workflow'
        unique_together = [('company', 'code')]

    def __str__(self):
        return self.name


class WorkflowInstance(models.Model):
    STATUS_CHOICES = [
        ('pending', 'En attente'), ('in_progress', 'En cours'),
        ('approved', 'Approuvé'), ('rejected', 'Rejeté'), ('cancelled', 'Annulé'),
    ]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='workflow_instances')
    template = models.ForeignKey(WorkflowTemplate, on_delete=models.SET_NULL, null=True, blank=True)
    object_type = models.CharField(max_length=80)
    object_id = models.CharField(max_length=80)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')
    current_step_index = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='created_workflow_instances',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'workflow_center'
        verbose_name = 'Instance workflow'
        verbose_name_plural = 'Instances workflow'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['company', 'status'])]

    def __str__(self):
        return f'{self.object_type} #{self.object_id} — {self.get_status_display()}'

    @property
    def current_step(self):
        if self.template and self.template.steps:
            steps = self.template.steps
            if self.current_step_index < len(steps):
                return steps[self.current_step_index]
        return None


class WorkflowAction(models.Model):
    ACTION_CHOICES = [
        ('approve', 'Approuver'), ('reject', 'Rejeter'),
        ('comment', 'Commenter'), ('cancel', 'Annuler'),
    ]
    instance = models.ForeignKey(WorkflowInstance, on_delete=models.CASCADE, related_name='actions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=40, choices=ACTION_CHOICES)
    step_index = models.PositiveIntegerField(default=0)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'workflow_center'
        verbose_name = 'Action workflow'
        verbose_name_plural = 'Actions workflow'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.instance} — {self.get_action_display()} par {self.user}'
