"""
apps/backups/services.py — Service de sauvegarde Orion ERP
Utilise mysqldump pour les bases de données et zipfile pour les fichiers.
"""
import os
import hashlib
import shutil
import zipfile
import subprocess
import time
from pathlib import Path
from datetime import datetime

from django.conf import settings
from django.utils import timezone

# ── Résolution de mysqldump ───────────────────────────────────────────────────
_MYSQLDUMP_FALLBACK_PATHS = [
    r'C:\xampp\mysql\bin\mysqldump.exe',
    r'C:\xampp\mysql\bin\mysqldump',
    r'C:\wamp64\bin\mysql\mysql8.0\bin\mysqldump.exe',
    r'C:\wamp\bin\mysql\mysql8.0\bin\mysqldump.exe',
    r'C:\laragon\bin\mysql\mysql-8.0\bin\mysqldump.exe',
    r'C:\Program Files\MySQL\MySQL Server 8.4\bin\mysqldump.exe',
    r'C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe',
    r'C:\Program Files\MySQL\MySQL Server 9.0\bin\mysqldump.exe',
]

_MYSQL_FALLBACK_PATHS = [p.replace('mysqldump', 'mysql') for p in _MYSQLDUMP_FALLBACK_PATHS]


def _find_executable(name, fallback_paths):
    """Retourne le chemin vers l'exécutable : PATH d'abord, puis chemins courants."""
    # Priorité 1 : settings override
    setting_key = f'MYSQL_{"DUMP" if "dump" in name else "CLIENT"}_PATH'
    from_settings = getattr(settings, setting_key, None)
    if from_settings and os.path.exists(from_settings):
        return from_settings
    # Priorité 2 : PATH système
    found = shutil.which(name)
    if found:
        return found
    # Priorité 3 : emplacements courants
    for path in fallback_paths:
        if os.path.exists(path):
            return path
    return name  # laisse subprocess échouer avec un message clair


def get_backup_storage_path(company=None, scope='database') -> Path:
    base = Path(settings.BASE_DIR) / 'storage' / 'backups'
    if scope == 'core':
        path = base / 'core'
    elif company:
        path = base / 'companies' / f'company_{company.pk}' / scope
    else:
        path = base / 'general' / scope
    path.mkdir(parents=True, exist_ok=True)
    return path


def calculate_checksum(file_path: str) -> str:
    sha256 = hashlib.sha256()
    try:
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    except Exception:
        return ''


def _get_db_config():
    db = settings.DATABASES['default']
    return {
        'host': db.get('HOST', '127.0.0.1'),
        'port': db.get('PORT', '3306'),
        'user': db.get('USER', 'root'),
        'password': db.get('PASSWORD', ''),
        'name': db.get('NAME', 'orion_core'),
    }


def _run_mysqldump(db_name: str, output_path: str) -> tuple[bool, str]:
    cfg = _get_db_config()
    mysqldump = _find_executable('mysqldump', _MYSQLDUMP_FALLBACK_PATHS)

    cmd = [mysqldump, f'-h{cfg["host"]}', f'-P{cfg["port"]}', f'-u{cfg["user"]}']
    if cfg['password']:
        cmd.append(f'-p{cfg["password"]}')
    cmd += ['--single-transaction', '--routines', '--triggers', db_name]

    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, timeout=300)
        if result.returncode != 0:
            err = result.stderr.decode('utf-8', errors='replace')
            return False, err
        return True, ''
    except FileNotFoundError:
        return False, f'mysqldump introuvable ({mysqldump}). Vérifiez l\'installation MySQL/XAMPP.'
    except subprocess.TimeoutExpired:
        return False, 'Timeout lors de la sauvegarde (5 minutes dépassées).'
    except Exception as e:
        return False, str(e)


