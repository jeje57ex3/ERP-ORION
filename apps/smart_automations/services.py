"""
smart_automations/services.py
Moteur d'exécution des règles d'automatisation.
"""
from django.utils import timezone
from .models import AutomationRule, AutomationRun


ACTION_REGISTRY = {}


def register_action(code):
    """Décorateur pour enregistrer un gestionnaire d'action."""
    def decorator(fn):
        ACTION_REGISTRY[code] = fn
        return fn
    return decorator


@register_action('create_alert')
def _action_create_alert(company, payload, context):
    from apps.smart_alerts.services import create_alert
    return create_alert(
        company=company,
        title=payload.get('title', 'Alerte automatisation'),
        source_module='smart_automations',
        message=payload.get('message', ''),
        priority=payload.get('priority', 'normal'),
    )


@register_action('send_email')
def _action_send_email(company, payload, context):
    from django.core.mail import send_mail
    from django.conf import settings
    try:
        send_mail(
            subject=payload.get('subject', 'Notification Orion ERP'),
            message=payload.get('body', ''),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=payload.get('recipients', []),
            fail_silently=True,
        )
        return {'sent': True}
    except Exception as exc:
        return {'sent': False, 'error': str(exc)}


@register_action('notify_user')
def _action_notify_user(company, payload, context):
    return {'notified': True, 'user_id': payload.get('user_id')}


def _evaluate_conditions(conditions, context):
    """Évalue toutes les conditions. Retourne True si toutes passent."""
    for cond in conditions:
        field = cond.get('field', '')
        operator = cond.get('operator', 'eq')
        value = cond.get('value')
        actual = context.get(field)
        if operator == 'eq' and actual != value:
            return False
        elif operator == 'gt' and not (actual is not None and actual > value):
            return False
        elif operator == 'lt' and not (actual is not None and actual < value):
            return False
        elif operator == 'contains' and not (actual and str(value) in str(actual)):
            return False
    return True


def execute_rule(rule, trigger_payload=None, triggered_by=None):
    """Exécute une règle et crée un AutomationRun."""
    run = AutomationRun.objects.create(
        company=rule.company,
        rule=rule,
        status='running',
        trigger_payload=trigger_payload or {},
        triggered_by=triggered_by,
    )
    results = []
    try:
        context = trigger_payload or {}
        if not _evaluate_conditions(rule.conditions, context):
            run.status = 'skipped'
            run.result_payload = {'reason': 'conditions_not_met'}
            run.finished_at = timezone.now()
            run.save(update_fields=['status', 'result_payload', 'finished_at'])
            return run

        for action_def in rule.actions:
            action_code = action_def.get('type', '')
            handler = ACTION_REGISTRY.get(action_code)
            if handler:
                result = handler(rule.company, action_def.get('payload', {}), context)
                results.append({'action': action_code, 'result': str(result)})
            else:
                results.append({'action': action_code, 'result': 'unknown_action'})

        run.status = 'success'
        run.result_payload = {'actions': results}
    except Exception as exc:
        run.status = 'failed'
        run.error_message = str(exc)

    run.finished_at = timezone.now()
    run.save(update_fields=['status', 'result_payload', 'error_message', 'finished_at'])

    rule.last_run_at = timezone.now()
    rule.run_count += 1
    rule.save(update_fields=['last_run_at', 'run_count'])

    return run


def trigger_event(event_type, company, payload=None):
    """Déclenche toutes les règles actives liées à cet événement."""
    rules = AutomationRule.objects.filter(
        company=company, trigger_type=event_type, is_active=True
    )
    runs = []
    for rule in rules:
        run = execute_rule(rule, trigger_payload=payload or {})
        runs.append(run)
    return runs


def get_rule_stats(company):
    qs = AutomationRule.objects.filter(company=company)
    return {
        'total': qs.count(),
        'active': qs.filter(is_active=True).count(),
        'total_runs': AutomationRun.objects.filter(company=company).count(),
        'failed_runs': AutomationRun.objects.filter(company=company, status='failed').count(),
    }
