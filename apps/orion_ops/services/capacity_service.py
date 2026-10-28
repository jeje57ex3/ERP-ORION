"""
apps/orion_ops/services/capacity_service.py — Prévision de capacité par régression linéaire.

Pour chaque ressource (disque, DB, mémoire…) : on compare la valeur actuelle
aux lectures historiques SensorReading des 7 et 30 derniers jours, puis on
projette linéairement la date de saturation.

Principe :
  - Seule la tendance réelle mesurée est utilisée
  - Si la tendance est décroissante ou stable, days_until_limit = None
  - Si la projection dépasse 365 jours, on considère que c'est non-urgent
"""
from __future__ import annotations

from datetime import timedelta, date
from typing import Optional

from django.utils import timezone


def _sensor_avg(sensor_type: str, start, end) -> Optional[float]:
    """Moyenne des lectures d'un capteur sur une période."""
    from apps.system_health.models import SensorReading
    from django.db.models import Avg
    r = (SensorReading.objects
         .filter(sensor_type=sensor_type, collected_at__gte=start, collected_at__lte=end)
         .aggregate(avg=Avg('value')))
    return r['avg']


def _sensor_latest(sensor_type: str) -> Optional[float]:
    from apps.system_health.models import SensorReading
    r = SensorReading.objects.filter(sensor_type=sensor_type).order_by('-collected_at').first()
    return r.value if r else None


def _project_days_until_limit(current: float, growth_per_day: float,
                               limit: float, is_percentage: bool = True) -> Optional[int]:
    """
    Calcule dans combien de jours `current` atteint `limit` au rythme `growth_per_day`.
    Retourne None si croissance ≤ 0 ou délai > 365 jours.
    """
    if growth_per_day <= 0:
        return None
    if is_percentage:
        remaining = limit - current
    else:
        remaining = current - limit  # pour "combien de Go avant d'être à 0"
    if remaining <= 0:
        return 0
    days = remaining / growth_per_day
    return int(days) if days <= 365 else None


def compute_disk_trend() -> dict:
    """Disque C: — capteur disk_usage (% utilisé)."""
    now = timezone.now()
    current = _sensor_latest('disk_usage')
    if current is None:
        return {'resource_type': 'disk_c', 'status': 'no_data'}

    avg_7d = _sensor_avg('disk_usage', now - timedelta(days=7), now - timedelta(days=1))
    avg_30d = _sensor_avg('disk_usage', now - timedelta(days=30), now - timedelta(days=8))

    growth_7d_pct = None
    growth_30d_pct = None
    growth_per_day = None

    if avg_7d is not None and avg_7d > 0:
        growth_7d_pct = round((current - avg_7d) / avg_7d * 100, 2)
        daily_change = (current - avg_7d) / 7
        growth_per_day = daily_change

    if avg_30d is not None and avg_30d > 0:
        growth_30d_pct = round((current - avg_30d) / avg_30d * 100, 2)

    days = None
    sat_date = None
    if growth_per_day and growth_per_day > 0:
        days = _project_days_until_limit(current, growth_per_day, 95.0, is_percentage=True)
        if days is not None:
            sat_date = (date.today() + timedelta(days=days))

    recommendation = ''
    if current > 95:
        recommendation = 'URGENT: Disque C: quasi plein. Déplacer des fichiers vers D: immédiatement.'
    elif days is not None and days < 30:
        recommendation = f'Disque C: saturera dans environ {days} jours. Planifier un nettoyage.'
    elif days is not None and days < 90:
        recommendation = f'Disque C: saturera dans environ {days} jours. Surveiller.'

    return {
        'resource_type': 'disk_c',
        'current_value': current,
        'value_7d_ago': avg_7d,
        'value_30d_ago': avg_30d,
        'growth_7d_pct': growth_7d_pct,
        'growth_30d_pct': growth_30d_pct,
        'days_until_limit': days,
        'saturation_date': sat_date,
        'alert_threshold': 90.0,
        'recommendation': recommendation,
    }


def compute_memory_trend() -> dict:
    """Mémoire RAM — capteur memory_usage (%)."""
    now = timezone.now()
    current = _sensor_latest('memory_usage')
    if current is None:
        return {'resource_type': 'memory_pct', 'status': 'no_data'}

    avg_7d = _sensor_avg('memory_usage', now - timedelta(days=7), now - timedelta(days=1))
    avg_30d = _sensor_avg('memory_usage', now - timedelta(days=30), now - timedelta(days=8))

    growth_7d_pct = None
    growth_30d_pct = None
    growth_per_day = None
    days = None
    sat_date = None

    if avg_7d is not None and avg_7d > 0:
        growth_7d_pct = round((current - avg_7d) / avg_7d * 100, 2)
        growth_per_day = (current - avg_7d) / 7

    if avg_30d is not None and avg_30d > 0:
        growth_30d_pct = round((current - avg_30d) / avg_30d * 100, 2)

    if growth_per_day and growth_per_day > 0:
        days = _project_days_until_limit(current, growth_per_day, 95.0)
        if days is not None:
            sat_date = date.today() + timedelta(days=days)

    recommendation = ''
    if current > 90:
        recommendation = 'Mémoire critique. Vérifier les fuites mémoire ou augmenter la RAM.'
    elif current > 80:
        recommendation = 'Mémoire élevée. Surveiller les workers Celery et Django.'

    return {
        'resource_type': 'memory_pct',
        'current_value': current,
        'value_7d_ago': avg_7d,
        'value_30d_ago': avg_30d,
        'growth_7d_pct': growth_7d_pct,
        'growth_30d_pct': growth_30d_pct,
        'days_until_limit': days,
        'saturation_date': sat_date,
        'alert_threshold': 85.0,
        'recommendation': recommendation,
    }


