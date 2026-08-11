"""
apps/backups/models.py — Modèles système de sauvegardes Orion ERP
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class BackupJob(models.Model):
    BACKUP_TYPE_CHOICES = [
        ('manual',        'Manuel'),
        ('scheduled',     'Planifié'),
        ('pre_restore',   'Pré-restauration'),
        ('pre_migration', 'Pré-migration'),
        ('system',        'Système'),
        ('imported',      'Importé'),
    ]

    SCOPE_CHOICES = [
        ('core_database',    'Base centrale'),
        ('company_database', 'Base entreprise'),
        ('all_companies',    'Toutes les entreprises'),
        ('media_files',      'Fichiers médias'),
        ('documents',        'Documents'),
        ('full_system',      'Système complet'),
        ('portable_export',  'Export portable (base + médias, transfert entre instances)'),
    ]

    STATUS_CHOICES = [
        ('pending',   'En attente'),
        ('running',   'En cours'),
        ('success',   'Succès'),
        ('failed',    'Échoué'),
        ('cancelled', 'Annulé'),
    ]

    company = models.ForeignKey(
        'core.Company', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='backup_jobs',
        verbose_name='Entreprise',
    )
    name          = models.CharField('Nom', max_length=255)
    backup_type   = models.CharField('Type', max_length=20, choices=BACKUP_TYPE_CHOICES, default='manual')
    scope         = models.CharField('Périmètre', max_length=30, choices=SCOPE_CHOICES, default='company_database')
    status        = models.CharField('Statut', max_length=20, choices=STATUS_CHOICES, default='pending')
    file_path     = models.CharField('Chemin fichier', max_length=500, blank=True)
    file_size     = models.BigIntegerField('Taille (octets)', null=True, blank=True)
    checksum      = models.CharField('Checksum SHA-256', max_length=64, blank=True)
    started_at    = models.DateTimeField('Début', null=True, blank=True)
    finished_at   = models.DateTimeField('Fin', null=True, blank=True)
    duration_seconds = models.FloatField('Durée (s)', null=True, blank=True)
    error_message = models.TextField('Erreur', blank=True)
    created_by    = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='backup_jobs_created', verbose_name='Créé par',
    )
    created_at    = models.DateTimeField('Créé le', auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Sauvegarde'
        verbose_name_plural = 'Sauvegardes'

    def __str__(self):
        return f"{self.name} — {self.get_status_display()}"

    @property
    def file_size_display(self):
        if not self.file_size:
            return '—'
        size = float(self.file_size)
        for unit in ['o', 'Ko', 'Mo', 'Go']:
            if size < 1024:
                return f'{size:.1f} {unit}'
            size /= 1024
        return f'{size:.1f} To'

    @property
    def duration_display(self):
        if not self.duration_seconds:
            return '—'
        d = int(self.duration_seconds)
        if d < 60:
            return f'{d}s'
        return f'{d // 60}m {d % 60}s'

    @property
    def status_color(self):
        return {
            'pending':   'secondary',
            'running':   'primary',
            'success':   'success',
            'failed':    'danger',
            'cancelled': 'warning',
        }.get(self.status, 'secondary')

    @property
    def status_icon(self):
        return {
            'pending':   'bi-hourglass',
            'running':   'bi-arrow-repeat',
            'success':   'bi-check-circle',
            'failed':    'bi-x-circle',
            'cancelled': 'bi-slash-circle',
        }.get(self.status, 'bi-question-circle')


class BackupSchedule(models.Model):
    FREQUENCY_CHOICES = [
        ('daily',   'Quotidienne'),
        ('weekly',  'Hebdomadaire'),
        ('monthly', 'Mensuelle'),
    ]

    DAY_CHOICES = [
        (0, 'Lundi'), (1, 'Mardi'), (2, 'Mercredi'),
        (3, 'Jeudi'), (4, 'Vendredi'), (5, 'Samedi'), (6, 'Dimanche'),
    ]

    SCOPE_CHOICES = BackupJob.SCOPE_CHOICES

    company        = models.ForeignKey(
        'core.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='backup_schedules',
        verbose_name='Entreprise',
    )
    name           = models.CharField('Nom', max_length=200)
    scope          = models.CharField('Périmètre', max_length=30, choices=SCOPE_CHOICES, default='company_database')
    frequency      = models.CharField('Fréquence', max_length=10, choices=FREQUENCY_CHOICES, default='daily')
    time           = models.TimeField('Heure', default='02:00')
    day_of_week    = models.IntegerField('Jour de la semaine', choices=DAY_CHOICES, null=True, blank=True)
    retention_days = models.PositiveIntegerField('Rétention (jours)', default=30)
    is_active      = models.BooleanField('Actif', default=True)
    last_run_at    = models.DateTimeField('Dernier run', null=True, blank=True)
    next_run_at    = models.DateTimeField('Prochain run', null=True, blank=True)
    created_by     = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='backup_schedules_created', verbose_name='Créé par',
    )
    created_at     = models.DateTimeField('Créé le', auto_now_add=True)

    class Meta:
        ordering = ['frequency', 'time']
        verbose_name = 'Planification sauvegarde'
        verbose_name_plural = 'Planifications sauvegardes'

    def __str__(self):
        return f"{self.name} ({self.get_frequency_display()})"


class BackupRestoreLog(models.Model):
    STATUS_CHOICES = [
        ('running', 'En cours'),
        ('success', 'Succès'),
        ('failed',  'Échoué'),
    ]

    backup      = models.ForeignKey(BackupJob, on_delete=models.CASCADE, related_name='restore_logs', verbose_name='Sauvegarde')
    company     = models.ForeignKey(
        'core.Company', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='restore_logs', verbose_name='Entreprise',
    )
    status      = models.CharField('Statut', max_length=20, choices=STATUS_CHOICES, default='running')
    started_at  = models.DateTimeField('Début', auto_now_add=True)
    finished_at = models.DateTimeField('Fin', null=True, blank=True)
    restored_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='restore_logs', verbose_name='Restauré par',
    )
    error_message = models.TextField('Erreur', blank=True)
    created_at  = models.DateTimeField('Créé le', auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Log de restauration'
        verbose_name_plural = 'Logs de restauration'

    def __str__(self):
        return f"Restauration {self.backup.name} — {self.get_status_display()}"
