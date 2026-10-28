"""
apps/orion_ops/services/slo_service.py — Calcul des SLO, budget d'erreur et violations.

Principe : chaque SLO lit les SensorReadings correspondantes sur la fenêtre
de mesure, calcule le taux de disponibilité réel, puis compare à la cible.
Aucune donnée n'est inventée — si les lectures sont absentes, le statut est
'no_data' et aucune violation n'est créée.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Optional

from django.db.models import Avg, Count, Q
from django.utils import timezone


def _get_period_bounds(period: str):
    """Retourne (start, end) pour la fenêtre de mesure du SLO."""
    now = timezone.now()
    if period == 'daily':
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'weekly':
        start = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0)
    elif period == 'monthly':
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == 'rolling_7d':
        start = now - timedelta(days=7)
    elif period == 'rolling_30d':
        start = now - timedelta(days=30)
    else:
        start = now - timedelta(hours=24)
    return start, now


def compute_slo_value(slo) -> Optional[float]:
    """
    Calcule la valeur actuelle du SLO en se basant sur les SensorReadings.
    Retourne None si les données sont insuffisantes.

    Pour les capteurs booléens (app_available, db_available) :
      valeur = % de lectures en statut 'ok' sur la période.
    Pour les capteurs numériques (avg_response_ms, error_rate_pct) :
      valeur = % de lectures sous le seuil défini dans target_pct.
    """
    from apps.system_health.models import SensorReading

    start, end = _get_period_bounds(slo.period)
    readings = SensorReading.objects.filter(
        sensor_type=slo.sli_sensor,
        collected_at__gte=start,
        collected_at__lte=end,
    )
    total = readings.count()
    if total < 3:
        return None

    # Pour les capteurs booléens : % de lectures ok
    boolean_sensors = {'app_available', 'db_available', 'backup_age_hours'}
    if slo.sli_sensor in boolean_sensors:
        ok_count = readings.filter(status='ok').count()
        return round(ok_count / total * 100, 3)

    # Pour queue_workers : % de lectures où au moins 1 worker tourne
    # (status 'warning' = 1 worker actif = fonctionnel mais non-idéal)
    if slo.sli_sensor == 'queue_workers':
        ok_count = readings.filter(value__gte=1).count()
        return round(ok_count / total * 100, 3)

    # Pour error_rate_pct : % de lectures où error_rate < seuil
    if slo.sli_sensor == 'error_rate_pct':
        ok_count = readings.filter(value__lt=slo.target_pct).count()
        return round(ok_count / total * 100, 3)

    # Défaut : % de lectures non critiques
    ok_count = readings.filter(status__in=['ok', 'warning']).count()
    return round(ok_count / total * 100, 3)


def compute_error_budget(slo, current_value: float) -> float:
    """
    Retourne le pourcentage de budget d'erreur restant.
    Budget total = (1 - target/100) × 100 points.
    Consommé = (1 - current/100) × 100 points.
    """
    total_budget = 100 - slo.target_pct
    if total_budget <= 0:
        return 100.0
    consumed = 100 - current_value
    remaining = total_budget - consumed
    return round(max(0.0, remaining / total_budget * 100), 1)


def refresh_slo(slo) -> dict:
    """
    Recalcule et persiste le statut d'un SLO.
    Crée une SLOBreach si l'objectif est violé pour la première fois.
    Retourne un dict résumé.
    """
    from apps.orion_ops.models import SLOBreach

    if not slo.enabled:
        slo.status = 'inactive'
        slo.save(update_fields=['status', 'updated_at'])
        return {'slug': slo.slug, 'status': 'inactive'}

    current_value = compute_slo_value(slo)
    if current_value is None:
        slo.status = 'no_data'
        slo.current_value = None
        slo.error_budget_pct = None
        slo.save(update_fields=['status', 'current_value', 'error_budget_pct', 'updated_at'])
        return {'slug': slo.slug, 'status': 'no_data'}

    error_budget = compute_error_budget(slo, current_value)
    at_risk_threshold = slo.compute_at_risk_threshold()

    if current_value < slo.target_pct:
        new_status = 'breached'
    elif current_value < at_risk_threshold:
        new_status = 'at_risk'
    else:
        new_status = 'ok'

    old_status = slo.status
    slo.current_value = current_value
    slo.error_budget_pct = error_budget
    slo.status = new_status
    slo.save(update_fields=['current_value', 'error_budget_pct', 'status', 'updated_at'])

    # Créer une violation si on passe en 'breached' et qu'il n'y en a pas
    # déjà une ouverte pour cette période.
    if new_status == 'breached' and old_status != 'breached':
        start, end = _get_period_bounds(slo.period)
        already_exists = SLOBreach.objects.filter(
            slo=slo,
            period_start=start,
            severity='breach',
        ).exists()
        if not already_exists:
            SLOBreach.objects.create(
                slo=slo,
                severity='breach',
                period_start=start,
                period_end=end,
                target_pct=slo.target_pct,
                actual_pct=current_value,
                budget_consumed_pct=100 - error_budget,
            )

    return {
        'slug': slo.slug,
        'status': new_status,
        'current_value': current_value,
        'error_budget_pct': error_budget,
    }


def refresh_all_slos() -> list:
    """Recalcule tous les SLO actifs. Appelé par la tâche Celery."""
    from apps.orion_ops.models import SLOTarget
    results = []
    for slo in SLOTarget.objects.filter(enabled=True).select_related('owner'):
        try:
            results.append(refresh_slo(slo))
        except Exception as exc:
            results.append({'slug': slo.slug, 'error': str(exc)})
    return results


def setup_default_slos():
    """
    Crée les SLO pré-configurés s'ils n'existent pas encore.
    Idempotent — ne modifie pas les SLO existants.
    """
    from apps.orion_ops.models import SLOTarget

    defaults = [
        {
            'name': 'Disponibilité ERP',
            'slug': 'erp-availability',
            'description': 'Pourcentage de cycles de collecte où l\'application est disponible.',
            'sli_sensor': 'app_available',
            'period': 'monthly',
            'target_pct': 99.9,
            'at_risk_pct': 99.5,
        },
        {
            'name': 'Taux d\'erreur HTTP',
            'slug': 'http-error-rate',
            'description': 'Pourcentage de cycles où le taux d\'erreur est inférieur à 3 %.',
            'sli_sensor': 'error_rate_pct',
            'period': 'weekly',
            'target_pct': 99.0,
            'at_risk_pct': 97.0,
        },
        {
            'name': 'Worker Celery disponible',
            'slug': 'celery-worker-available',
            'description': 'Pourcentage de cycles où au moins un worker Celery est actif.',
            'sli_sensor': 'queue_workers',
            'period': 'weekly',
            'target_pct': 99.0,
            'at_risk_pct': 95.0,
        },
        {
            'name': 'Sauvegarde journalière',
            'slug': 'daily-backup',
            'description': 'Pourcentage de cycles où la dernière sauvegarde a moins de 26 h.',
            'sli_sensor': 'backup_age_hours',
            'period': 'monthly',
            'target_pct': 95.0,
            'at_risk_pct': 90.0,
        },
        {
            'name': 'Base de données disponible',
            'slug': 'db-availability',
            'description': 'Pourcentage de cycles où la base de données répond.',
            'sli_sensor': 'db_available',
            'period': 'monthly',
            'target_pct': 99.9,
            'at_risk_pct': 99.5,
        },
    ]

    created = 0
    for d in defaults:
        _, was_created = SLOTarget.objects.get_or_create(slug=d['slug'], defaults=d)
        if was_created:
            created += 1
    return {'created': created, 'total': len(defaults)}
