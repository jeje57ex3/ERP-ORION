"""
apps/orion_ops/services/rule_engine.py — Moteur d'évaluation des règles d'alerte.

Principe : chaque AlertRule est évaluée contre la valeur live de sa source.
Si la condition est vérifiée ET que la règle n'a pas déjà été déclenchée dans
sa fenêtre de fréquence, les actions configurées sont exécutées.

Garanties :
  - Idempotent sur la fenêtre frequency_min (pas de doublon d'alertes)
  - Les règles silencieuses (silence_until) sont ignorées
  - Les secrets ne sont jamais inclus dans les messages d'alerte
  - Les actions sont exécutées sans bloquer l'évaluation des autres règles
"""
from __future__ import annotations

import logging
import operator as op
from datetime import timedelta
from typing import Optional

from django.utils import timezone

logger = logging.getLogger('orion_ops.rule_engine')


# ─── Opérateurs ───────────────────────────────────────────────────────────────

_OPERATORS = {
    'gt':  op.gt,
    'lt':  op.lt,
    'gte': op.ge,
    'lte': op.le,
    'eq':  op.eq,
    'neq': op.ne,
}


def _evaluate_condition(current_value: float, operator_key: str, threshold: float) -> bool:
    fn = _OPERATORS.get(operator_key)
    if fn is None:
        return False
    return fn(current_value, threshold)


# ─── Récupération de la valeur courante par source ────────────────────────────

def _get_current_value(source: str, metric_key: str, max_age_hours: int = 2) -> Optional[float]:
    cutoff = timezone.now() - timedelta(hours=max_age_hours)

    if source == 'sensor':
        from apps.system_health.models import SensorReading
        reading = (SensorReading.objects
                   .filter(sensor_type=metric_key, collected_at__gte=cutoff)
                   .order_by('-collected_at').first())
        return reading.value if reading and reading.value is not None else None

    if source == 'business_metric':
        from apps.orion_ops.models import BusinessMetricReading
        reading = (BusinessMetricReading.objects
                   .filter(metric_type=metric_key, collected_at__gte=cutoff)
                   .order_by('-collected_at').first())
        return reading.value if reading else None

    if source == 'slo':
        from apps.orion_ops.models import SLOTarget
        try:
            slo = SLOTarget.objects.get(slug=metric_key, enabled=True)
            return slo.current_value
        except SLOTarget.DoesNotExist:
            return None

    if source == 'data_quality':
        # metric_key peut être 'open_critical', 'open_high', 'total_open'
        from apps.orion_ops.models import DataQualityAnomaly
        qs = DataQualityAnomaly.objects.filter(status__in=['open', 'acknowledged', 'fixing'])
        if metric_key == 'open_critical':
            return float(qs.filter(severity='critical').count())
        if metric_key == 'open_high':
            return float(qs.filter(severity='high').count())
        return float(qs.count())

    return None


# ─── Exécution des actions ────────────────────────────────────────────────────

def _execute_actions(rule, current_value: float) -> None:
    """Exécute les actions configurées sur la règle. Ne lève pas d'exception."""
    actions = rule.actions or []
    label = f'[{rule.severity.upper()}] {rule.name}'
    message = (f'Règle "{rule.name}" déclenchée — '
               f'valeur actuelle : {current_value} '
               f'{rule.get_operator_display()} {rule.threshold}')

    if 'create_alert' in actions or 'create_incident' in actions:
        _create_system_error(rule, label, message, current_value)

    if 'create_incident' in actions:
        _create_incident(rule, label, message)

    if 'notify_superusers' in actions:
        _notify_superusers(rule, message)

    if 'notify_team' in actions and rule.notify_users:
        _notify_users(rule, message)

    if 'webhook' in actions and rule.webhook_url:
        _call_webhook(rule, current_value)


def _create_system_error(rule, label: str, message: str, value: float) -> None:
    try:
        from apps.system_health.models import SystemError
        SystemError.objects.get_or_create(
            code=f'RULE_{rule.pk}',
            status__in=['new', 'analysed'],
            defaults={
                'code': f'RULE_{rule.pk}',
                'message': f'{label} — {message}',
                'source': 'rule_engine',
                'severity': rule.severity,
                'status': 'new',
                'context': {'rule_id': rule.pk, 'current_value': value,
                            'threshold': rule.threshold, 'operator': rule.operator},
            },
        )
    except Exception as e:
        logger.warning('rule_engine: create_system_error failed for rule %s: %s', rule.pk, e)