def create_database_backup(company=None, scope='company_database', created_by=None):
    from apps.backups.models import BackupJob
    from django.conf import settings as django_settings

    db_cfg = _get_db_config()
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')

    if scope == 'core_database':
        db_name = db_cfg['name']
        label = 'core'
        path = get_backup_storage_path(scope='core')
    elif company:
        db_name = getattr(company, 'database_name', None) or db_cfg['name']
        label = company.slug
        path = get_backup_storage_path(company=company, scope='database')
    else:
        db_name = db_cfg['name']
        label = 'default'
        path = get_backup_storage_path(scope='database')

    filename = f'{label}_{ts}.sql'
    file_path = str(path / filename)
    job_name = f'DB {label} — {ts}'

    job = BackupJob.objects.create(
        company=company,
        name=job_name,
        backup_type='manual',
        scope=scope,
        status='running',
        started_at=timezone.now(),
        created_by=created_by,
    )

    t0 = time.time()
    try:
        success, err = _run_mysqldump(db_name, file_path)
        if success and os.path.exists(file_path):
            size = os.path.getsize(file_path)
            checksum = calculate_checksum(file_path)
            job.status = 'success'
            job.file_path = file_path
            job.file_size = size
            job.checksum = checksum
        else:
            job.status = 'failed'
            job.error_message = err
    except Exception as e:
        job.status = 'failed'
        job.error_message = str(e)
    finally:
        job.finished_at = timezone.now()
        job.duration_seconds = time.time() - t0
        job.save()

    return job


