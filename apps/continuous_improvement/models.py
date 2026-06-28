from django.conf import settings
from django.db import models
from django.utils import timezone


class PDCACycle(models.Model):
    STAGE_CHOICES = [
        ('plan', 'Planifier'),
        ('do', 'Faire'),
        ('check', 'Vérifier'),
        ('act', 'Agir'),
        ('closed', 'Clôturé'),
    ]

    STATUS_CHOICES = [
        ('draft', 'Brouillon'),
        ('active', 'Actif'),
        ('paused', 'En pause'),
        ('completed', 'Terminé'),
        ('failed', 'Échec'),
        ('cancelled', 'Annulé'),
    ]

    CATEGORY_CHOICES = [
        ('quality', 'Qualité'),
        ('bug', 'Bug'),
        ('sales', 'Ventes'),
        ('shop', 'Boutique'),
        ('customer_service', 'Service client'),
        ('supplier', 'Fournisseur'),
        ('stock', 'Stock'),
        ('payment', 'Paiement'),
        ('delivery', 'Livraison'),
        ('system_health', 'Santé système'),
        ('updates', 'Mises à jour'),
        ('security', 'Sécurité'),
        ('marketing', 'Marketing'),
        ('operations', 'Opérations'),
        ('other', 'Autre'),
    ]

    PRIORITY_CHOICES = [
        ('low', 'Basse'),
        ('medium', 'Moyenne'),
        ('high', 'Haute'),
        ('critical', 'Critique'),
    ]

    company = models.ForeignKey(
        'core.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='pdca_cycles',
    )

    brand_key = models.CharField(max_length=40, blank=True, help_text='Exemple : siecle, lunea')

    title = models.CharField(max_length=220)
    problem_statement = models.TextField(help_text='Quel problème ou amélioration veut-on traiter ?')
    objective = models.TextField(help_text='Quel résultat veut-on atteindre ?')

    category = models.CharField(max_length=60, choices=CATEGORY_CHOICES, default='quality')
    priority = models.CharField(max_length=40, choices=PRIORITY_CHOICES, default='medium')

    stage = models.CharField(max_length=40, choices=STAGE_CHOICES, default='plan')
    status = models.CharField(max_length=40, choices=STATUS_CHOICES, default='draft')

    root_cause = models.TextField(blank=True)
    expected_result = models.TextField(blank=True)
    actual_result = models.TextField(blank=True)

    success_criteria = models.TextField(blank=True)
    failure_reason = models.TextField(blank=True)

    start_date = models.DateField(null=True, blank=True)
    target_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='owned_pdca_cycles',
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_pdca_cycles',
    )

    parent_cycle = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='child_cycles',
        help_text='Cycle précédent si amélioration relancée.',
    )

    related_module = models.CharField(max_length=80, blank=True)
    related_object_id = models.CharField(max_length=80, blank=True)

    ai_summary = models.TextField(blank=True)
    ai_recommendations = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'continuous_improvement'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'brand_key']),
            models.Index(fields=['stage', 'status']),
            models.Index(fields=['category', 'priority']),
        ]

    def __str__(self):
        return self.title

    @property
    def is_late(self):
        if not self.target_date:
            return False
        if self.status in ('completed', 'cancelled'):
            return False
        return self.target_date < timezone.now().date()

    @property
    def progress_percent(self):
        return {'plan': 25, 'do': 50, 'check': 75, 'act': 90, 'closed': 100}.get(self.stage, 0)


class PDCAPlan(models.Model):
    cycle = models.OneToOneField(PDCACycle, on_delete=models.CASCADE, related_name='plan')

    current_situation = models.TextField(blank=True)
    analysis = models.TextField(blank=True)
    root_causes = models.TextField(blank=True)
    risks = models.TextField(blank=True)
    assumptions = models.TextField(blank=True)
    planned_actions_summary = models.TextField(blank=True)

    baseline_metric_name = models.CharField(max_length=160, blank=True)
    baseline_metric_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    target_metric_name = models.CharField(max_length=160, blank=True)
    target_metric_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
    )
    validated_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'continuous_improvement'


class PDCADo(models.Model):
    cycle = models.OneToOneField(PDCACycle, on_delete=models.CASCADE, related_name='do')

    execution_summary = models.TextField(blank=True)
    difficulties = models.TextField(blank=True)
    deviations_from_plan = models.TextField(blank=True)

    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'continuous_improvement'


