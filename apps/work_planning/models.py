from datetime import time
from django.conf import settings
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal


class EmployeeProfile(models.Model):
    ROLE_CHOICES = [
        ('employee', 'Employé'),
        ('manager', 'Manager'),
        ('director', 'Directeur'),
        ('contractor', 'Prestataire'),
    ]

    company = models.ForeignKey(
        'core.Company', on_delete=models.CASCADE, related_name='employee_profiles',
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='work_planning_profiles',
    )
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default='employee')
    color_code = models.CharField(max_length=7, default='#6366F1', help_text='Couleur hex pour le planning')
    default_hours_per_day = models.DecimalField(max_digits=4, decimal_places=1, default=Decimal('8.0'))
    weekly_capacity_hours = models.DecimalField(max_digits=5, decimal_places=1, default=Decimal('35.0'))
    skills = models.JSONField(
        default=list, blank=True,
        help_text='Liste de compétences : support, ecommerce, logistique, technique, creation...',
    )
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    # Heures supplémentaires
    accepts_overtime = models.BooleanField(
        default=False,
        verbose_name='Accepte les heures supplémentaires',
    )
    max_overtime_hours_per_week = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        verbose_name='Maximum heures supplémentaires / semaine',
    )

    # Horaires normaux
    normal_work_start = models.TimeField(
        default=time(9, 0),
        verbose_name='Début journée normale',
    )
    normal_work_end = models.TimeField(
        default=time(17, 0),
        verbose_name='Fin journée normale',
    )
    lunch_break_start = models.TimeField(
        null=True, blank=True,
        verbose_name='Début pause déjeuner',
    )
    lunch_break_end = models.TimeField(
        null=True, blank=True,
        verbose_name='Fin pause déjeuner',
    )
    planning_notes = models.TextField(
        blank=True,
        verbose_name='Notes planning',
        help_text='Exemple : ne pas planifier après 16h30 le mercredi.',
    )

    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('company', 'user')
        ordering = ['user__last_name', 'user__first_name']
        verbose_name = 'Profil employé'
        verbose_name_plural = 'Profils employés'

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.company.name})"

    @property
    def display_name(self):
        return self.user.get_full_name() or self.user.username

    def has_skill(self, skill):
        return skill in (self.skills or [])


