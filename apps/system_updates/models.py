from django.conf import settings
from django.db import models
from django.utils import timezone


class SystemUpdateSettings(models.Model):
    update_enabled = models.BooleanField(default=True)
    manual_only = models.BooleanField(default=True)

    git_remote = models.CharField(max_length=120, default='origin')
    git_branch = models.CharField(max_length=120, default='main')
    github_token_encrypted = models.TextField(
        blank=True,
        help_text="Jeton d'accès personnel GitHub (chiffré), requis si le dépôt est privé.",
    )

    require_backup_before_update = models.BooleanField(default=True)
    require_health_check_before_update = models.BooleanField(default=True)
    allow_rollback = models.BooleanField(default=True)

    update_backend_enabled = models.BooleanField(default=True)
    update_frontend_siecle_enabled = models.BooleanField(default=True)
    update_frontend_lunea_enabled = models.BooleanField(default=True)

    run_migrations = models.BooleanField(default=True)
    collect_static = models.BooleanField(default=True)
    restart_services = models.BooleanField(default=True)

    maintenance_mode_during_update = models.BooleanField(default=True)

    notify_admins = models.BooleanField(default=True)
    notify_email = models.EmailField(blank=True)

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'system_updates'
        verbose_name = 'Paramètres mises à jour'
        verbose_name_plural = 'Paramètres mises à jour'

    def __str__(self):
        return 'Paramètres mises à jour Orion'

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj


class SystemUpdateCheck(models.Model):
    STATUS_CHOICES = [
        ('checking', 'Vérification en cours'),
        ('up_to_date', 'À jour'),
        ('update_available', 'Mise à jour disponible'),
        ('failed', 'Échec'),
    ]

    status = models.CharField(max_length=40, choices=STATUS_CHOICES, default='checking')

    current_version = models.CharField(max_length=80, blank=True)
    current_commit = models.CharField(max_length=120, blank=True)

    remote_version = models.CharField(max_length=80, blank=True)
    remote_commit = models.CharField(max_length=120, blank=True)

    commits_behind = models.PositiveIntegerField(default=0)
    commits_ahead = models.PositiveIntegerField(default=0)

    branch = models.CharField(max_length=120, blank=True)

    changelog = models.TextField(blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)

    error_message = models.TextField(blank=True)

    checked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    checked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'system_updates'
        ordering = ['-checked_at']

    def __str__(self):
        return f'Check update {self.status} — {self.checked_at}'


class SystemUpdateRun(models.Model):
    STATUS_CHOICES = [
        ('planned', 'Planifiée'),
        ('running', 'En cours'),
        ('success', 'Succès'),
        ('failed', 'Échec'),
        ('cancelled', 'Annulée'),
        ('rolled_back', 'Rollback effectué'),
    ]

    status = models.CharField(max_length=40, choices=STATUS_CHOICES, default='planned')

    from_commit = models.CharField(max_length=120, blank=True)
    to_commit = models.CharField(max_length=120, blank=True)

    from_version = models.CharField(max_length=80, blank=True)
    to_version = models.CharField(max_length=80, blank=True)

    backup_reference = models.CharField(max_length=255, blank=True)
    maintenance_enabled = models.BooleanField(default=False)

    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    error_message = models.TextField(blank=True)
    result_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        app_label = 'system_updates'
        ordering = ['-started_at']

    def __str__(self):
        return f'Mise à jour #{self.id} — {self.status}'


class SystemUpdateStepLog(models.Model):
    LEVEL_CHOICES = [
        ('info', 'Info'),
        ('success', 'Succès'),
        ('warning', 'Avertissement'),
        ('error', 'Erreur'),
    ]

    update_run = models.ForeignKey(
        SystemUpdateRun,
        on_delete=models.CASCADE,
        related_name='logs',
    )
    step_code = models.CharField(max_length=120)
    step_name = models.CharField(max_length=180)
    level = models.CharField(max_length=40, choices=LEVEL_CHOICES, default='info')
    message = models.TextField(blank=True)
    command = models.TextField(blank=True)
    output = models.TextField(blank=True)
    error_output = models.TextField(blank=True)

    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        app_label = 'system_updates'
        ordering = ['started_at']

    def __str__(self):
        return f'{self.step_code} — {self.level}'


class SystemRollbackRun(models.Model):
    STATUS_CHOICES = [
        ('running', 'En cours'),
        ('success', 'Succès'),
        ('failed', 'Échec'),
    ]

    update_run = models.ForeignKey(
        SystemUpdateRun,
        on_delete=models.CASCADE,
        related_name='rollback_runs',
    )
    status = models.CharField(max_length=40, choices=STATUS_CHOICES, default='running')
    rollback_to_commit = models.CharField(max_length=120)
    backup_reference = models.CharField(max_length=255, blank=True)

    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    error_message = models.TextField(blank=True)
    result_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        app_label = 'system_updates'
        ordering = ['-started_at']

    def __str__(self):
        return f'Rollback #{self.id} → {self.rollback_to_commit[:8]} — {self.status}'


class ServerActionLog(models.Model):
    ACTION_CHOICES = [
        ('reboot',   'Redémarrage'),
        ('shutdown', 'Extinction'),
        ('cancel',   'Annulation'),
    ]
    STATUS_CHOICES = [
        ('success', 'Succès'),
        ('failed',  'Échec'),
    ]

    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    message = models.TextField(blank=True)

    executed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    executed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'system_updates'
        ordering = ['-executed_at']
        verbose_name = 'Action serveur'
        verbose_name_plural = 'Actions serveur'

    def __str__(self):
        return f'{self.get_action_display()} — {self.get_status_display()} ({self.executed_at:%d/%m/%Y %H:%M})'
