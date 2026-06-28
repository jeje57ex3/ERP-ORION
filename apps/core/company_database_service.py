"""
apps/core/company_database_service.py
Service de gestion des bases de données dédiées par entreprise.
Orion ERP — Architecture multi-tenant avec base séparée par entreprise.
"""
import logging
import os
import subprocess
from datetime import datetime, timezone as dt_timezone
from django.conf import settings
from django.db import connections, connection
from django.utils import timezone

logger = logging.getLogger(__name__)


# ─── Nommage ──────────────────────────────────────────────────────────────────

def generate_company_database_name(company) -> str:
    """Génère un nom de base de données unique et sûr pour l'entreprise."""
    slug = company.slug.replace('-', '_').lower()[:30]
    return f'orion_company_{company.pk}_{slug}'


def get_company_database_alias(company) -> str:
    """Retourne l'alias Django pour la base de l'entreprise."""
    return f'company_{company.pk}'


# ─── Enregistrement ───────────────────────────────────────────────────────────

def register_company_database(company) -> dict:
    """
    Enregistre dynamiquement la base de l'entreprise dans settings.DATABASES.
    Appelé au démarrage et lors de la création d'entreprise.
    """
    alias = get_company_database_alias(company)
    db_name = company.database_name or generate_company_database_name(company)

    db_config = {
        'ENGINE': settings.DATABASES['default']['ENGINE'],
        'NAME': db_name,
        'USER': company.database_user or settings.DATABASES['default'].get('USER', 'root'),
        'PASSWORD': company.database_password or settings.DATABASES['default'].get('PASSWORD', ''),
        'HOST': company.database_host or settings.DATABASES['default'].get('HOST', '127.0.0.1'),
        'PORT': company.database_port or settings.DATABASES['default'].get('PORT', 3306),
        'OPTIONS': {
            'charset': 'utf8mb4',
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
        'TIME_ZONE': None,
        'CONN_MAX_AGE': 60,
    }

    settings.DATABASES[alias] = db_config
    return db_config


def ensure_company_database_exists(company) -> bool:
    """
    S'assure que la base est enregistrée dans settings.DATABASES.
    Crée l'entrée si elle n'existe pas.
    """
    alias = get_company_database_alias(company)
    if alias not in settings.DATABASES:
        register_company_database(company)
    return True


# ─── Connexion ────────────────────────────────────────────────────────────────

def test_company_database_connection(company) -> tuple[bool, str]:
    """
    Teste la connexion à la base de l'entreprise.
    Retourne (succès, message).
    """
    ensure_company_database_exists(company)
    alias = get_company_database_alias(company)

    try:
        conn = connections[alias]
        conn.ensure_connection()
        version = conn.mysql_version if hasattr(conn, 'mysql_version') else 'OK'
        conn.close()
        return True, f'Connexion réussie (base : {company.database_name})'
    except Exception as e:
        return False, f'Erreur de connexion : {e}'


# ─── Création ─────────────────────────────────────────────────────────────────

def create_company_database(company) -> tuple[bool, str]:
    """
    Crée physiquement la base MySQL de l'entreprise.
    """
    if not company.database_name:
        company.database_name = generate_company_database_name(company)
        company.save(update_fields=['database_name'])

    db_name = company.database_name
    host = company.database_host or settings.DATABASES['default'].get('HOST', '127.0.0.1')
    port = company.database_port or int(settings.DATABASES['default'].get('PORT', 3306))
    user = company.database_user or settings.DATABASES['default'].get('USER', 'root')
    password = company.database_password or settings.DATABASES['default'].get('PASSWORD', '')

    try:
        import MySQLdb
        if password:
            conn = MySQLdb.connect(host=host, port=port, user=user, password=password)
        else:
            conn = MySQLdb.connect(host=host, port=port, user=user)

        cursor = conn.cursor()
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
            f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
        )
        conn.commit()
        cursor.close()
        conn.close()

        # Enregistrer la base dans settings
        register_company_database(company)

        # Mettre à jour le modèle
        company.database_created = True
        company.database_created_at = timezone.now()
        company.save(update_fields=['database_created', 'database_created_at'])

        # Créer / mettre à jour CompanyDatabase
        _update_company_database_record(company, 'created')

        logger.info(f'Base créée : {db_name} pour {company.name}')
        return True, f'Base de données "{db_name}" créée avec succès.'

    except ImportError:
        # Fallback via connexion Django sur la base default (CREATE DATABASE)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                    f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
                )
            register_company_database(company)
            company.database_created = True
            company.database_created_at = timezone.now()
            company.save(update_fields=['database_created', 'database_created_at'])
            _update_company_database_record(company, 'created')
            return True, f'Base de données "{db_name}" créée avec succès.'
        except Exception as e2:
            logger.error(f'Erreur création base {db_name}: {e2}')
            _update_company_database_record(company, 'error', str(e2))
            return False, f'Erreur lors de la création : {e2}'

    except Exception as e:
        logger.error(f'Erreur création base {db_name}: {e}')
        _update_company_database_record(company, 'error', str(e))
        return False, f'Erreur lors de la création : {e}'


