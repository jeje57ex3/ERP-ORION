"""
apps/orion_ops/services/behavioral_detection.py — Détection comportementale.

Identifie des patterns suspects en croisant :
  - SensorReading (failed_logins_1h)
  - SecurityEvent (2fa_failed, recovery_code_used)
  - AuditLog ou RequestLog (accès hors-heures)

Chaque détection crée une DataQualityAnomaly de type 'custom' ou une
SystemError selon la gravité, sans jamais exposer de données sensibles.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger('orion_ops.behavioral')


# ─── Détection 1 : Force brute sur les connexions ─────────────────────────────

def detect_brute_force() -> dict:
    """
    Détecte des pics de tentatives de connexion échouées.
    Seuil : > 15 échecs en 1h → anomalie haute ; > 30 → critique.
    Source : SensorReading.failed_logins_1h
    """
    from apps.system_health.models import SensorReading

    result = {'detected': False, 'count': 0, 'severity': None}
    reading = (SensorReading.objects
               .filter(sensor_type='failed_logins_1h',
                       collected_at__gte=timezone.now() - timedelta(hours=1))
               .order_by('-collected_at').first())

    if reading is None or reading.value is None:
        return result

    count = int(reading.value)
    result['count'] = count

    if count >= 30:
        severity = 'critical'
    elif count >= 15:
        severity = 'high'
    else:
        return result

    result['detected'] = True
    result['severity'] = severity

    _upsert_security_anomaly(
        anomaly_type='custom',
        severity=severity,
        count=count,
        module='other',
        cause=f'{count} tentatives de connexion échouées en 1h',
        fix_hint='Vérifier les logs d\'accès, envisager un blocage IP temporaire.',
        dedup_key='brute_force_logins',
    )
    return result


# ─── Détection 2 : Pic d'échecs 2FA par utilisateur ──────────────────────────

def detect_2fa_failure_spike() -> dict:
    """
    Détecte si un utilisateur a échoué la 2FA plus de 5 fois en 30 min.
    Source : SecurityEvent(event='2fa_failed')
    """
    try:
        from apps.user_security.models import SecurityEvent
    except ImportError:
        return {'detected': False, 'users_affected': 0}

    cutoff = timezone.now() - timedelta(minutes=30)
    from django.db.models import Count

    spikes = (SecurityEvent.objects
              .filter(event='2fa_failed', created_at__gte=cutoff)
              .values('user_id')
              .annotate(total=Count('pk'))
              .filter(total__gte=5))

    count = spikes.count()
    if count == 0:
        return {'detected': False, 'users_affected': 0}

    _upsert_security_anomaly(
        anomaly_type='custom',
        severity='high',
        count=count,
        module='other',
        cause=f'{count} compte(s) avec ≥ 5 échecs 2FA en 30 min',
        fix_hint='Examiner les sessions actives de ces comptes. Envisager un verrouillage temporaire.',
        dedup_key='2fa_failure_spike',
    )
    return {'detected': True, 'users_affected': count}


# ─── Détection 3 : Utilisation de codes de récupération 2FA ─────────────────

def detect_recovery_code_usage() -> dict:
    """
    Alerte si des codes de récupération 2FA ont été utilisés récemment.
    Ces codes ne doivent être utilisés qu'exceptionnellement.
    Source : SecurityEvent(event='recovery_code_used')
    """
    try:
        from apps.user_security.models import SecurityEvent
    except ImportError:
        return {'detected': False, 'count': 0}

    cutoff = timezone.now() - timedelta(hours=24)
    count = SecurityEvent.objects.filter(
        event='recovery_code_used', created_at__gte=cutoff
    ).count()

    if count == 0:
        return {'detected': False, 'count': 0}

    _upsert_security_anomaly(
        anomaly_type='custom',
        severity='high' if count > 1 else 'medium',
        count=count,
        module='other',
        cause=f'{count} code(s) de récupération 2FA utilisé(s) en 24h',
        fix_hint='Vérifier que l\'utilisateur est légitime. Régénérer les codes si nécessaire.',
        dedup_key='recovery_code_usage_24h',
    )
    return {'detected': True, 'count': count}


# ─── Détection 4 : Nombre d'erreurs Celery trop élevé ────────────────────────

def detect_failed_task_accumulation() -> dict:
    """
    Détecte une accumulation anormale de tâches Celery échouées non fermées.
    Seuil : > 10 tâches 'failed' dans la journée.
    """
    from apps.orion_ops.models import FailedTask

    today_cutoff = timezone.now() - timedelta(hours=24)
    count = FailedTask.objects.filter(status='failed', failed_at__gte=today_cutoff).count()

    if count < 10:
        return {'detected': False, 'count': count}

    severity = 'critical' if count >= 30 else 'high'
    _upsert_security_anomaly(
        anomaly_type='custom',
        severity=severity,
        count=count,
        module='other',
        cause=f'{count} tâches Celery échouées non traitées en 24h',
        fix_hint='Consulter /orion-admin/ops/taches-echouees/ pour examiner les erreurs.',
        dedup_key='celery_failed_tasks_accumulation',
    )
    return {'detected': True, 'count': count}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _upsert_security_anomaly(
    anomaly_type: str,
    severity: str,
    count: int,
    module: str,
    cause: str,
    fix_hint: str,
    dedup_key: str,
) -> None:
    """
    Crée ou met à jour une DataQualityAnomaly de type sécurité comportementale.
    Déduplique sur dedup_key (stocké dans cause) sur une fenêtre de 24h.
    """
    from apps.orion_ops.models import DataQualityAnomaly

    cutoff = timezone.now() - timedelta(hours=24)
    existing = DataQualityAnomaly.objects.filter(
        anomaly_type=anomaly_type,
        cause__startswith=dedup_key,
        status__in=['open', 'acknowledged'],
        detected_at__gte=cutoff,
    ).first()

    if existing:
        existing.count = count
        existing.save(update_fields=['count'])
        return

    DataQualityAnomaly.objects.create(
        anomaly_type=anomaly_type,
        severity=severity,
        count=count,
        module=module,
        cause=f'{dedup_key}: {cause}',
        fix_hint=fix_hint,
        status='open',
    )


# ─── Collecteur principal ─────────────────────────────────────────────────────

def run_behavioral_detection() -> dict:
    """
    Lance tous les contrôles de détection comportementale.
    Retourne un résumé des détections.
    """
    results = {}
    detectors = [
        ('brute_force',          detect_brute_force),
        ('2fa_spike',            detect_2fa_failure_spike),
        ('recovery_code',        detect_recovery_code_usage),
        ('failed_task_backlog',  detect_failed_task_accumulation),
    ]

    for name, fn in detectors:
        try:
            results[name] = fn()
        except Exception as e:
            logger.error('behavioral_detection: error in %s: %s', name, e)
            results[name] = {'detected': False, 'error': str(e)}

    total_detected = sum(1 for r in results.values() if r.get('detected'))
    logger.info('behavioral_detection: %d/%d checks triggered anomalies',
                total_detected, len(detectors))
    return results
