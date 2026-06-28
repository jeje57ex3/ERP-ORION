from django.db import models
from django.conf import settings
from apps.core.models import Company


TRIGGER_TYPE_CHOICES = [
    ('invoice_overdue', 'Facture en retard'),
    ('stock_low', 'Stock faible'),
    ('new_customer', 'Nouveau client'),
    ('new_order', 'Nouvelle commande'),
    ('order_paid', 'Commande payée'),
    ('quote_not_followed', 'Devis sans suite'),
    ('domain_error', 'Erreur domaine'),
    ('backup_failed', 'Sauvegarde échouée'),
    ('employee_missing_timesheet', 'Pointage manquant'),
    ('project_starts_tomorrow', 'Chantier démarre demain'),
    ('cart_abandoned', 'Panier abandonné'),
    ('scheduled', 'Planifié (CRON)'),
    ('manual', 'Déclenchement manuel'),
]

RUN_STATUS_CHOICES = [
    ('pending', 'En attente'),
    ('running', 'En cours'),
    ('success', 'Succès'),
    ('failed', 'Échoué'),
    ('skipped', 'Ignoré'),
]


class AutomationRule(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='automation_rules')
    name = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    trigger_type = models.CharField(max_length=100, choices=TRIGGER_TYPE_CHOICES)
    conditions = models.JSONField(default=list, blank=True)
    actions = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    run_count = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_automation_rules',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'smart_automations'
        verbose_name = 'Règle d\'automatisation'
        verbose_name_plural = 'Règles d\'automatisation'
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class AutomationRun(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='automation_runs')
    rule = models.ForeignKey(AutomationRule, on_delete=models.CASCADE, related_name='runs')
    status = models.CharField(max_length=30, choices=RUN_STATUS_CHOICES, default='pending')
    trigger_payload = models.JSONField(default=dict, blank=True)
    result_payload = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='triggered_automation_runs',
    )
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'smart_automations'
        verbose_name = 'Exécution automatisation'
        verbose_name_plural = 'Exécutions automatisations'
        ordering = ['-started_at']

    def __str__(self):
        return f'{self.rule.name} — {self.get_status_display()} ({self.started_at:%d/%m/%Y %H:%M})'

    @property
    def duration_seconds(self):
        if self.finished_at and self.started_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None