class EmployeeAvailabilityConstraint(models.Model):
    """
    Contraintes personnelles, familiales ou professionnelles d'un salarié.
    Exemple : chercher sa fille à 16h30, rendez-vous médical, indisponibilité récurrente.
    """

    CONSTRAINT_TYPE_CHOICES = [
        ('family', 'Familiale'),
        ('personal', 'Personnelle'),
        ('medical', 'Médicale'),
        ('school', 'École / enfant'),
        ('transport', 'Transport'),
        ('fixed_meeting', 'Réunion fixe'),
        ('other', 'Autre'),
    ]

    PRIORITY_CHOICES = [
        ('soft', 'Souple'),
        ('important', 'Importante'),
        ('blocking', 'Bloquante'),
    ]

    RECURRENCE_CHOICES = [
        ('none', 'Aucune (ponctuelle)'),
        ('daily', 'Tous les jours'),
        ('weekly', 'Chaque semaine'),
        ('monthly', 'Chaque mois'),
    ]

    WEEKDAY_CHOICES = [
        (0, 'Lundi'), (1, 'Mardi'), (2, 'Mercredi'),
        (3, 'Jeudi'), (4, 'Vendredi'), (5, 'Samedi'), (6, 'Dimanche'),
    ]

    company = models.ForeignKey(
        'core.Company', on_delete=models.CASCADE,
        related_name='employee_availability_constraints',
    )
    employee = models.ForeignKey(
        'work_planning.EmployeeProfile', on_delete=models.CASCADE,
        related_name='availability_constraints',
    )
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    constraint_type = models.CharField(
        max_length=40, choices=CONSTRAINT_TYPE_CHOICES, default='personal',
    )
    priority = models.CharField(
        max_length=40, choices=PRIORITY_CHOICES, default='blocking',
    )
    recurrence = models.CharField(
        max_length=40, choices=RECURRENCE_CHOICES, default='none',
    )
    weekday = models.PositiveSmallIntegerField(
        choices=WEEKDAY_CHOICES, null=True, blank=True,
        help_text='Utilisé pour les contraintes hebdomadaires.',
    )
    starts_at = models.DateTimeField(
        null=True, blank=True,
        help_text='Début pour contrainte ponctuelle.',
    )
    ends_at = models.DateTimeField(
        null=True, blank=True,
        help_text='Fin pour contrainte ponctuelle.',
    )
    start_time = models.TimeField(
        null=True, blank=True,
        help_text='Heure de début pour contrainte récurrente.',
    )
    end_time = models.TimeField(
        null=True, blank=True,
        help_text='Heure de fin pour contrainte récurrente.',
    )
    is_active = models.BooleanField(default=True)
    can_be_overridden_by_manager = models.BooleanField(
        default=False,
        help_text='Permet à un manager de forcer manuellement. Jamais automatiquement.',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_employee_constraints',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['employee', 'weekday', 'start_time']
        indexes = [
            models.Index(fields=['company', 'employee', 'is_active']),
            models.Index(fields=['priority']),
            models.Index(fields=['recurrence']),
            models.Index(fields=['weekday']),
        ]
        verbose_name = 'Contrainte disponibilité salarié'
        verbose_name_plural = 'Contraintes disponibilité salariés'

    def __str__(self):
        return f"{self.employee} — {self.title}"


class WorkMission(models.Model):
    STATUS_CHOICES = [
        ('active', 'En cours'),
        ('paused', 'En pause'),
        ('completed', 'Terminée'),
        ('cancelled', 'Annulée'),
    ]
    PRIORITY_CHOICES = [
        ('low', 'Basse'),
        ('normal', 'Normale'),
        ('high', 'Haute'),
        ('urgent', 'Urgente'),
    ]

    company = models.ForeignKey(
        'core.Company', on_delete=models.CASCADE, related_name='work_missions',
    )
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=30, blank=True, help_text='Code court de référence')
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal')
    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField(null=True, blank=True)
    estimated_hours = models.DecimalField(max_digits=8, decimal_places=1, null=True, blank=True)
    color_code = models.CharField(max_length=7, default='#0EA5E9')
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_work_missions',
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-priority', 'name']
        verbose_name = 'Mission'
        verbose_name_plural = 'Missions'

    def __str__(self):
        return f"[{self.code}] {self.name}" if self.code else self.name

    @property
    def is_active(self):
        return self.status == 'active'

    @property
    def tasks_count(self):
        return self.tasks.count()

    @property
    def total_hours_logged(self):
        result = self.time_blocks.aggregate(total=models.Sum('hours'))
        return result['total'] or Decimal('0')


class CustomerRequest(models.Model):
    SOURCE_CHOICES = [
        ('manual', 'Manuelle'),
        ('website', 'Site web'),
        ('email', 'Email'),
        ('phone', 'Téléphone'),
        ('chat', 'Chat'),
        ('erp', 'ERP'),
        ('other', 'Autre'),
    ]
    STATUS_CHOICES = [
        ('new', 'Nouvelle'),
        ('qualified', 'Qualifiée'),
        ('planned', 'Planifiée'),
        ('in_progress', 'En cours'),
        ('waiting_customer', 'En attente client'),
        ('completed', 'Terminée'),
        ('cancelled', 'Annulée'),
    ]
    URGENCY_CHOICES = [
        ('low', 'Faible'),
        ('normal', 'Normale'),
        ('high', 'Haute'),
        ('urgent', 'Urgente'),
        ('critical', 'Critique'),
    ]

    company = models.ForeignKey(
        'core.Company', on_delete=models.CASCADE, related_name='customer_requests',
    )
    customer = models.ForeignKey(
        'crm.Customer', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='planning_requests',
    )
    website = models.ForeignKey(
        'websites.Website', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='customer_requests',
    )
    brand_key = models.CharField(max_length=50, blank=True)
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    source = models.CharField(max_length=40, choices=SOURCE_CHOICES, default='manual')
    status = models.CharField(max_length=40, choices=STATUS_CHOICES, default='new')
    urgency = models.CharField(max_length=40, choices=URGENCY_CHOICES, default='normal')
    requested_deadline = models.DateField(null=True, blank=True)
    estimated_minutes = models.PositiveIntegerField(
        default=60, help_text='Temps estimé en minutes pour traiter la demande.',
    )
    required_skill = models.CharField(
        max_length=120, blank=True,
        help_text='Compétence requise : support, logistique, ecommerce, technique, creation...',
    )
    assigned_employee = models.ForeignKey(
        'work_planning.EmployeeProfile', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_customer_requests',
    )
    mission = models.ForeignKey(
        'work_planning.WorkMission', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='customer_requests',
    )
    created_task = models.ForeignKey(
        'work_planning.WorkTask', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='source_customer_requests',
    )
    auto_planning_enabled = models.BooleanField(default=True)
    is_locked = models.BooleanField(
        default=False, help_text='Empêche la planification automatique de modifier cette demande.',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_customer_requests',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'status']),
            models.Index(fields=['company', 'urgency']),
            models.Index(fields=['requested_deadline']),
        ]
        verbose_name = 'Demande client'
        verbose_name_plural = 'Demandes clients'

    def __str__(self):
        return self.title

    @property
    def estimated_hours(self):
        return Decimal(self.estimated_minutes) / 60


