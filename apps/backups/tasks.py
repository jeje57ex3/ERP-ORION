"""
apps/backups/tasks.py — Tâches Celery pour les sauvegardes
Nécessite Celery + Redis. Fonctionne aussi via management commands.
"""
try:
    from celery import shared_task
except ImportError:
    def shared_task(fn=None, **kwargs):
        if fn:
            return fn
        def decorator(f):
            return f
        return decorator


@shared_task(bind=True, max_retries=3)
def run_scheduled_backup(self, schedule_id):
    try:
        from apps.backups.models import BackupSchedule
        from apps.backups.services import create_database_backup, create_full_backup
        schedule = BackupSchedule.objects.get(pk=schedule_id)
        if not schedule.is_active:
            return 'Schedule inactif'
        if schedule.scope == 'full_system':
            create_full_backup(company=schedule.company)
        else:
            create_database_backup(company=schedule.company, scope=schedule.scope)
        from django.utils import timezone
        schedule.last_run_at = timezone.now()
        schedule.save()
        return f'OK: {schedule.name}'
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@shared_task
def run_company_backup(company_id):
    from apps.core.models import Company
    from apps.backups.services import create_database_backup
    try:
        company = Company.objects.get(pk=company_id)
        job = create_database_backup(company=company, scope='company_database')
        return f'Backup {company.name}: {job.status}'
    except Exception as e:
        return f'Erreur: {e}'


@shared_task
def run_full_system_backup():
    from apps.core.models import Company
    from apps.backups.services import create_database_backup, create_full_backup
    results = []
    core_job = create_database_backup(scope='core_database')
    results.append(f'Core: {core_job.status}')
    for company in Company.objects.filter(is_active=True):
        job = create_database_backup(company=company, scope='company_database')
        results.append(f'{company.name}: {job.status}')
    return results


@shared_task
def cleanup_old_backup_files():
    from apps.backups.services import cleanup_old_backups
    deleted = cleanup_old_backups()
    return f'{deleted} sauvegardes supprimées'
