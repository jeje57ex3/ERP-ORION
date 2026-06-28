from django.db import models
from django.conf import settings
from apps.core.models import Company


JOB_TYPE_CHOICES = [
    ('full_db', 'Base de données complète'), ('incremental_db', 'BDD incrémentale'),
    ('media_files', 'Fichiers media'), ('config', 'Configuration'),
    ('full_system', 'Système complet'),
]

STORAGE_TARGET_CHOICES = [
    ('local', 'Local'), ('s3', 'Amazon S3'), ('gcs', 'Google Cloud Storage'),
    ('azure_blob', 'Azure Blob'), ('ftp', 'FTP/SFTP'), ('email', 'E-mail'),
]

STATUS_CHOICES = [
    ('pending', 'En attente'), ('running', 'En cours'),
    ('success', 'Succès'), ('failed', 'Échec'), ('partial', 'Partiel'),
]

SCHEDULE_CHOICES = [
    ('manual', 'Manuel'), ('hourly', 'Toutes les heures'),
    ('daily', 'Quotidien'), ('weekly', 'Hebdomadaire'), ('monthly', 'Mensuel'),
]


class BackupJob(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='backup_center_jobs')
    name = models.CharField(max_length=180)
    job_type = models.CharField(max_length=40, choices=JOB_TYPE_CHOICES)
    schedule = models.CharField(max_length=30, choices=SCHEDULE_CHOICES, default='manual')
    storage_target = models.CharField(max_length=40, choices=STORAGE_TARGET_CHOICES, default='local')
    storage_config = models.JSONField(default=dict, blank=True)
    retention_days = models.PositiveIntegerField(default=30)
    is_active = models.BooleanField(default=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    last_status = models.CharField(max_length=30, choices=STATUS_CHOICES, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_backup_jobs',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'backup_center'
        verbose_name = 'Tâche de sauvegarde'
        verbose_name_plural = 'Tâches de sauvegarde'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.get_job_type_display()})'


class BackupRun(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='backup_runs')
    job = models.ForeignKey(BackupJob, on_delete=models.SET_NULL, null=True, related_name='runs')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')
    file_path = models.CharField(max_length=500, blank=True)
    file_size_bytes = models.BigIntegerField(default=0)
    checksum = models.CharField(max_length=128, blank=True)
    error_message = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='triggered_backup_runs',
    )
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'backup_center'
        verbose_name = 'Exécution sauvegarde'
        verbose_name_plural = 'Exécutions sauvegarde'
        ordering = ['-started_at']
        indexes = [models.Index(fields=['company', 'status', 'started_at'])]

    def __str__(self):
        return f'{self.job} — {self.get_status_display()} ({self.started_at:%d/%m/%Y})'

    @property
    def duration_seconds(self):
        if self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None

    @property
    def file_size_mb(self):
        return round(self.file_size_bytes / 1024 / 1024, 2)