def create_media_backup(company=None, created_by=None):
    from apps.backups.models import BackupJob

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    label = company.slug if company else 'global'
    path = get_backup_storage_path(company=company, scope='media')
    filename = f'media_{label}_{ts}.zip'
    file_path = str(path / filename)

    job = BackupJob.objects.create(
        company=company,
        name=f'Médias {label} — {ts}',
        backup_type='manual',
        scope='media_files',
        status='running',
        started_at=timezone.now(),
        created_by=created_by,
    )

    t0 = time.time()
    try:
        media_root = Path(settings.MEDIA_ROOT)
        if company and media_root.exists():
            with zipfile.ZipFile(file_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for f in media_root.rglob('*'):
                    if f.is_file():
                        zf.write(f, f.relative_to(media_root.parent))
        size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        job.status = 'success'
        job.file_path = file_path
        job.file_size = size
        job.checksum = calculate_checksum(file_path)
    except Exception as e:
        job.status = 'failed'
        job.error_message = str(e)
    finally:
        job.finished_at = timezone.now()
        job.duration_seconds = time.time() - t0
        job.save()

    return job


def create_full_backup(company=None, created_by=None):
    """Sauvegarde complète : base + médias."""
    db_job = create_database_backup(
        company=company,
        scope='company_database' if company else 'core_database',
        created_by=created_by,
    )
    media_job = create_media_backup(company=company, created_by=created_by)
    return db_job, media_job


def verify_backup_integrity(backup) -> tuple[bool, str]:
    """Vérifie que le fichier existe et que le checksum correspond."""
    if not backup.file_path or not os.path.exists(backup.file_path):
        return False, 'Fichier introuvable'
    if backup.checksum:
        current = calculate_checksum(backup.file_path)
        if current != backup.checksum:
            return False, f'Checksum incorrect (attendu: {backup.checksum[:8]}…, actuel: {current[:8]}…)'
    return True, 'OK'


def restore_backup(backup, restored_by=None):
    """Restaure une sauvegarde de base de données."""
    from apps.backups.models import BackupRestoreLog

    pre_restore = create_database_backup(
        company=backup.company,
        scope=backup.scope,
        created_by=restored_by,
    )
    pre_restore.backup_type = 'pre_restore'
    pre_restore.name = f'PRE-RESTORE avant #{backup.pk}'
    pre_restore.save()

    log = BackupRestoreLog.objects.create(
        backup=backup,
        company=backup.company,
        status='running',
        restored_by=restored_by,
    )

    try:
        if not backup.file_path or not os.path.exists(backup.file_path):
            raise FileNotFoundError(f'Fichier de sauvegarde introuvable : {backup.file_path}')

        cfg = _get_db_config()
        db_name = cfg['name']
        if backup.company and getattr(backup.company, 'database_name', None):
            db_name = backup.company.database_name

        mysql = _find_executable('mysql', _MYSQL_FALLBACK_PATHS)
        cmd = [mysql, f'-h{cfg["host"]}', f'-u{cfg["user"]}']
        if cfg['password']:
            cmd.append(f'-p{cfg["password"]}')
        cmd.append(db_name)

        with open(backup.file_path, 'r', encoding='utf-8') as f:
            result = subprocess.run(cmd, stdin=f, stderr=subprocess.PIPE, timeout=300)

        if result.returncode != 0:
            raise RuntimeError(result.stderr.decode('utf-8', errors='replace'))

        log.status = 'success'
    except Exception as e:
        log.status = 'failed'
        log.error_message = str(e)
    finally:
        log.finished_at = timezone.now()
        log.save()

    return log


def create_portable_backup(created_by=None):
    """
    Sauvegarde portable : base de données centrale + médias dans une seule
    archive .zip (database.sql + media/) — pensée pour être téléchargée et
    importée sur une AUTRE instance Orion ERP, contrairement aux sauvegardes
    classiques (restaurables seulement là où elles ont été créées, un
    BackupJob local pointe vers un fichier sur le même disque).
    """
    from apps.backups.models import BackupJob

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    path = get_backup_storage_path(scope='portable')
    file_path = str(path / f'orion_export_{ts}.zip')
    tmp_sql = str(path / f'.tmp_db_{ts}.sql')

    job = BackupJob.objects.create(
        name=f'Export portable — {ts}',
        backup_type='manual',
        scope='portable_export',
        status='running',
        started_at=timezone.now(),
        created_by=created_by,
    )

    t0 = time.time()
    try:
        db_cfg = _get_db_config()
        success, err = _run_mysqldump(db_cfg['name'], tmp_sql)
        if not success:
            raise RuntimeError(err)

        media_root = Path(settings.MEDIA_ROOT)
        with zipfile.ZipFile(file_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.write(tmp_sql, 'database.sql')
            if media_root.exists():
                for f in media_root.rglob('*'):
                    if f.is_file():
                        zf.write(f, str(Path('media') / f.relative_to(media_root)))

        job.status = 'success'
        job.file_path = file_path
        job.file_size = os.path.getsize(file_path)
        job.checksum = calculate_checksum(file_path)
    except Exception as e:
        job.status = 'failed'
        job.error_message = str(e)
    finally:
        if os.path.exists(tmp_sql):
            os.remove(tmp_sql)
        job.finished_at = timezone.now()
        job.duration_seconds = time.time() - t0
        job.save()

    return job


def import_portable_backup(uploaded_file, created_by=None):
    """
    Importe une sauvegarde portable (créée par create_portable_backup, sur
    cette instance ou une autre) : REMPLACE la base de données centrale et
    les médias par le contenu de l'archive. Crée automatiquement une
    sauvegarde de sécurité de l'état actuel juste avant, restaurable via
    restore_backup en cas de problème.
    """
    from apps.backups.models import BackupJob, BackupRestoreLog

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    path = get_backup_storage_path(scope='portable')
    file_path = str(path / f'import_{ts}_{uploaded_file.name}')

    with open(file_path, 'wb') as f:
        for chunk in uploaded_file.chunks():
            f.write(chunk)

    # IMPORTANT : database.sql est un dump COMPLET de la base, y compris les
    # tables backups_backupjob/backups_backuprestorelog elles-mêmes. Toute
    # ligne de suivi créée AVANT l'import mysql serait donc écrasée par
    # l'import (remplacée par le contenu — antérieur — du dump importé) et
    # disparaîtrait silencieusement. On extrait/valide/importe D'ABORD, et on
    # ne crée les lignes de suivi (job, log) QU'APRÈS l'import, pour qu'elles
    # persistent réellement dans l'état final de la base.
    #
    # La sauvegarde de sécurité pré-import, elle, doit être prise AVANT
    # (avant que les données actuelles ne soient remplacées) — son fichier
    # .zip reste donc la protection réelle même si sa propre ligne BackupJob
    # peut, elle aussi, être écrasée par l'import.
    pre_import = create_portable_backup(created_by=created_by)
    pre_import.backup_type = 'pre_restore'
    pre_import.name = f'PRE-IMPORT avant import de {uploaded_file.name}'
    pre_import.save()

    extract_dir = path / f'.extract_{ts}'
    error_message = ''
    try:
        if not zipfile.is_zipfile(file_path):
            raise ValueError('Le fichier fourni n\'est pas une archive .zip valide.')

        with zipfile.ZipFile(file_path) as zf:
            if 'database.sql' not in zf.namelist():
                raise ValueError(
                    'Archive invalide : database.sql introuvable '
                    '(ce fichier a-t-il bien été exporté depuis Orion ERP ?).'
                )
            extract_dir.mkdir(parents=True, exist_ok=True)
            zf.extractall(extract_dir)

        db_cfg = _get_db_config()
        mysql  = _find_executable('mysql', _MYSQL_FALLBACK_PATHS)
        cmd = [mysql, f'-h{db_cfg["host"]}', f'-u{db_cfg["user"]}']
        if db_cfg['password']:
            cmd.append(f'-p{db_cfg["password"]}')
        cmd.append(db_cfg['name'])

        with open(extract_dir / 'database.sql', 'r', encoding='utf-8') as f:
            result = subprocess.run(cmd, stdin=f, stderr=subprocess.PIPE, timeout=1800)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.decode('utf-8', errors='replace'))

        media_src = extract_dir / 'media'
        if media_src.exists():
            media_root = Path(settings.MEDIA_ROOT)
            media_root.mkdir(parents=True, exist_ok=True)
            for item in media_src.rglob('*'):
                if item.is_file():
                    dest = media_root / item.relative_to(media_src)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, dest)

        success = True
    except Exception as e:
        success = False
        error_message = str(e)
    finally:
        shutil.rmtree(extract_dir, ignore_errors=True)

    # Lignes de suivi créées maintenant seulement (voir note ci-dessus) — la
    # base est soit celle importée (succès), soit inchangée (échec avant tout
    # mysql import réussi), dans les deux cas ces INSERT persistent bien.
    job = BackupJob.objects.create(
        name=f'Import — {uploaded_file.name}',
        backup_type='imported',
        scope='portable_export',
        status='success' if success else 'failed',
        file_path=file_path,
        file_size=os.path.getsize(file_path) if os.path.exists(file_path) else None,
        checksum=calculate_checksum(file_path) if os.path.exists(file_path) else '',
        error_message=error_message,
        started_at=timezone.now(),
        finished_at=timezone.now(),
        created_by=created_by,
    )
    log = BackupRestoreLog.objects.create(
        backup=job,
        status='success' if success else 'failed',
        error_message=error_message,
        restored_by=created_by,
        finished_at=timezone.now(),
    )

    return log


