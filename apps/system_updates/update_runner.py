import shlex
import sys
from pathlib import Path
from time import monotonic

from django.conf import settings
from django.utils import timezone

from apps.core.maintenance import enable_maintenance_mode, disable_maintenance_mode
from apps.system_updates.git_service import build_pull_command, get_current_commit, run_command
from apps.system_updates.health_checks import run_post_update_health_checks
from apps.system_updates.models import SystemUpdateRun, SystemUpdateStepLog
from apps.system_updates.selectors import get_update_settings


class UpdateAlreadyRunning(Exception):
    pass


def _get_lock_file():
    return Path(getattr(settings, 'ORION_UPDATE_LOCK_FILE', '/tmp/orion_update.lock'))


def _create_update_lock():
    lock_file = _get_lock_file()
    if lock_file.exists():
        raise UpdateAlreadyRunning('Une mise à jour est déjà en cours.')
    lock_file.write_text(str(timezone.now()), encoding='utf-8')


def _remove_update_lock():
    lock_file = _get_lock_file()
    if lock_file.exists():
        lock_file.unlink()


def log_step(update_run, step_code, step_name, level='info', message='',
             command='', output='', error_output='', started_time=None):
    duration = None
    if started_time is not None:
        duration = round(monotonic() - started_time, 2)
    return SystemUpdateStepLog.objects.create(
        update_run=update_run,
        step_code=step_code,
        step_name=step_name,
        level=level,
        message=message,
        command=command,
        output=output,
        error_output=error_output,
        finished_at=timezone.now(),
        duration_seconds=duration,
    )


def run_shell_step(update_run, step_code, step_name, command, cwd=None, timeout=1200, log_command=None):
    started = monotonic()
    result = run_command(command, cwd=cwd, timeout=timeout)
    log_step(
        update_run=update_run,
        step_code=step_code,
        step_name=step_name,
        level='success' if result['ok'] else 'error',
        command=log_command if log_command is not None else command,
        output=result['stdout'],
        error_output=result['stderr'],
        started_time=started,
    )
    if not result['ok']:
        raise RuntimeError(result['stderr'] or result['stdout'])
    return result


def run_system_update(started_by=None):
    update_settings = get_update_settings()

    if not update_settings.update_enabled:
        raise RuntimeError('Les mises à jour sont désactivées.')

    _create_update_lock()

    from_commit = get_current_commit()
    backend_path = getattr(settings, 'ORION_BACKEND_PATH', '') or str(settings.BASE_DIR)
    project_root = getattr(settings, 'ORION_PROJECT_ROOT', '') or str(settings.BASE_DIR)
    remote = getattr(settings, 'ORION_GIT_REMOTE', 'origin')
    branch = getattr(settings, 'ORION_GIT_BRANCH', 'main')

    update_run = SystemUpdateRun.objects.create(
        status='running',
        from_commit=from_commit,
        started_by=started_by,
    )

    try:
        if update_settings.maintenance_mode_during_update:
            enable_maintenance_mode()
            update_run.maintenance_enabled = True
            update_run.save(update_fields=['maintenance_enabled'])
            log_step(update_run, 'maintenance_on', 'Activation maintenance', 'success',
                     'Mode maintenance activé.')

        if update_settings.require_backup_before_update:
            backup_cmd = getattr(settings, 'ORION_UPDATE_BACKUP_COMMAND', '')
            if not backup_cmd:
                raise RuntimeError('Commande de sauvegarde non configurée.')
            run_shell_step(update_run, 'backup', 'Sauvegarde avant mise à jour',
                           backup_cmd, cwd=backend_path, timeout=3600)

        pull_command, pull_display = build_pull_command(remote, branch)
        run_shell_step(update_run, 'git_pull', 'Récupération du code',
                       pull_command, cwd=project_root, timeout=1200, log_command=pull_display)

        python_bin = shlex.quote(sys.executable)

        if update_settings.run_migrations:
            run_shell_step(update_run, 'migrations', 'Migrations Django',
                           f'{python_bin} manage.py migrate', cwd=backend_path, timeout=1800)

        if update_settings.collect_static:
            run_shell_step(update_run, 'collectstatic', 'Collect static',
                           f'{python_bin} manage.py collectstatic --noinput',
                           cwd=backend_path, timeout=1200)

        siecle_path = getattr(settings, 'ORION_FRONTEND_SIECLE_PATH', '')
        lunea_path = getattr(settings, 'ORION_FRONTEND_LUNEA_PATH', '')
        build_enabled = getattr(settings, 'ORION_UPDATE_FRONTEND_BUILD_ENABLED', True)
        build_cmd = getattr(settings, 'ORION_UPDATE_FRONTEND_BUILD_COMMAND', 'npm run build')

        if update_settings.update_frontend_siecle_enabled and build_enabled and siecle_path:
            run_shell_step(update_run, 'build_siecle', 'Build frontend SIÈCLE',
                           build_cmd, cwd=siecle_path, timeout=1800)

        if update_settings.update_frontend_lunea_enabled and build_enabled and lunea_path:
            run_shell_step(update_run, 'build_lunea', 'Build frontend LUNEA',
                           build_cmd, cwd=lunea_path, timeout=1800)

        if update_settings.restart_services:
            restart_cmd = getattr(settings, 'ORION_UPDATE_RESTART_COMMAND', '')
            celery_cmd = getattr(settings, 'ORION_UPDATE_CELERY_RESTART_COMMAND', '')
            beat_cmd = getattr(settings, 'ORION_UPDATE_CELERY_BEAT_RESTART_COMMAND', '')

            if restart_cmd:
                run_shell_step(update_run, 'restart_orion', 'Redémarrage Orion',
                               restart_cmd, cwd=backend_path, timeout=300)
            if celery_cmd:
                run_shell_step(update_run, 'restart_celery', 'Redémarrage Celery',
                               celery_cmd, cwd=backend_path, timeout=300)
            if beat_cmd:
                run_shell_step(update_run, 'restart_celery_beat', 'Redémarrage Celery Beat',
                               beat_cmd, cwd=backend_path, timeout=300)

        if update_settings.require_health_check_before_update:
            health = run_post_update_health_checks()
            log_step(update_run, 'health_check', 'Vérification santé',
                     'success' if health['ok'] else 'error', message=str(health))
            if not health['ok']:
                raise RuntimeError('Health check post-update échoué.')

        if update_settings.maintenance_mode_during_update:
            disable_maintenance_mode()
            log_step(update_run, 'maintenance_off', 'Désactivation maintenance', 'success',
                     'Mode maintenance désactivé.')

        update_run.status = 'success'
        update_run.to_commit = get_current_commit()
        update_run.finished_at = timezone.now()
        update_run.save()

        return update_run

    except Exception as exc:
        update_run.status = 'failed'
        update_run.error_message = str(exc)
        update_run.finished_at = timezone.now()
        update_run.save()
        log_step(update_run, 'failed', 'Échec mise à jour', 'error', message=str(exc))
        if update_settings.maintenance_mode_during_update:
            try:
                disable_maintenance_mode()
            except Exception:
                pass
        raise

    finally:
        _remove_update_lock()
