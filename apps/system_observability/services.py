import logging
import time

from django.utils import timezone
from .models import SystemHealthCheck, SystemObservabilityAlert

logger = logging.getLogger('system_observability')


def record_health_check(company, check_type, status, *, message='',
                        response_time_ms=None, metadata=None):
    return SystemHealthCheck.objects.create(
        company=company, check_type=check_type, status=status,
        message=message, response_time_ms=response_time_ms,
        metadata=metadata or {},
    )


def get_latest_health_checks(company):
    """Returns the most recent check per check_type."""
    from django.db.models import Max
    latest_ids = (
        SystemHealthCheck.objects.filter(company=company)
        .values('check_type')
        .annotate(latest_id=Max('id'))
        .values_list('latest_id', flat=True)
    )
    return SystemHealthCheck.objects.filter(
        pk__in=latest_ids
    ).order_by('check_type')


def get_health_status(company):
    checks = list(get_latest_health_checks(company))
    if not checks:
        return 'unknown'
    statuses = {c.status for c in checks}
    if 'critical' in statuses:
        return 'critical'
    if 'warning' in statuses:
        return 'warning'
    if all(c.status == 'ok' for c in checks):
        return 'ok'
    return 'unknown'


def create_system_alert(company, alert_type, severity, title, message, metadata=None):
    return SystemObservabilityAlert.objects.create(
        company=company, alert_type=alert_type, severity=severity,
        title=title, message=message, metadata=metadata or {},
    )


def acknowledge_system_alert(alert, user):
    alert.is_acknowledged = True
    alert.acknowledged_by = user
    alert.acknowledged_at = timezone.now()
    alert.save(update_fields=['is_acknowledged', 'acknowledged_by', 'acknowledged_at'])
    return alert


def get_system_alerts(company, *, severity=None, include_acknowledged=False):
    qs = SystemObservabilityAlert.objects.filter(company=company)
    if not include_acknowledged:
        qs = qs.filter(is_acknowledged=False)
    if severity:
        qs = qs.filter(severity=severity)
    return qs.order_by('-created_at')


def get_check_history(company, check_type, limit=50):
    return SystemHealthCheck.objects.filter(
        company=company, check_type=check_type
    ).order_by('-checked_at')[:limit]


def get_observability_stats(company):
    checks = list(get_latest_health_checks(company))
    alerts = SystemObservabilityAlert.objects.filter(company=company)
    return {
        'overall_status': get_health_status(company),
        'checks_ok': sum(1 for c in checks if c.status == 'ok'),
        'checks_warning': sum(1 for c in checks if c.status == 'warning'),
        'checks_critical': sum(1 for c in checks if c.status == 'critical'),
        'unacknowledged_alerts': alerts.filter(is_acknowledged=False).count(),
        'critical_alerts': alerts.filter(severity='critical', is_acknowledged=False).count(),
    }


# ─── Collecte des checks (16.x — voir apps.system_health pour les capteurs serveur) ──
# Rien n'appelait record_health_check() : cette section fournit les checks
# réellement exécutés par `manage.py collect_observability_checks`.

def _status_from_percent(pct):
    if pct is None:
        return 'unknown'
    if pct >= 90:
        return 'critical'
    if pct >= 80:
        return 'warning'
    return 'ok'


def check_database(company):
    from django.db import connection
    start = time.perf_counter()
    try:
        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        elapsed_ms = round((time.perf_counter() - start) * 1000)
        return record_health_check(
            company, 'database', 'ok',
            message='Connexion base de données OK.', response_time_ms=elapsed_ms,
        )
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - start) * 1000)
        return record_health_check(
            company, 'database', 'critical',
            message=f'Connexion impossible : {exc}', response_time_ms=elapsed_ms,
        )


def check_cache(company):
    from django.core.cache import cache
    key = '_system_observability_cache_check'
    start = time.perf_counter()
    try:
        cache.set(key, 'ok', timeout=30)
        ok = cache.get(key) == 'ok'
        elapsed_ms = round((time.perf_counter() - start) * 1000)
        return record_health_check(
            company, 'cache', 'ok' if ok else 'warning',
            message='Cache opérationnel.' if ok else 'Lecture/écriture cache incohérente.',
            response_time_ms=elapsed_ms,
        )
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - start) * 1000)
        return record_health_check(
            company, 'cache', 'critical',
            message=f'Cache indisponible : {exc}', response_time_ms=elapsed_ms,
        )


def _disk_summary():
    """Réutilise le calcul d'usage disque déjà en place dans system_health
    plutôt que de dupliquer la logique psutil."""
    try:
        from apps.system_health.services import get_disk_summary
        return get_disk_summary()
    except Exception as exc:
        logger.warning('get_disk_summary indisponible : %s', exc)
        return None