def cleanup_old_backups():
    """Supprime les anciennes sauvegardes selon la rétention."""
    from apps.backups.models import BackupJob, BackupSchedule
    from datetime import timedelta

    deleted = 0
    for schedule in BackupSchedule.objects.filter(is_active=True, retention_days__gt=0):
        cutoff = timezone.now() - timedelta(days=schedule.retention_days)
        old_jobs = BackupJob.objects.filter(
            company=schedule.company,
            scope=schedule.scope,
            status='success',
            created_at__lt=cutoff,
        )
        for job in old_jobs:
            if job.file_path and os.path.exists(job.file_path):
                try:
                    os.remove(job.file_path)
                except OSError:
                    pass
            job.delete()
            deleted += 1
    return deleted


def get_backup_stats():
    """Retourne les statistiques globales de sauvegarde."""
    from apps.backups.models import BackupJob
    from django.db.models import Sum, Count

    qs = BackupJob.objects.all()
    return {
        'total':        qs.count(),
        'success':      qs.filter(status='success').count(),
        'failed':       qs.filter(status='failed').count(),
        'running':      qs.filter(status='running').count(),
        'total_size':   qs.filter(status='success').aggregate(s=Sum('file_size'))['s'] or 0,
        'last_success': qs.filter(status='success').order_by('-finished_at').first(),
    }
