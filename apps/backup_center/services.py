from django.utils import timezone
from .models import BackupJob, BackupRun


def create_job(company, name, job_type, *, schedule='manual', storage_target='local',
               storage_config=None, retention_days=30, created_by=None):
    return BackupJob.objects.create(
        company=company, name=name, job_type=job_type,
        schedule=schedule, storage_target=storage_target,
        storage_config=storage_config or {}, retention_days=retention_days,
        created_by=created_by,
    )


def start_backup_run(company, job, triggered_by=None):
    run = BackupRun.objects.create(
        company=company, job=job, status='running',
        triggered_by=triggered_by,
    )
    job.last_run_at = timezone.now()
    job.last_status = 'running'
    job.save(update_fields=['last_run_at', 'last_status'])
    return run


def finish_backup_run(run, *, success=True, file_path='', file_size_bytes=0,
                      checksum='', error_message='', metadata=None):
    run.status = 'success' if success else 'failed'
    run.file_path = file_path
    run.file_size_bytes = file_size_bytes
    run.checksum = checksum
    run.error_message = error_message
    run.metadata = metadata or {}
    run.finished_at = timezone.now()
    run.save(update_fields=[
        'status', 'file_path', 'file_size_bytes', 'checksum',
        'error_message', 'metadata', 'finished_at',
    ])
    if run.job:
        run.job.last_status = run.status
        run.job.save(update_fields=['last_status'])
    return run


def get_backup_runs(company, job=None, limit=50):
    qs = BackupRun.objects.filter(company=company).select_related('job')
    if job:
        qs = qs.filter(job=job)
    return qs.order_by('-started_at')[:limit]


def get_recent_failures(company, limit=10):
    return BackupRun.objects.filter(
        company=company, status='failed'
    ).order_by('-started_at')[:limit]


def get_backup_stats(company):
    jobs = BackupJob.objects.filter(company=company)
    runs = BackupRun.objects.filter(company=company)
    from datetime import timedelta
    since_24h = timezone.now() - timedelta(hours=24)
    return {
        'total_jobs': jobs.count(),
        'active_jobs': jobs.filter(is_active=True).count(),
        'total_runs': runs.count(),
        'success_24h': runs.filter(status='success', started_at__gte=since_24h).count(),
        'failed_24h': runs.filter(status='failed', started_at__gte=since_24h).count(),
        'last_success': runs.filter(status='success').order_by('-started_at').first(),
    }
