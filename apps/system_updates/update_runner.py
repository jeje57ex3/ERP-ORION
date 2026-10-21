import logging
import os
import shlex
import sys
from pathlib import Path
from time import monotonic, time

from django.conf import settings
from django.utils import timezone

from apps.core.maintenance import (
    annoncer,
    clore_annonces,
    disable_maintenance_mode,
    enable_maintenance_mode,
)
from apps.system_updates.git_service import build_pull_command, get_current_commit, run_command
from apps.system_updates.health_checks import run_post_update_health_checks
from apps.system_updates.models import SystemUpdateRun, SystemUpdateStepLog
from apps.system_updates.selectors import get_update_settings

logger = logging.getLogger(__name__)


class UpdateAlreadyRunning(Exception):
    pass


def _get_lock_file():
    return Path(getattr(settings, 'ORION_UPDATE_LOCK_FILE', '/tmp/orion_update.lock'))


# Au-delà de cette durée, un verrou est considéré comme abandonné. Large à
# dessein : une mise à jour complète (pip, migrations, builds React) peut
# durer longtemps, mais jamais plusieurs heures.
LOCK_MAX_AGE_SECONDS = 3 * 3600


def _process_alive(pid: int) -> bool:
    # Uniquement sur POSIX : sous Windows, os.kill() TERMINE le processus
    # quel que soit le signal demandé, y compris 0.
    if os.name != 'posix':
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True  # existe mais hors de portée (permissions)
    return True


def _lock_stale_reason(lock_file: Path):
    """Pourquoi ce verrou est abandonné, ou None s'il est légitime.

    Le verrou n'avait ni âge ni PID : un processus tué en cours de route
    (agent invité qui tombe, « qm guest exec » interrompu, VM redémarrée)
    laissait un verrou DÉFINITIF, et plus aucune mise à jour n'était possible
    sans supprimer à la main un fichier dont l'emplacement n'était documenté
    nulle part. Constaté sur l'appliance Proxmox.
    """
    try:
        age = time() - lock_file.stat().st_mtime
    except OSError:
        return 'verrou illisible'

    pid = None
    try:
        for ligne in lock_file.read_text(encoding='utf-8').splitlines():
            if ligne.startswith('pid='):
                pid = int(ligne[4:].strip())
                break
    except (OSError, ValueError):
        pass

    if pid is not None and not _process_alive(pid):
        return f'processus {pid} absent'
    if age > LOCK_MAX_AGE_SECONDS:
        return f'verrou vieux de {int(age // 3600)} h'
    return None


def _create_update_lock():
    lock_file = _get_lock_file()
    if lock_file.exists():
        raison = _lock_stale_reason(lock_file)
        if raison is None:
            age = int(time() - lock_file.stat().st_mtime)
            raise UpdateAlreadyRunning(
                f'Une mise à jour est déjà en cours (démarrée il y a {age} s). '
                f'Si ce n\'est pas le cas, supprimez {lock_file}.'
            )
        logger.warning('Verrou de mise à jour abandonné repris (%s) : %s', raison, lock_file)
        _remove_update_lock()

    lock_file.parent.mkdir(parents=True, exist_ok=True)
    lock_file.write_text(
        f'created={timezone.now().isoformat()}\npid={os.getpid()}\n',
        encoding='utf-8',
    )


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

    # Ces lignes etaient hors du try/finally : un echec ici (commit Git
    # illisible, base indisponible) laissait le verrou en place et bloquait
    # toutes les mises a jour suivantes.
    try:
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
    except Exception:
        _remove_update_lock()
        raise

    try:
        if update_settings.maintenance_mode_during_update:
            enable_maintenance_mode()
            # Dire CE QUI se passe : la page de maintenance affichera
            # « Mise a jour en cours » et une heure de retour, au lieu d'un
            # « maintenance programmee » qui n'apprend rien.
            annoncer('mise_a_jour', duree_minutes=15)
            update_run.maintenance_enabled = True
            update_run.save(update_fields=['maintenance_enabled'])
            log_step(update_run, 'maintenance_on', 'Activation maintenance', 'success',
                     'Mode maintenance activé.')

        if update_settings.require_backup_before_update:
            backup_cmd = getattr(settings, 'ORION_UPDATE_BACKUP_COMMAND', '')
            if not backup_cmd:
                # Repli sur la sauvegarde intégrée au lieu d'échouer :
                # require_backup_before_update vaut True côté modèle et
                # ORION_UPDATE_BACKUP_COMMAND vaut '' côté settings, et le .env
                # généré par l'appliance n'en définit aucun — exiger une
                # commande externe rendait donc TOUTE mise à jour impossible
                # par défaut, avec un message qui n'indiquait pas quoi
                # configurer. backup_all est déjà la commande employée par le
                # backup.sh de l'appliance et par le cron quotidien.
                backup_cmd = f'{shlex.quote(sys.executable)} manage.py backup_all'
            run_shell_step(update_run, 'backup', 'Sauvegarde avant mise à jour',
                           backup_cmd, cwd=backend_path, timeout=3600)

        pull_command, pull_display = build_pull_command(remote, branch)
        run_shell_step(update_run, 'git_pull', 'Récupération du code',
                       pull_command, cwd=project_root, timeout=1200, log_command=pull_display)

        python_bin = shlex.quote(sys.executable)

        requirements_path = Path(backend_path) / 'requirements.txt'
        if requirements_path.exists():
            run_shell_step(update_run, 'pip_install', 'Installation des dépendances Python',
                           f'{python_bin} -m pip install -r {shlex.quote(str(requirements_path))}',
                           cwd=backend_path, timeout=1200)

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
