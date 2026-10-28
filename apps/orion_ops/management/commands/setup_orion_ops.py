"""
python manage.py setup_orion_ops

Initialise les données de référence pour orion_ops :
  - SLO par défaut (5 objectifs de service)
  - Composants services (cartographie des composants système)
  - Tâches Celery Beat planifiées

Idempotent — peut être lancé plusieurs fois sans risque.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone


COMPONENTS = [
    {
        'slug': 'django-app',
        'name': 'Application Django (Orion ERP)',
        'component_type': 'web_app',
        'criticality': 'critical',
        'host': '127.0.0.1',
        'port': 5172,
        'check_url': '/health/live',
        'version': '4.2.16',
        'metadata': {'python': '3.14'},
    },
    {
        'slug': 'mariadb',
        'name': 'Base de données MariaDB',
        'component_type': 'database',
        'criticality': 'critical',
        'host': '127.0.0.1',
        'port': 3306,
        'version': '10.4.32',
    },
    {
        'slug': 'redis',
        'name': 'Redis (broker + cache)',
        'component_type': 'broker',
        'criticality': 'critical',
        'host': '127.0.0.1',
        'port': 6379,
        'version': '5.0.14',
    },
    {
        'slug': 'celery-worker',
        'name': 'Worker Celery',
        'component_type': 'celery_worker',
        'criticality': 'major',
        'metadata': {'queues': ['default', 'maintenance', 'notifications']},
    },
    {
        'slug': 'celery-beat',
        'name': 'Celery Beat (planificateur)',
        'component_type': 'celery_beat',
        'criticality': 'major',
    },
    {
        'slug': 'cloudflare-tunnel',
        'name': 'Tunnel Cloudflare',
        'component_type': 'tunnel',
        'criticality': 'critical',
        'metadata': {
            'domains': ['orion.elysiums.fr', 'siecle.elysiums.fr', 'lunea.elysiums.fr'],
            'note': 'Ports fixes — ne pas modifier',
        },
    },
    {
        'slug': 'stripe-api',
        'name': 'API Stripe (paiements)',
        'component_type': 'payment',
        'criticality': 'major',
        'metadata': {'provider': 'Stripe'},
    },
    {
        'slug': 'local-storage',
        'name': 'Stockage fichiers local',
        'component_type': 'storage',
        'criticality': 'minor',
        'host': 'D:\\',
    },
]

DEPENDENCIES = [
    ('django-app',    'mariadb',          'required', 'Django ne peut pas démarrer sans MariaDB'),
    ('django-app',    'redis',            'required', 'Sessions et cache requièrent Redis'),
    ('celery-worker', 'redis',            'required', 'Celery utilise Redis comme broker'),
    ('celery-beat',   'redis',            'required', 'Celery Beat publie via Redis'),
    ('celery-beat',   'mariadb',          'required', 'Tâches planifiées stockées en DB'),
    ('django-app',    'cloudflare-tunnel','required', 'Accès externe via tunnel'),
    ('django-app',    'stripe-api',       'optional', 'Paiements e-commerce'),
    ('django-app',    'local-storage',    'optional', 'Médias et sauvegardes'),
]


DEFAULT_ALERT_RULES = [
    {
        'name': 'disque-c-critique',
        'description': 'Disque C: utilisé à plus de 95% — saturation imminente',
        'source': 'sensor', 'metric_key': 'disk_usage', 'operator': 'gte', 'threshold': 95.0,
        'severity': 'critical', 'frequency_min': 30,
        'actions': ['create_alert', 'notify_superusers'],
    },
    {
        'name': 'disque-c-avertissement',
        'description': 'Disque C: utilisé à plus de 85%',
        'source': 'sensor', 'metric_key': 'disk_usage', 'operator': 'gte', 'threshold': 85.0,
        'severity': 'warning', 'frequency_min': 60,
        'actions': ['create_alert'],
    },
    {
        'name': 'memoire-critique',
        'description': 'RAM utilisée à plus de 90% — risque de saturation',
        'source': 'sensor', 'metric_key': 'memory_usage', 'operator': 'gte', 'threshold': 90.0,
        'severity': 'critical', 'frequency_min': 15,
        'actions': ['create_alert', 'notify_superusers'],
    },
    {
        'name': 'cpu-soutenu-eleve',
        'description': 'CPU moyen au-dessus de 85% pendant plusieurs cycles',
        'source': 'sensor', 'metric_key': 'cpu_usage', 'operator': 'gte', 'threshold': 85.0,
        'severity': 'warning', 'frequency_min': 30,
        'actions': ['create_alert'],
    },
    {
        'name': 'sauvegarde-en-retard',
        'description': 'Dernière sauvegarde plus ancienne que 30h',
        'source': 'sensor', 'metric_key': 'backup_age_hours', 'operator': 'gte', 'threshold': 30.0,
        'severity': 'warning', 'frequency_min': 120,
        'actions': ['create_alert', 'create_incident'],
    },
    {
        'name': 'celery-beat-hors-service',
        'description': 'Celery Beat inactif — les tâches planifiées ne s\'exécutent plus',
        'source': 'sensor', 'metric_key': 'celery_beat_ok', 'operator': 'lt', 'threshold': 1.0,
        'severity': 'critical', 'frequency_min': 10,
        'actions': ['create_alert', 'create_incident', 'notify_superusers'],
    },
    {
        'name': 'taux-erreur-http-eleve',
        'description': 'Taux d\'erreurs HTTP dépasse 5%',
        'source': 'sensor', 'metric_key': 'error_rate_pct', 'operator': 'gte', 'threshold': 5.0,
        'severity': 'warning', 'frequency_min': 15,
        'actions': ['create_alert'],
    },
    {
        'name': 'anomalie-qualite-critique',
        'description': 'Au moins une anomalie de qualité critique ouverte',
        'source': 'data_quality', 'metric_key': 'open_critical', 'operator': 'gte', 'threshold': 1.0,
        'severity': 'warning', 'frequency_min': 120,
        'actions': ['create_alert', 'notify_superusers'],
    },
    {
        'name': 'broker-redis-hors-service',
        'description': 'Redis broker inaccessible — Celery ne peut plus traiter de tâches',
        'source': 'sensor', 'metric_key': 'celery_broker_ok', 'operator': 'lt', 'threshold': 1.0,
        'severity': 'emergency', 'frequency_min': 5,
        'actions': ['create_alert', 'create_incident', 'notify_superusers'],
    },
    {
        'name': 'tentatives-connexion-suspectes',
        'description': 'Plus de 20 tentatives de connexion échouées en 1h',
        'source': 'sensor', 'metric_key': 'failed_logins_1h', 'operator': 'gte', 'threshold': 20.0,
        'severity': 'critical', 'frequency_min': 30,
        'actions': ['create_alert', 'notify_superusers'],
    },
]


class Command(BaseCommand):
    help = 'Initialise les données de référence Orion Ops (SLO, composants, dépendances, règles d\'alerte)'

    def add_arguments(self, parser):
        parser.add_argument('--skip-beat', action='store_true',
                            help='Ne pas créer les tâches Celery Beat')

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('Orion Ops — Initialisation'))

        # SLO
        self._setup_slos()

        # Composants
        self._setup_components()

        # Règles d'alerte
        self._setup_alert_rules()

        # Celery Beat
        if not options['skip_beat']:
            self._setup_beat_tasks()

        self.stdout.write(self.style.SUCCESS('Orion Ops initialisé avec succès.'))

    def _setup_slos(self):
        from apps.orion_ops.services.slo_service import setup_default_slos
        result = setup_default_slos()
        self.stdout.write(f"  SLO : {result['created']} créé(s) / {result['total']} total")

    def _setup_components(self):
        from apps.orion_ops.models import ServiceComponent, ComponentDependency

        created = 0
        for data in COMPONENTS:
            obj, was_created = ServiceComponent.objects.get_or_create(
                slug=data['slug'],
                defaults=data,
            )
            if was_created:
                created += 1
        self.stdout.write(f'  Composants : {created} créé(s) / {len(COMPONENTS)} total')

        # Dépendances
        dep_created = 0
        for source_slug, target_slug, dep_type, impact_desc in DEPENDENCIES:
            try:
                source = ServiceComponent.objects.get(slug=source_slug)
                target = ServiceComponent.objects.get(slug=target_slug)
                _, was_created = ComponentDependency.objects.get_or_create(
                    source=source, target=target,
                    defaults={'dep_type': dep_type, 'impact_desc': impact_desc},
                )
                if was_created:
                    dep_created += 1
            except ServiceComponent.DoesNotExist as e:
                self.stdout.write(self.style.WARNING(f'    Composant introuvable : {e}'))

        self.stdout.write(f'  Dépendances : {dep_created} créée(s) / {len(DEPENDENCIES)} total')

    def _setup_alert_rules(self):
        from apps.orion_ops.models import AlertRule
        created = 0
        for data in DEFAULT_ALERT_RULES:
            _, was_created = AlertRule.objects.get_or_create(
                name=data['name'],
                defaults={k: v for k, v in data.items() if k != 'name'},
            )
            if was_created:
                created += 1
        self.stdout.write(f'  Règles d\'alerte : {created} créée(s) / {len(DEFAULT_ALERT_RULES)} total')

    def _setup_beat_tasks(self):
        try:
            from django_celery_beat.models import PeriodicTask, CrontabSchedule
            import json

            tasks_to_create = [
                {
                    'name': 'orion-ops-collect-business-metrics',
                    'task': 'orion_ops.collect_business_metrics',
                    'cron': {'minute': '*/30', 'hour': '*', 'day_of_week': '*',
                             'day_of_month': '*', 'month_of_year': '*'},
                },
                {
                    'name': 'orion-ops-compute-extended-scores',
                    'task': 'orion_ops.compute_extended_scores',
                    'cron': {'minute': '10', 'hour': '*', 'day_of_week': '*',
                             'day_of_month': '*', 'month_of_year': '*'},
                },
                {
                    'name': 'orion-ops-refresh-slo-status',
                    'task': 'orion_ops.refresh_slo_status',
                    'cron': {'minute': '*/15', 'hour': '*', 'day_of_week': '*',
                             'day_of_month': '*', 'month_of_year': '*'},
                },
                {
                    'name': 'orion-ops-data-quality-daily',
                    'task': 'orion_ops.run_data_quality_checks',
                    'cron': {'minute': '30', 'hour': '3', 'day_of_week': '*',
                             'day_of_month': '*', 'month_of_year': '*'},
                },
                {
                    'name': 'orion-ops-purge-old-records',
                    'task': 'orion_ops.purge_old_extended_records',
                    'cron': {'minute': '0', 'hour': '5', 'day_of_week': '0',
                             'day_of_month': '*', 'month_of_year': '*'},
                },
                {
                    'name': 'orion-ops-capacity-trends',
                    'task': 'orion_ops.compute_capacity_trends',
                    'cron': {'minute': '20', 'hour': '*/6', 'day_of_week': '*',
                             'day_of_month': '*', 'month_of_year': '*'},
                },
                {
                    'name': 'orion-ops-evaluate-alert-rules',
                    'task': 'orion_ops.evaluate_alert_rules',
                    'cron': {'minute': '*/5', 'hour': '*', 'day_of_week': '*',
                             'day_of_month': '*', 'month_of_year': '*'},
                },
                {
                    'name': 'orion-ops-behavioral-detection',
                    'task': 'orion_ops.run_behavioral_detection',
                    'cron': {'minute': '*/30', 'hour': '*', 'day_of_week': '*',
                             'day_of_month': '*', 'month_of_year': '*'},
                },
            ]

            created_beat = 0
            for t in tasks_to_create:
                crontab, _ = CrontabSchedule.objects.get_or_create(**t['cron'])
                _, was_created = PeriodicTask.objects.get_or_create(
                    name=t['name'],
                    defaults={
                        'task': t['task'],
                        'crontab': crontab,
                        'args': json.dumps([]),
                        'enabled': True,
                    },
                )
                if was_created:
                    created_beat += 1
            self.stdout.write(f'  Celery Beat : {created_beat} tâche(s) créée(s) / {len(tasks_to_create)} total')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  Celery Beat non configuré : {e}'))