# ─── Migrations ───────────────────────────────────────────────────────────────

def run_company_migrations(company) -> tuple[bool, str]:
    """
    Lance les migrations Django sur la base de l'entreprise.
    """
    ensure_company_database_exists(company)
    alias = get_company_database_alias(company)

    try:
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        call_command('migrate', '--database', alias, '--run-syncdb', stdout=out, stderr=out)
        result = out.getvalue()

        _update_company_database_record(company, 'active')
        company_db = _get_or_create_company_db_record(company)
        company_db.last_migration_at = timezone.now()
        company_db.status = 'active'
        company_db.is_active = True
        company_db.save(update_fields=['last_migration_at', 'status', 'is_active'])

        logger.info(f'Migrations OK pour {company.name} (base: {alias})')
        return True, f'Migrations appliquées :\n{result}'

    except Exception as e:
        logger.error(f'Erreur migrations {alias}: {e}')
        _update_company_database_record(company, 'error', str(e))
        return False, f'Erreur lors des migrations : {e}'


# ─── Données initiales ────────────────────────────────────────────────────────

def seed_company_initial_data(company) -> None:
    """Crée les données initiales dans la base de l'entreprise."""
    alias = get_company_database_alias(company)
    ensure_company_database_exists(company)

    try:
        from apps.core.db_router import set_company_db
        set_company_db(alias)
        # Les seeds spécifiques par module peuvent être ajoutées ici
        logger.info(f'Données initiales créées pour {company.name}')
    except Exception as e:
        logger.warning(f'Données initiales partielles pour {company.name}: {e}')
    finally:
        from apps.core.db_router import clear_company_db
        clear_company_db()


# ─── Archivage ────────────────────────────────────────────────────────────────

def archive_company_database(company) -> tuple[bool, str]:
    """Archive la base de l'entreprise (la marque inactive sans la supprimer)."""
    try:
        company.database_archived = True
        company.database_archived_at = timezone.now()
        company.status = 'archived'
        company.is_active = False
        company.save(update_fields=['database_archived', 'database_archived_at', 'status', 'is_active'])
        _update_company_database_record(company, 'archived')
        return True, f'Base de "{company.name}" archivée.'
    except Exception as e:
        return False, f'Erreur archivage : {e}'


# ─── Sauvegarde ───────────────────────────────────────────────────────────────

def backup_company_database(company) -> tuple[bool, str]:
    """
    Sauvegarde la base MySQL via mysqldump.
    Enregistre le fichier dans MEDIA_ROOT/backups/.
    """
    db_name = company.database_name
    if not db_name:
        return False, 'Aucune base configurée pour cette entreprise.'

    backup_dir = os.path.join(settings.MEDIA_ROOT, 'backups', 'databases')
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'{db_name}_{timestamp}.sql'
    filepath = os.path.join(backup_dir, filename)

    host = company.database_host or '127.0.0.1'
    port = str(company.database_port or 3306)
    user = company.database_user or 'root'
    password = company.database_password or ''

    cmd = ['mysqldump', f'-h{host}', f'-P{port}', f'-u{user}']
    if password:
        cmd.append(f'-p{password}')
    cmd += ['--single-transaction', '--quick', db_name]

    try:
        with open(filepath, 'w') as f:
            result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, timeout=300)

        if result.returncode != 0:
            error = result.stderr.decode()
            return False, f'mysqldump a échoué : {error}'

        size_mb = os.path.getsize(filepath) / (1024 * 1024)

        company_db = _get_or_create_company_db_record(company)
        company_db.last_backup_at = timezone.now()
        company_db.save(update_fields=['last_backup_at'])

        return True, f'Sauvegarde créée : {filename} ({size_mb:.1f} Mo)'
    except FileNotFoundError:
        return False, 'mysqldump introuvable. Installez MySQL client tools.'
    except subprocess.TimeoutExpired:
        return False, 'La sauvegarde a pris trop de temps.'
    except Exception as e:
        return False, f'Erreur sauvegarde : {e}'


# ─── Suppression sécurisée ────────────────────────────────────────────────────

DELETION_CONFIRMATION_TEXT = "Je confirme la suppression définitive de la base de données de cette entreprise."