class PDCACheck(models.Model):
    RESULT_CHOICES = [
        ('not_checked', 'Non vérifié'),
        ('success', 'Succès'),
        ('partial', 'Partiel'),
        ('failed', 'Échec'),
    ]

    cycle = models.OneToOneField(PDCACycle, on_delete=models.CASCADE, related_name='pdca_check')

    measured_result = models.TextField(blank=True)
    data_sources = models.TextField(blank=True)
    result_status = models.CharField(max_length=40, choices=RESULT_CHOICES, default='not_checked')

    measured_metric_name = models.CharField(max_length=160, blank=True)
    measured_metric_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    gap_analysis = models.TextField(blank=True)
    lessons_learned = models.TextField(blank=True)

    checked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
    )
    checked_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'continuous_improvement'


class PDCAAct(models.Model):
    DECISION_CHOICES = [
        ('standardize', 'Standardiser'),
        ('adjust', 'Ajuster'),
        ('restart_cycle', 'Relancer un cycle'),
        ('abandon', 'Abandonner'),
    ]

    cycle = models.OneToOneField(PDCACycle, on_delete=models.CASCADE, related_name='act')

    decision = models.CharField(max_length=40, choices=DECISION_CHOICES, blank=True)
    decision_reason = models.TextField(blank=True)
    standardization_notes = models.TextField(blank=True)
    next_steps = models.TextField(blank=True)
    create_new_cycle = models.BooleanField(default=False)

    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'continuous_improvement'


class PDCAAction(models.Model):
    STATUS_CHOICES = [
        ('todo', 'À faire'),
        ('in_progress', 'En cours'),
        ('blocked', 'Bloqué'),
        ('done', 'Terminé'),
        ('cancelled', 'Annulé'),
    ]

    cycle = models.ForeignKey(PDCACycle, on_delete=models.CASCADE, related_name='actions')

    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=40, choices=STATUS_CHOICES, default='todo')

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_pdca_actions',
    )

    due_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    order = models.PositiveIntegerField(default=100)
    evidence = models.TextField(blank=True)
    attachment = models.FileField(upload_to='pdca/actions/', null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_pdca_actions',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'continuous_improvement'
        ordering = ['order', 'due_date', 'created_at']

    def __str__(self):
        return self.title


class PDCAKPI(models.Model):
    cycle = models.ForeignKey(PDCACycle, on_delete=models.CASCADE, related_name='kpis')

    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    unit = models.CharField(max_length=40, blank=True)

    before_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    target_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    after_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    source_module = models.CharField(max_length=80, blank=True)
    measured_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'continuous_improvement'

    def __str__(self):
        return self.name

    @property
    def improvement_value(self):
        if self.before_value is None or self.after_value is None:
            return None
        return self.after_value - self.before_value

    @property
    def target_reached(self):
        if self.target_value is None or self.after_value is None:
            return False
        return self.after_value >= self.target_value


class PDCAStandard(models.Model):
    company = models.ForeignKey(
        'core.Company', on_delete=models.CASCADE, null=True, blank=True,
        related_name='pdca_standards',
    )
    brand_key = models.CharField(max_length=40, blank=True)

    cycle = models.ForeignKey(
        PDCACycle, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='standards',
    )

    title = models.CharField(max_length=220)
    description = models.TextField()
    module = models.CharField(max_length=80, blank=True)
    procedure = models.TextField(blank=True)
    checklist = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'continuous_improvement'
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class PDCATemplate(models.Model):
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)

    category = models.CharField(max_length=60, choices=PDCACycle.CATEGORY_CHOICES, default='quality')
    priority = models.CharField(max_length=40, choices=PDCACycle.PRIORITY_CHOICES, default='medium')

    default_problem_statement = models.TextField(blank=True)
    default_objective = models.TextField(blank=True)
    default_success_criteria = models.TextField(blank=True)

    default_actions = models.JSONField(default=list, blank=True)
    default_kpis = models.JSONField(default=list, blank=True)

    related_module = models.CharField(max_length=80, blank=True)
    is_system_template = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'continuous_improvement'
        ordering = ['category', 'title']

    def __str__(self):
        return self.title


class PDCAEventLog(models.Model):
    cycle = models.ForeignKey(PDCACycle, on_delete=models.CASCADE, related_name='event_logs')

    event_type = models.CharField(max_length=80)
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    payload = models.JSONField(default=dict, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'continuous_improvement'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.event_type} — {self.title}'
