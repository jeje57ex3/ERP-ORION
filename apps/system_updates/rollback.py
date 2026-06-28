from django.conf import settings
from django.utils import timezone

from apps.core.maintenance import enable_maintenance_mode, disable_maintenance_mode
from apps.system_updates.git_service import hard_reset_to_commit, run_command
from apps.system_updates.models import SystemRollbackRun


def rollback_update(update_run, started_by=None):
    if not update_run.from_commit:
        raise RuntimeError('Commit de retour introuvable.')

    rollback = SystemRollbackRun.objects.create(
        update_run=update_run,
        rollback_to_commit=update_run.from_commit,
        started_by=started_by,
    )

    backend_path = getattr(settings, 'ORION_BACKEND_PATH', '') or str(settings.BASE_DIR)

    try:
        enable_maintenance_mode()

        result = hard_reset_to_commit(update_run.from_commit)
        if not result['ok']:
            raise RuntimeError(result['stderr'] or result['stdout'])

        run_command('python manage.py migrate', cwd=backend_path, timeout=1800)

        restart_cmd = getattr(settings, 'ORION_UPDATE_RESTART_COMMAND', '')
        if restart_cmd:
            run_command(restart_cmd, cwd=backend_path, timeout=300)

        disable_maintenance_mode()

        rollback.status = 'success'
        rollback.finished_at = timezone.now()
        rollback.result_payload = {'git': result}
        rollback.save()

        update_run.status = 'rolled_back'
        update_run.save(update_fields=['status'])

        return rollback

    except Exception as exc:
        rollback.status = 'failed'
        rollback.error_message = str(exc)
        rollback.finished_at = timezone.now()
        rollback.save()
        try:
            disable_maintenance_mode()
        except Exception:
            pass
        raise