def delete_company_database(company, confirmation_code: str, requesting_user) -> tuple[bool, str]:
    """
    Supprime définitivement la base MySQL de l'entreprise.

    Règles de sécurité :
    - L'utilisateur doit être superadmin ou avoir can_delete_company_database
    - Le texte de confirmation doit correspondre exactement
    - Une sauvegarde est faite avant suppression
    - L'action est tracée dans AuditLog
    """
    # Vérification permission
    if not requesting_user.is_superuser:
        try:
            access = CompanyAccess.objects.get(user=requesting_user, company=company)
            if not access.can_delete_company_database:
                return False, "Permission refusée. Seul un superadmin peut supprimer une base."
        except Exception:
            return False, "Permission refusée."

    # Vérification confirmation
    if confirmation_code.strip() != DELETION_CONFIRMATION_TEXT:
        return False, "Le texte de confirmation ne correspond pas exactement."

    db_name = company.database_name
    if not db_name:
        return False, "Aucune base configurée pour cette entreprise."

    # Sauvegarde préventive
    backup_ok, backup_msg = backup_company_database(company)
    logger.info(f'Sauvegarde avant suppression de {db_name}: {backup_msg}')

    # Marquer en cours de suppression
    company.status = 'deleting'
    company.save(update_fields=['status'])

    # Suppression physique
    host = company.database_host or '127.0.0.1'
    port = company.database_port or 3306
    user = company.database_user or 'root'
    password = company.database_password or ''

    try:
        import MySQLdb
        if password:
            conn = MySQLdb.connect(host=host, port=port, user=user, password=password)
        else:
            conn = MySQLdb.connect(host=host, port=port, user=user)

        cursor = conn.cursor()
        cursor.execute(f"DROP DATABASE IF EXISTS `{db_name}`;")
        conn.commit()
        cursor.close()
        conn.close()

    except ImportError:
        with connection.cursor() as cursor:
            cursor.execute(f"DROP DATABASE IF EXISTS `{db_name}`;")

    except Exception as e:
        company.status = 'active'
        company.save(update_fields=['status'])
        return False, f'Erreur suppression base : {e}'

    # Mettre à jour les enregistrements
    company.database_deleted = True
    company.database_deleted_at = timezone.now()
    company.status = 'deleted'
    company.is_active = False
    company.database_created = False
    company.save(update_fields=['database_deleted', 'database_deleted_at', 'status', 'is_active', 'database_created'])

    try:
        company_db = company.company_database
        company_db.status = 'deleted'
        company_db.is_active = False
        company_db.save(update_fields=['status', 'is_active'])
    except Exception:
        pass

    # Supprimer l'alias de settings.DATABASES
    alias = get_company_database_alias(company)
    settings.DATABASES.pop(alias, None)

    # Audit log
    try:
        from .models import AuditLog
        AuditLog.objects.create(
            user=requesting_user,
            action='delete',
            model_name='CompanyDatabase',
            object_repr=db_name,
            description=f'Suppression définitive de la base {db_name} de l\'entreprise {company.name}',
        )
    except Exception:
        pass

    logger.warning(f'BASE SUPPRIMÉE : {db_name} par {requesting_user} (backup: {backup_ok})')
    return True, f'Base "{db_name}" supprimée définitivement. Sauvegarde : {backup_msg}'


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_or_create_company_db_record(company):
    """Récupère ou crée l'enregistrement CompanyDatabase."""
    from .models import CompanyDatabase
    alias = get_company_database_alias(company)
    db_name = company.database_name or generate_company_database_name(company)
    record, _ = CompanyDatabase.objects.get_or_create(
        company=company,
        defaults={
            'database_alias': alias,
            'database_name': db_name,
            'host': company.database_host or '127.0.0.1',
            'port': company.database_port or 3306,
            'user': company.database_user or 'root',
            'status': 'to_create',
        }
    )
    return record


def _update_company_database_record(company, status: str, error: str = '') -> None:
    """Met à jour le statut du CompanyDatabase."""
    try:
        record = _get_or_create_company_db_record(company)
        record.status = status
        if error:
            record.last_error = error
        record.is_active = status == 'active'
        record.save(update_fields=['status', 'last_error', 'is_active'])
    except Exception as e:
        logger.warning(f'Impossible de mettre à jour CompanyDatabase: {e}')


def load_all_company_databases() -> None:
    """
    Charge toutes les bases actives dans settings.DATABASES au démarrage.
    À appeler dans AppConfig.ready() de core.
    """
    try:
        from .models import Company
        for company in Company.objects.filter(database_created=True, is_active=True):
            if company.database_name:
                register_company_database(company)
    except Exception as e:
        logger.warning(f'Impossible de charger les bases entreprises: {e}')


# Import tardif pour éviter la circularité
try:
    from .models import CompanyAccess
except ImportError:
    CompanyAccess = None