class WorkTask(models.Model):
    STATUS_CHOICES = [
        ('todo', 'À faire'),
        ('in_progress', 'En cours'),
        ('review', 'En revue'),
        ('done', 'Terminée'),
    ]
    PRIORITY_CHOICES = [
        ('low', 'Basse'),
        ('normal', 'Normale'),
        ('high', 'Haute'),
        ('urgent', 'Urgente'),
    ]

    mission = models.ForeignKey(
        WorkMission, on_delete=models.CASCADE, related_name='tasks',
    )
    customer_request = models.ForeignKey(
        CustomerRequest, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tasks',
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='todo')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal')
    estimated_hours = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    estimated_minutes = models.PositiveIntegerField(default=0, help_text='Temps estimé en minutes (utilisé par le planificateur)')
    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_work_tasks',
    )
    due_date = models.DateField(null=True, blank=True)
    auto_scheduled = models.BooleanField(default=False)
    is_locked = models.BooleanField(default=False, help_text='Créneau verrouillé, non déplaçable automatiquement')
    scheduler_score = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0'))
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'created_at']
        verbose_name = 'Tâche'
        verbose_name_plural = 'Tâches'

    def __str__(self):
        return f"{self.mission.name} › {self.name}"

    @property
    def is_done(self):
        return self.status == 'done'

    @property
    def hours_logged(self):
        result = self.time_blocks.aggregate(total=models.Sum('hours'))
        return result['total'] or Decimal('0')

    def get_effective_hours(self):
        if self.estimated_minutes:
            return Decimal(self.estimated_minutes) / 60
        return self.estimated_hours or Decimal('1')


class DedicatedTimeBlock(models.Model):
    company = models.ForeignKey(
        'core.Company', on_delete=models.CASCADE, related_name='time_blocks',
    )
    employee = models.ForeignKey(
        EmployeeProfile, on_delete=models.CASCADE, related_name='time_blocks',
    )
    mission = models.ForeignKey(
        WorkMission, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='time_blocks',
    )
    task = models.ForeignKey(
        WorkTask, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='time_blocks',
    )
    date = models.DateField()
    hours = models.DecimalField(max_digits=4, decimal_places=1)
    note = models.TextField(blank=True)
    is_locked = models.BooleanField(default=False, help_text='Créneau verrouillé, non déplaçable par la planification auto')
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_time_blocks',
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['date', 'employee']
        verbose_name = 'Bloc de temps dédié'
        verbose_name_plural = 'Blocs de temps dédiés'

    def __str__(self):
        mission_name = self.mission.name if self.mission else '—'
        return f"{self.employee.display_name} — {self.date} — {self.hours}h ({mission_name})"


class PlanningConflict(models.Model):
    company = models.ForeignKey(
        'core.Company', on_delete=models.CASCADE, related_name='wp_planning_conflicts',
    )
    employee = models.ForeignKey(
        EmployeeProfile, on_delete=models.CASCADE, related_name='planning_conflicts',
    )
    date = models.DateField()
    total_hours_planned = models.DecimalField(max_digits=5, decimal_places=1)
    max_hours = models.DecimalField(max_digits=4, decimal_places=1)
    resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('company', 'employee', 'date')
        ordering = ['-date']
        verbose_name = 'Conflit de planning'
        verbose_name_plural = 'Conflits de planning'

    def __str__(self):
        return f"Conflit {self.employee.display_name} — {self.date} ({self.total_hours_planned}h / {self.max_hours}h max)"

    @property
    def overflow_hours(self):
        return self.total_hours_planned - self.max_hours
