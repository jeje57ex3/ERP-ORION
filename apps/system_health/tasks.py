"""
apps/system_health/tasks.py — Tâches Celery de collecte des capteurs.
"""
import logging
from celery import shared_task

logger = logging.getLogger('system_health')


@shared_task(name='system_health.collect_all_sensors', bind=True, max_retries=2)
def collect_all_sensors(self):
    """
    Collecte tous les capteurs, calcule le score global, enregistre un snapshot,
    et déclenche les alertes automatiques si nécessaire.
    Planifié toutes les 5 minutes via Celery Beat.
    """
    from . import services
    from .models import HealthSnapshot

    try:
        # 1. Récupérer l'état précédent avant d'écraser les lectures
        last_snapshot = HealthSnapshot.objects.order_by('-collected_at').first()
        prev_criticals = last_snapshot.critical_sensors if last_snapshot else []

        # 2. Collecter tous les capteurs
        services.collect_server_sensors()
        services.collect_app_sensors()
        services.collect_db_sensors()
        services.collect_backup_sensors()
        services.collect_security_sensors()
        services.collect_celery_sensors()

        # 3. Calculer le score global
        health = services.compute_global_health()

        # 4. Enregistrer le snapshot
        services.save_health_snapshot(health)

        # 5. Vérifier et déclencher les alertes automatiques
        services.check_and_alert(prev_criticals, health)

        logger.info(
            'system_health collected: global=%d/100 (%s) — criticals=%s',
            health['score'], health['status'], health.get('critical', [])
        )
        return {
            'score': health['score'],
            'status': health['status'],
            'breakdown': health['breakdown'],
        }

    except Exception as exc:
        logger.exception('collect_all_sensors failed: %s', exc)
        raise self.retry(exc=exc, countdown=60)


@shared_task(name='system_health.purge_old_sensor_readings')
def purge_old_sensor_readings(days=90):
    """Purge les lectures de capteurs et snapshots anciens."""
    from . import services
    deleted_readings = services.purge_old_sensor_readings(days=days)
    deleted_snapshots = services.purge_old_snapshots(days=30)
    return {'deleted_readings': deleted_readings, 'deleted_snapshots': deleted_snapshots}
