"""
apps/core/backups.py — Sauvegardes des bases de données Orion

Fonctions :
    backup_core_database()
    backup_company_database(company)
    backup_all_company_databases()
    list_company_backups(company)
    delete_old_backups(days=30)
"""
import os
import logging
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger('orion')

BACKUP_DIR = getattr(settings, 'BACKUP_DIR', Path(settings.BASE_DIR) / 'backups')


def _get_mysqldump_cmd(db_config: dict, output_file: str) -> list:
    """Construit la commande mysqldump."""
    cmd = [
        'mysqldump',
        f"--host={db_config['HOST']}",
        f"--port={db_config.get('PORT', 3306)}",
        f"--user={db_config['USER']}",
        '--single-transaction',
        '--routines',
        '--triggers',
        '--set-gtid-purged=OFF',
        db_config['NAME'],
    ]
    if db_config.get('PASSWORD'):
        cmd.insert(1, f"--password={db_config['PASSWORD']}")
    return cmd


def backup_core_database() -> tuple[bool, str]:
    """Sauvegarde la base centrale (orion_core)."""
    db = settings.DATABASES['default']
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = Path(BACKUP_DIR) / 'core'
    backup_dir.mkdir(parents=True, exist_ok=True)
    output_file = backup_dir / f"orion_core_{timestamp}.sql"

    try:
        cmd = _get_mysqldump_cmd(db, str(output_file))
        with open(output_file, 'w', encoding='utf-8') as f:
            result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, timeout=300)

        if result.returncode != 0:
            error = result.stderr.decode('utf-8', errors='replace')
            logger.error("Échec sauvegarde core: %s", error)
            return False, f"Erreur mysqldump: {error[:200]}"

        size = output_file.stat().st_size
        logger.info("Sauvegarde core réussie: %s (%d octets)", output_file.name, size)
        _log_audit_backup('core', str(output_file), size)
        return True, str(output_file)

    except FileNotFoundError:
        return False, "mysqldump introuvable. Vérifiez que MySQL est installé et dans le PATH."
    except subprocess.TimeoutExpired:
        return False, "Timeout sauvegarde (>5 min)."
    except Exception as e:
        logger.exception("Erreur inattendue sauvegarde core")
        return False, str(e)


def backup_company_database(company) -> tuple[bool, str]:
    """Sauvegarde la base dédiée d'une entreprise."""
    if not company.database_created or not company.database_name:
        return False, f"Entreprise {company.name}: aucune base dédiée créée."

    from apps.core.company_database_service import get_company_database_alias
    alias = get_company_database_alias(company)

    if alias not in settings.DATABASES:
        return False, f"Alias '{alias}' introuvable dans DATABASES."

    db = settings.DATABASES[alias]
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = Path(BACKUP_DIR) / 'companies' / f"company_{company.pk}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(c if c.isalnum() or c == '_' else '_' for c in company.name)
    output_file = backup_dir / f"{safe_name}_{timestamp}.sql"

    try:
        cmd = _get_mysqldump_cmd(db, str(output_file))
        with open(output_file, 'w', encoding='utf-8') as f:
            result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, timeout=600)

        if result.returncode != 0:
            error = result.stderr.decode('utf-8', errors='replace')
            logger.error("Échec sauvegarde entreprise %s: %s", company.name, error)
            return False, f"Erreur mysqldump: {error[:200]}"

        size = output_file.stat().st_size
        logger.info("Sauvegarde entreprise %s réussie: %s (%d octets)", company.name, output_file.name, size)
        _log_audit_backup(company.name, str(output_file), size, company=company)
        return True, str(output_file)

    except FileNotFoundError:
        return False, "mysqldump introuvable."
    except subprocess.TimeoutExpired:
        return False, "Timeout sauvegarde (>10 min)."
    except Exception as e:
        logger.exception("Erreur inattendue sauvegarde entreprise %s", company.name)
        return False, str(e)


def backup_all_company_databases() -> list[dict]:
    """Sauvegarde toutes les bases entreprises actives."""
    from apps.core.models import Company
    results = []
    companies = Company.objects.filter(database_created=True, is_active=True)
    for company in companies:
        ok, msg = backup_company_database(company)
        results.append({'company': company.name, 'ok': ok, 'message': msg})
    return results


def list_company_backups(company) -> list[dict]:
    """Liste les sauvegardes disponibles pour une entreprise."""
    backup_dir = Path(BACKUP_DIR) / 'companies' / f"company_{company.pk}"
    if not backup_dir.exists():
        return []

    backups = []
    for f in sorted(backup_dir.glob('*.sql'), reverse=True):
        stat = f.stat()
        backups.append({
            'filename': f.name,
            'path': str(f),
            'size': stat.st_size,
            'created_at': datetime.fromtimestamp(stat.st_mtime),
        })
    return backups


def delete_old_backups(days: int = 30) -> int:
    """Supprime les sauvegardes plus anciennes que `days` jours."""
    cutoff = datetime.now() - timedelta(days=days)
    deleted = 0
    backup_root = Path(BACKUP_DIR)

    for sql_file in backup_root.rglob('*.sql'):
        if datetime.fromtimestamp(sql_file.stat().st_mtime) < cutoff:
            try:
                sql_file.unlink()
                deleted += 1
                logger.info("Sauvegarde supprimée (>%d j): %s", days, sql_file.name)
            except Exception as e:
                logger.warning("Impossible de supprimer %s: %s", sql_file, e)

    return deleted


def _log_audit_backup(target: str, filepath: str, size: int, company=None):
    """Enregistre la sauvegarde dans l'AuditLog si disponible."""
    try:
        from apps.core.models import AuditLog
        AuditLog.objects.create(
            company=company,
            action='other',
            model_name='Database',
            object_repr=target,
            description=f"Sauvegarde: {Path(filepath).name} ({size} octets)",
        )
    except Exception:
        pass
