from django.db import transaction
from django.utils import timezone

from apps.orion_ai.models import OrionAIProposedAction
from apps.orion_ai.permissions import (
    can_execute_ai_write_actions,
    can_execute_dangerous_ai_actions,
)
from apps.orion_ai.tool_registry import get_ai_tool
from apps.orion_ai.services import audit_ai_event
from apps.orion_ai.safety import redact_payload


@transaction.atomic
def confirm_and_execute_action(*, action, user, request=None):
    if action.status != 'pending':
        raise RuntimeError("Cette action n'est plus en attente.")

    if action.is_write_action and not can_execute_ai_write_actions(user):
        raise PermissionError("Vous ne pouvez pas exécuter cette action IA.")

    if action.is_dangerous_action and not can_execute_dangerous_ai_actions(user):
        raise PermissionError("Vous ne pouvez pas exécuter une action IA dangereuse.")

    tool = get_ai_tool(action.action_code)
    if not tool:
        raise RuntimeError(f'Outil/action introuvable : {action.action_code}')

    action.status = 'confirmed'
    action.confirmed_by = user
    action.confirmed_at = timezone.now()
    action.save(update_fields=['status', 'confirmed_by', 'confirmed_at'])

    try:
        result = tool['func'](
            company=action.conversation.company,
            user=user,
            **action.arguments,
        )

        action.status = 'executed'
        action.executed_at = timezone.now()
        action.result = redact_payload(result)
        action.save(update_fields=['status', 'executed_at', 'result'])

        audit_ai_event(
            company=action.conversation.company,
            user=user,
            event_type='action_executed',
            title=f'Action IA exécutée : {action.title}',
            payload={
                'action_id': action.id,
                'action_code': action.action_code,
                'result': redact_payload(result),
            },
            request=request,
        )

        return action

    except Exception as exc:
        action.status = 'failed'
        action.error_message = str(exc)
        action.save(update_fields=['status', 'error_message'])
        raise


def cancel_ai_action(*, action, user, request=None):
    if action.status != 'pending':
        raise RuntimeError("Cette action ne peut plus être annulée.")

    action.status = 'cancelled'
    action.save(update_fields=['status'])

    audit_ai_event(
        company=action.conversation.company,
        user=user,
        event_type='action_blocked',
        title=f'Action IA annulée : {action.title}',
        payload={
            'action_id': action.id,
            'action_code': action.action_code,
        },
        request=request,
    )

    return action
