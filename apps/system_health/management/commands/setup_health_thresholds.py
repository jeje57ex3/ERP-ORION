"""
manage.py setup_health_thresholds
Initialise les seuils d'alerte par défaut pour tous les capteurs.
Idempotent : ne crée que les seuils manquants.
"""
from django.core.management.base import BaseCommand
from apps.system_health.models import AlertThreshold


# (sensor_type, comparison, warning, critical)
DEFAULT_THRESHOLDS = [
    # Serveur
    ('cpu_usage',          'gt', 70,    90),
    ('memory_usage',       'gt', 75,    90),
    ('disk_usage',         'gt', 80,    95),
    ('disk_free_gb',       'lt', 5,     2),
    ('load_average',       'gt', 2.0,   4.0),
    ('open_files',         'gt', 1000,  2000),
    # Application
    ('avg_response_ms',    'gt', 800,   2000),
    ('max_response_ms',    'gt', 3000,  8000),
    ('error_rate_pct',     'gt', 1,     5),
    ('slow_requests_1h',   'gt', 20,    100),
    ('requests_per_min',   'gt', 500,   1000),
    # Base de données
    ('db_connections',     'gt', 50,    90),
    ('db_pending_migrations', 'gt', 0,  1),
    ('db_size_gb',         'gt', 10,    20),
    ('db_slow_queries_1h', 'gt', 10,    50),
    # Sauvegardes
    ('backup_age_hours',   'gt', 26,    50),
    ('backup_test_age_days','gt', 30,   60),
    # Sécurité
    ('failed_logins_1h',   'gt', 10,    30),
    ('locked_accounts',    'gt', 2,     5),
    ('open_errors',        'gt', 10,    50),
    # File Celery
    ('queue_failed_1h',    'gt', 5,     20),
    ('queue_pending',      'gt', 100,   500),
    ('queue_workers',      'lt', 1,     None),
]


class Command(BaseCommand):
    help = 'Initialise les seuils d\'alerte système par défaut (idempotent)'

    def handle(self, *args, **options):
        created = 0
        skipped = 0
        for sensor_type, comparison, warning, critical in DEFAULT_THRESHOLDS:
            _, was_created = AlertThreshold.objects.get_or_create(
                sensor_type=sensor_type,
                defaults={
                    'comparison':          comparison,
                    'warning_threshold':   warning,
                    'critical_threshold':  critical,
                    'enabled':             True,
                    'escalation_after_min': 30,
                }
            )
            if was_created:
                created += 1
            else:
                skipped += 1

        self.stdout.write(self.style.SUCCESS(
            f'{created} seuil(s) créé(s), {skipped} déjà présent(s).'
        ))