def check_storage(company):
    summary = _disk_summary()
    if not summary:
        return record_health_check(company, 'storage', 'unknown', message='Lecture disque indisponible.')
    return record_health_check(
        company, 'storage', summary['status'],
        message=f"{summary['used_gb']} Go utilisés / {summary['total_gb']} Go ({summary['percent']}%).",
        metadata={'percent': summary['percent'], 'free_gb': summary['free_gb']},
    )


def check_disk_space(company):
    summary = _disk_summary()
    if not summary:
        return record_health_check(company, 'disk_space', 'unknown', message='Lecture disque indisponible.')
    return record_health_check(
        company, 'disk_space', summary['status'],
        message=f"{summary['free_gb']} Go libres sur {summary['total_gb']} Go.",
        metadata={'percent': summary['percent']},
    )


def check_memory(company):
    try:
        import psutil
        mem = psutil.virtual_memory()
        return record_health_check(
            company, 'memory', _status_from_percent(mem.percent),
            message=f'{mem.percent}% utilisé ({round(mem.used / 1e9, 1)} Go / {round(mem.total / 1e9, 1)} Go).',
            metadata={'percent': mem.percent},
        )
    except ImportError:
        return record_health_check(company, 'memory', 'unknown', message='psutil non installé.')
    except Exception as exc:
        return record_health_check(company, 'memory', 'unknown', message=str(exc))


def check_cpu(company):
    try:
        import psutil
        pct = psutil.cpu_percent(interval=0.5)
        return record_health_check(
            company, 'cpu', _status_from_percent(pct),
            message=f'{pct}% de charge CPU.', metadata={'percent': pct},
        )
    except ImportError:
        return record_health_check(company, 'cpu', 'unknown', message='psutil non installé.')
    except Exception as exc:
        return record_health_check(company, 'cpu', 'unknown', message=str(exc))


def check_email(company):
    from django.conf import settings
    backend = getattr(settings, 'EMAIL_BACKEND', '')
    if 'smtp' not in backend.lower():
        return record_health_check(
            company, 'email', 'ok',
            message=f'Backend {backend.rsplit(".", 1)[-1]} actif (pas de SMTP à vérifier).',
        )
    start = time.perf_counter()
    try:
        from django.core.mail import get_connection
        conn = get_connection()
        conn.open()
        conn.close()
        elapsed_ms = round((time.perf_counter() - start) * 1000)
        return record_health_check(
            company, 'email', 'ok',
            message=f'Connexion SMTP {settings.EMAIL_HOST}:{settings.EMAIL_PORT} OK.',
            response_time_ms=elapsed_ms,
        )
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - start) * 1000)
        return record_health_check(
            company, 'email', 'critical',
            message=f'Connexion SMTP impossible : {exc}', response_time_ms=elapsed_ms,
        )


def check_queue(company):
    from django.conf import settings
    broker = getattr(settings, 'CELERY_BROKER_URL', None)
    if not broker:
        return record_health_check(
            company, 'queue', 'unknown',
            message='Celery non configuré sur cette instance (CELERY_BROKER_URL absent).',
        )
    try:
        from celery import current_app
        pong = current_app.control.ping(timeout=1.0)
        if pong:
            return record_health_check(company, 'queue', 'ok', message=f'{len(pong)} worker(s) répondent.')
        return record_health_check(company, 'queue', 'critical', message='Aucun worker Celery ne répond.')
    except Exception as exc:
        return record_health_check(company, 'queue', 'critical', message=f'Broker injoignable : {exc}')


def check_external_api(company):
    """Aucune intégration externe générique n'est câblée pour l'instant —
    honnête plutôt qu'un faux positif : marque le check comme non applicable."""
    return record_health_check(
        company, 'external_api', 'unknown',
        message='Aucune API externe configurée pour cette entreprise.',
    )


CHECK_FUNCTIONS = [
    ('database', check_database),
    ('cache', check_cache),
    ('storage', check_storage),
    ('disk_space', check_disk_space),
    ('memory', check_memory),
    ('cpu', check_cpu),
    ('email', check_email),
    ('queue', check_queue),
    ('external_api', check_external_api),
]


def run_all_checks(company):
    """Exécute tous les checks pour une entreprise et retourne les résultats créés."""
    results = []
    for label, fn in CHECK_FUNCTIONS:
        try:
            results.append(fn(company))
        except Exception as exc:
            logger.exception('Échec du check %s pour %s : %s', label, company, exc)
            results.append(record_health_check(company, label, 'unknown', message=f'Erreur interne : {exc}'))
    return results