def _create_incident(rule, label: str, message: str) -> None:
    try:
        from apps.system_health.models import SystemIncident
        from django.utils import timezone as _tz
        SEVERITY_MAP = {'info': 'minor', 'warning': 'major',
                        'critical': 'critical', 'emergency': 'emergency'}
        existing = SystemIncident.objects.filter(
            title__startswith=label,
            status__in=['detected', 'confirmed', 'assigned', 'investigating', 'fixing'],
        ).exists()
        if not existing:
            SystemIncident.objects.create(
                title=label,
                description=message,
                severity=SEVERITY_MAP.get(rule.severity, 'major'),
                status='detected',
                auto_created=True,
                component='rule_engine',
                started_at=_tz.now(),
            )
    except Exception as e:
        logger.warning('rule_engine: create_incident failed for rule %s: %s', rule.pk, e)


def _notify_superusers(rule, message: str) -> None:
    try:
        from django.contrib.auth.models import User
        from apps.notifications.models import Notification
        superusers = User.objects.filter(is_superuser=True, is_active=True)
        for user in superusers:
            Notification.objects.create(
                user=user,
                title=f'Alerte : {rule.name}',
                message=message,
                notification_type='warning',
                priority=rule.severity,
                source_module='orion_ops',
            )
    except Exception as e:
        logger.warning('rule_engine: notify_superusers failed for rule %s: %s', rule.pk, e)


def _notify_users(rule, message: str) -> None:
    try:
        from django.contrib.auth.models import User
        from apps.notifications.models import Notification
        users = User.objects.filter(pk__in=rule.notify_users, is_active=True)
        for user in users:
            Notification.objects.create(
                user=user,
                title=f'Alerte : {rule.name}',
                message=message,
                notification_type='warning',
                priority=rule.severity,
                source_module='orion_ops',
            )
    except Exception as e:
        logger.warning('rule_engine: notify_users failed for rule %s: %s', rule.pk, e)


def _call_webhook(rule, current_value: float) -> None:
    try:
        import urllib.request
        import json as _json
        payload = _json.dumps({
            'rule': rule.name,
            'severity': rule.severity,
            'current_value': current_value,
            'threshold': rule.threshold,
            'operator': rule.operator,
            'triggered_at': timezone.now().isoformat(),
        }).encode()
        req = urllib.request.Request(
            rule.webhook_url,
            data=payload,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        logger.warning('rule_engine: webhook call failed for rule %s: %s', rule.pk, e)


# ─── Évaluation principale ────────────────────────────────────────────────────

def evaluate_all_rules() -> dict:
    """
    Évalue toutes les règles d'alerte actives.
    Retourne un résumé {triggered: int, skipped: int, errors: int}.
    """
    from apps.orion_ops.models import AlertRule

    rules = AlertRule.objects.filter(enabled=True)
    triggered = 0
    skipped = 0
    errors = 0
    now = timezone.now()

    for rule in rules:
        try:
            # Règle silencieuse
            if rule.is_silenced():
                skipped += 1
                continue

            # Anti-spam : ne déclenche pas si déjà déclenché dans la fenêtre frequency_min
            if rule.last_triggered is not None:
                next_allowed = rule.last_triggered + timedelta(minutes=rule.frequency_min)
                if now < next_allowed:
                    skipped += 1
                    continue

            current_value = _get_current_value(rule.source, rule.metric_key)
            if current_value is None:
                # Pas de données disponibles — marquer et passer
                if rule.last_status != 'no_data':
                    rule.last_status = 'no_data'
                    rule.save(update_fields=['last_status'])
                skipped += 1
                continue

            condition_met = _evaluate_condition(current_value, rule.operator, rule.threshold)

            if condition_met:
                _execute_actions(rule, current_value)
                rule.last_triggered = now
                rule.trigger_count += 1
                rule.last_status = 'triggered'
                rule.save(update_fields=['last_triggered', 'trigger_count', 'last_status', 'updated_at'])
                triggered += 1
                logger.info('rule_engine: triggered rule "%s" (value=%.3f %s %.3f)',
                            rule.name, current_value, rule.operator, rule.threshold)
            else:
                if rule.last_status != 'ok':
                    rule.last_status = 'ok'
                    rule.save(update_fields=['last_status', 'updated_at'])

        except Exception as e:
            logger.error('rule_engine: error evaluating rule %s: %s', getattr(rule, 'pk', '?'), e)
            errors += 1

    return {'triggered': triggered, 'skipped': skipped, 'errors': errors, 'total': rules.count()}