def compute_db_size_trend() -> dict:
    """Taille de la base de données — capteur db_size_gb (Go)."""
    now = timezone.now()
    current = _sensor_latest('db_size_gb')
    if current is None:
        return {'resource_type': 'db_size_gb', 'status': 'no_data'}

    avg_7d = _sensor_avg('db_size_gb', now - timedelta(days=7), now - timedelta(days=1))
    avg_30d = _sensor_avg('db_size_gb', now - timedelta(days=30), now - timedelta(days=8))

    growth_7d_pct = None
    growth_30d_pct = None
    growth_per_day = None
    days = None
    sat_date = None

    if avg_7d is not None and avg_7d > 0:
        growth_7d_pct = round((current - avg_7d) / avg_7d * 100, 2)
        growth_per_day = (current - avg_7d) / 7

    if avg_30d is not None and avg_30d > 0:
        growth_30d_pct = round((current - avg_30d) / avg_30d * 100, 2)

    # Limite : on suppose 100 Go disponibles (sera affiné par config future)
    if growth_per_day and growth_per_day > 0:
        limit_gb = 50.0  # seuil d'alerte à 50 Go
        if current < limit_gb:
            remaining_days = (limit_gb - current) / growth_per_day
            days = int(remaining_days) if remaining_days <= 365 else None
            if days is not None:
                sat_date = date.today() + timedelta(days=days)

    recommendation = ''
    if growth_30d_pct and growth_30d_pct > 20:
        recommendation = f'La DB a grossi de {growth_30d_pct:.1f}% en 30 jours. Vérifier les archives et purges.'

    return {
        'resource_type': 'db_size_gb',
        'current_value': current,
        'value_7d_ago': avg_7d,
        'value_30d_ago': avg_30d,
        'growth_7d_pct': growth_7d_pct,
        'growth_30d_pct': growth_30d_pct,
        'days_until_limit': days,
        'saturation_date': sat_date,
        'alert_threshold': 30.0,
        'recommendation': recommendation,
    }


def compute_cpu_trend() -> dict:
    """CPU — capteur cpu_usage (%)."""
    now = timezone.now()
    current = _sensor_latest('cpu_usage')
    if current is None:
        return {'resource_type': 'cpu_avg', 'status': 'no_data'}

    avg_7d = _sensor_avg('cpu_usage', now - timedelta(days=7), now - timedelta(days=1))
    avg_30d = _sensor_avg('cpu_usage', now - timedelta(days=30), now - timedelta(days=8))

    growth_7d_pct = None
    growth_30d_pct = None

    if avg_7d is not None and avg_7d > 0:
        growth_7d_pct = round((current - avg_7d) / avg_7d * 100, 2)
    if avg_30d is not None and avg_30d > 0:
        growth_30d_pct = round((current - avg_30d) / avg_30d * 100, 2)

    recommendation = ''
    if current > 85:
        recommendation = 'CPU élevé. Investiguer les processus lourds. Envisager une optimisation des tâches.'

    return {
        'resource_type': 'cpu_avg',
        'current_value': current,
        'value_7d_ago': avg_7d,
        'value_30d_ago': avg_30d,
        'growth_7d_pct': growth_7d_pct,
        'growth_30d_pct': growth_30d_pct,
        'days_until_limit': None,
        'saturation_date': None,
        'alert_threshold': 80.0,
        'recommendation': recommendation,
    }


def run_all_capacity_trends() -> list:
    """Calcule et enregistre les tendances de toutes les ressources surveillées."""
    from apps.orion_ops.models import CapacityTrend

    computers = [
        compute_disk_trend,
        compute_memory_trend,
        compute_db_size_trend,
        compute_cpu_trend,
    ]
    saved = []
    for fn in computers:
        try:
            data = fn()
            if data.get('status') == 'no_data':
                continue
            CapacityTrend.objects.create(
                resource_type=data['resource_type'],
                current_value=data['current_value'],
                value_7d_ago=data.get('value_7d_ago'),
                value_30d_ago=data.get('value_30d_ago'),
                growth_7d_pct=data.get('growth_7d_pct'),
                growth_30d_pct=data.get('growth_30d_pct'),
                days_until_limit=data.get('days_until_limit'),
                saturation_date=data.get('saturation_date'),
                alert_threshold=data.get('alert_threshold'),
                recommendation=data.get('recommendation', ''),
            )
            saved.append(data['resource_type'])
        except Exception as e:
            saved.append({'error': fn.__name__, 'detail': str(e)})
    return saved


def get_latest_capacity_trends() -> dict:
    """Retourne le dernier CapacityTrend pour chaque ressource."""
    from apps.orion_ops.models import CapacityTrend

    resources = ['disk_c', 'disk_d', 'memory_pct', 'cpu_avg', 'db_size_gb',
                 'backup_size', 'table_rows']
    result = {}
    for r in resources:
        trend = CapacityTrend.objects.filter(resource_type=r).order_by('-computed_at').first()
        result[r] = trend
    return result
