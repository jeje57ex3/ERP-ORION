"""
apps/system_observability/tasks.py — Tâche Celery de collecte des checks.
Même schéma que apps.system_health.tasks.collect_all_sensors : à planifier
toutes les 5 minutes via Celery Beat une fois Celery configuré. En
attendant, `manage.py collect_observability_checks` fait la même chose à
la demande.
"""
import logging
from celery import shared_task

logger = logging.getLogger('system_observability')


@shared_task(name='system_observability.collect_all_checks', bind=True, max_retries=2)
def collect_all_checks(self):
    from apps.core.models import Company
    from .services import run_all_checks

    try:
        for company in Company.objects.filter(is_active=True):
            run_all_checks(company)
    except Exception as exc:
        logger.exception('Échec collecte observabilité : %s', exc)
        raise self.retry(exc=exc, countdown=60)
