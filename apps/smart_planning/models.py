from django.db import models
from django.conf import settings
from apps.core.models import Company


EVENT_TYPE_CHOICES = [
    ('employee_shift', 'Vacation salarié'), ('site_visit', 'Visite chantier'),
    ('customer_appointment', 'RDV client'), ('intervention', 'Intervention'),
    ('leave', 'Congé'), ('training', 'Formation'),
    ('delivery', 'Livraison'), ('meeting', 'Réunion'), ('other', 'Autre'),
]

STATUS_CHOICES = [
    ('planned', 'Planifié'), ('confirmed', 'Confirmé'),
    ('in_progress', 'En cours'), ('done', 'Terminé'), ('cancelled', 'Annulé'),
]


class PlanningEvent(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='planning_events')
    title = models.CharField(max_length=180)
    event_type = models.CharField(max_length=80, choices=EVENT_TYPE_CHOICES)
    employee = models.ForeignKey(
        'hr.Employee', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='planning_events',
    )
    customer = models.ForeignKey(
        'crm.Customer', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='planning_events',
    )
    project_id = models.CharField(max_length=80, blank=True)
    location = models.CharField(max_length=255, blank=True)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    status = models.CharField(max_length=40, choices=STATUS_CHOICES, default='planned')
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_planning_events',
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'smart_planning'
        verbose_name = 'Événement planning'
        verbose_name_plural = 'Événements planning'
        ordering = ['start_at']
        indexes = [
            models.Index(fields=['company', 'start_at', 'end_at']),
            models.Index(fields=['company', 'employee', 'start_at']),
        ]

    def __str__(self):
        return f'{self.title} ({self.start_at:%d/%m/%Y})'

    @property
    def duration_hours(self):
        return (self.end_at - self.start_at).total_seconds() / 3600


class PlanningConflict(models.Model):
    CONFLICT_TYPE_CHOICES = [
        ('double_booking', 'Double réservation'), ('overload', 'Surcharge'),
        ('leave_overlap', 'Chevauchement congé'), ('other', 'Autre'),
    ]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='planning_conflicts')
    event = models.ForeignKey(PlanningEvent, on_delete=models.CASCADE, related_name='conflicts')
    conflicting_event = models.ForeignKey(
        PlanningEvent, on_delete=models.CASCADE, null=True, blank=True,
        related_name='conflicted_by',
    )
    conflict_type = models.CharField(max_length=80, choices=CONFLICT_TYPE_CHOICES)
    message = models.TextField()
    severity = models.CharField(max_length=30, default='normal')
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'smart_planning'
        verbose_name = 'Conflit planning'
        verbose_name_plural = 'Conflits planning'
        ordering = ['-created_at']

    def __str__(self):
        return f'Conflit : {self.event.title} — {self.get_conflict_type_display()}'
