"""
apps/orion_ops/tasks.py — Tâches Celery planifiées pour l'observabilité OpsV2.

Files utilisées :
  - 'default'     : collecte des métriques métier (toutes les 30 min)
  - 'maintenance' : contrôles qualité données (quotidien), calcul scores (horaire)
"""
from celery import shared_task

import logging

logger = logging.getLogger('orion_ops')


@shared_task(
    name='orion_ops.collect_business_metrics',
    bind=True,
    max_retries=2,
    queue='default',
)
def collect_business_metrics(self):
    """Collecte toutes les métriques métier fonctionnelles."""
    try:
        from apps.orion_ops.services.business_metric_service import collect_all_business_metrics
        result = collect_all_business_metrics()
        logger.info('Business metrics collected: %s', result)
        return result
    except Exception as exc:
        logger.exception('collect_business_metrics failed')
        raise self.retry(exc=exc, countdown=60)


@shared_task(
    name='orion_ops.compute_extended_scores',
    bind=True,
    max_retries=1,
    queue='maintenance',
)
def compute_extended_scores(self):
    """Calcule et persiste les 7 scores de santé étendus."""
    try:
        from apps.orion_ops.services.score_service import compute_all_extended_scores
        result = compute_all_extended_scores()
        logger.info('Extended scores computed: %s', result)
        return result
    except Exception as exc:
        logger.exception('compute_extended_scores failed')
        raise self.retry(exc=exc, countdown=120)


@shared_task(
    name='orion_ops.refresh_slo_status',
    bind=True,
    max_retries=1,
    queue='maintenance',
)
def refresh_slo_status(self):
    """Recalcule le statut de tous les SLO actifs."""
    try:
        from apps.orion_ops.services.slo_service import refresh_all_slos
        result = refresh_all_slos()
        breached = sum(1 for r in result if r.get('status') == 'breached')
        logger.info('SLO refresh done: %d SLO(s), %d breached', len(result), breached)
        return {'total': len(result), 'breached': breached}
    except Exception as exc:
        logger.exception('refresh_slo_status failed')
        raise self.retry(exc=exc, countdown=120)


@shared_task(
    name='orion_ops.run_data_quality_checks',
    bind=True,
    max_retries=1,
    queue='maintenance',
)
def run_data_quality_checks(self):
    """Lance les contrôles de qualité des données (quotidien)."""
    try:
        from apps.orion_ops.services.data_quality_service import run_all_data_quality_checks
        result = run_all_data_quality_checks()
        logger.info('Data quality checks done: %s', result)
        return result
    except Exception as exc:
        logger.exception('run_data_quality_checks failed')
        raise self.retry(exc=exc, countdown=300)


@shared_task(
    name='orion_ops.compute_capacity_trends',
    bind=True,
    max_retries=1,
    queue='maintenance',
)
def compute_capacity_trends(self):
    """Calcule les prévisions de capacité pour toutes les ressources."""
    try:
        from apps.orion_ops.services.capacity_service import run_all_capacity_trends
        result = run_all_capacity_trends()
        logger.info('Capacity trends computed: %s', result)
        return {'saved': result}
    except Exception as exc:
        logger.exception('compute_capacity_trends failed')
        raise self.retry(exc=exc, countdown=120)


@shared_task(
    name='orion_ops.run_behavioral_detection',
    bind=True,
    max_retries=1,
    queue='maintenance',
)
def run_behavioral_detection(self):
    """Détection comportementale : brute force, 2FA spike, codes de récupération, backlog Celery."""
    try:
        from apps.orion_ops.services.behavioral_detection import run_behavioral_detection as _run
        result = _run()
        detected = sum(1 for r in result.values() if r.get('detected'))
        if detected:
            logger.warning('behavioral_detection: %d anomalie(s) détectée(s)', detected)
        else:
            logger.info('behavioral_detection: aucune anomalie comportementale')
        return result
    except Exception as exc:
        logger.exception('run_behavioral_detection failed')
        raise self.retry(exc=exc, countdown=120)


@shared_task(
    name='orion_ops.evaluate_alert_rules',
    bind=True,
    max_retries=1,
    queue='maintenance',
)
def evaluate_alert_rules(self):
    """Évalue toutes les règles d'alerte actives contre les données live."""
    try:
        from apps.orion_ops.services.rule_engine import evaluate_all_rules
        result = evaluate_all_rules()
        if result['triggered'] > 0:
            logger.warning('Alert rules: %d triggered, %d skipped, %d errors',
                           result['triggered'], result['skipped'], result['errors'])
        else:
            logger.info('Alert rules evaluated: %d total, none triggered', result['total'])
        return result
    except Exception as exc:
        logger.exception('evaluate_alert_rules failed')
        raise self.retry(exc=exc, countdown=60)


@shared_task(
    name='orion_ops.purge_old_extended_records',
    queue='maintenance',
)
def purge_old_extended_records(days_scores=30, days_metrics=14, days_capacity=60):
    """Purge les enregistrements anciens pour éviter la croissance illimitée."""
    from django.utils import timezone
    from datetime import timedelta
    from apps.orion_ops.models import HealthScoreRecord, BusinessMetricReading, CapacityTrend

    now = timezone.now()
    deleted_scores = HealthScoreRecord.objects.filter(
        computed_at__lt=now - timedelta(days=days_scores)
    ).delete()[0]
    deleted_metrics = BusinessMetricReading.objects.filter(
        collected_at__lt=now - timedelta(days=days_metrics)
    ).delete()[0]
    deleted_capacity = CapacityTrend.objects.filter(
        computed_at__lt=now - timedelta(days=days_capacity)
    ).delete()[0]

    return {
        'deleted_scores': deleted_scores,
        'deleted_metrics': deleted_metrics,
        'deleted_capacity': deleted_capacity,
    }
