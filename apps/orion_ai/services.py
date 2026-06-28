from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.orion_ai.memory import get_memory_context
from apps.orion_ai.models import (
    OrionAIAuditLog,
    OrionAIConversation,
    OrionAIMessage,
    OrionAIProposedAction,
    OrionAISettings,
    OrionAIToolCall,
)
from apps.orion_ai.permissions import can_use_ai
from apps.orion_ai.prompts import build_system_prompt
from apps.orion_ai.providers import get_ai_provider, AIProviderError
from apps.orion_ai.safety import (
    is_dangerous_action,
    is_write_action,
    redact_payload,
    redact_sensitive_text,
    validate_user_prompt,
)
from apps.orion_ai.tool_registry import get_ai_tool


def get_request_company(request):
    return getattr(request, 'active_company', None) or getattr(request, 'company', None)


def get_ai_settings(company=None):
    if company:
        return OrionAISettings.get_for_company(company)
    return OrionAISettings.get_global()


def audit_ai_event(*, company, user, event_type, title, description='', payload=None, request=None):
    payload = redact_payload(payload or {})
    OrionAIAuditLog.objects.create(
        company=company,
        user=user,
        event_type=event_type,
        title=title,
        description=description,
        payload=payload,
        ip_address=request.META.get('REMOTE_ADDR') if request else None,
        user_agent=request.META.get('HTTP_USER_AGENT', '') if request else '',
    )


def build_messages_for_provider(conversation, ai_settings, user_message, company=None, user=None, brand_key=''):
    system_prompt = build_system_prompt(ai_settings, user=user, company=company)

    memory_context = get_memory_context(
        company=company,
        user=user,
        brand_key=brand_key,
    )
    if memory_context:
        system_prompt += '\n\n' + memory_context

    messages = [{'role': 'system', 'content': system_prompt}]

    history = list(
        conversation.messages
        .exclude(role='system')
        .order_by('-created_at')[:ai_settings.max_history_messages]
    )
    history = list(reversed(history))

    for msg in history:
        if msg.role in ('user', 'assistant'):
            messages.append({'role': msg.role, 'content': msg.content})

    messages.append({'role': 'user', 'content': user_message})

    return messages


def create_or_get_conversation(*, company, user, conversation_id=None, title='Nouvelle conversation', context_module='', brand_key=''):
    if conversation_id:
        return OrionAIConversation.objects.get(
            id=conversation_id,
            company=company,
            user=user,
        )
    return OrionAIConversation.objects.create(
        company=company,
        user=user,
        title=title,
        context_module=context_module,
        brand_key=brand_key,
    )


@transaction.atomic
def send_ai_message(*, request, prompt, conversation_id=None, context_module='', brand_key=''):
    user = request.user
    company = get_request_company(request)

    if not can_use_ai(user):
        raise PermissionError("Vous n'avez pas accès à l'assistant IA.")

    ai_settings = get_ai_settings(company)

    if not ai_settings.ai_enabled or not getattr(settings, 'ORION_AI_ENABLED', False):
        raise RuntimeError("L'assistant IA est désactivé. Activez ORION_AI_ENABLED dans la configuration.")

    valid, error_message = validate_user_prompt(prompt)
    if not valid:
        raise ValueError(error_message)

    if len(prompt) > ai_settings.max_input_chars:
        raise ValueError(f'Message trop long (max {ai_settings.max_input_chars} caractères).')

    clean_prompt = redact_sensitive_text(prompt) if ai_settings.redact_sensitive_data else prompt

    conversation = create_or_get_conversation(
        company=company,
        user=user,
        conversation_id=conversation_id,
        context_module=context_module,
        brand_key=brand_key,
    )

    OrionAIMessage.objects.create(
        conversation=conversation,
        role='user',
        content=clean_prompt,
    )

    messages = build_messages_for_provider(
        conversation,
        ai_settings,
        clean_prompt,
        company=company,
        user=user,
        brand_key=brand_key,
    )

    provider = get_ai_provider(ai_settings.default_provider)

    response = provider.generate(
        messages=messages,
        model=ai_settings.default_model,
        temperature=ai_settings.temperature,
    )

    assistant_content = redact_sensitive_text(response['content'])

    assistant_msg = OrionAIMessage.objects.create(
        conversation=conversation,
        role='assistant',
        content=assistant_content,
        provider=response['provider'],
        model=response['model'],
        token_input=response.get('token_input', 0),
        token_output=response.get('token_output', 0),
        raw_payload=redact_payload(response.get('raw', {})),
    )

    update_fields = ['updated_at']
    if conversation.title == 'Nouvelle conversation':
        conversation.title = clean_prompt[:80]
        update_fields.append('title')
    conversation.updated_at = timezone.now()
    conversation.save(update_fields=update_fields)

    if ai_settings.log_conversations:
        audit_ai_event(
            company=company,
            user=user,
            event_type='chat_message',
            title='Message IA',
            description=clean_prompt[:220],
            payload={
                'conversation_id': conversation.id,
                'provider': response['provider'],
                'model': response['model'],
            },
            request=request,
        )

    return {
        'conversation_id': conversation.id,
        'message_id': assistant_msg.id,
        'answer': assistant_msg.content,
        'provider': response['provider'],
        'model': response['model'],
    }


def propose_ai_action(*, conversation, title, description, action_code, arguments):
    action = OrionAIProposedAction.objects.create(
        conversation=conversation,
        title=title,
        description=description,
        action_code=action_code,
        arguments=redact_payload(arguments),
        is_write_action=is_write_action(action_code),
        is_dangerous_action=is_dangerous_action(action_code),
        requires_confirmation=True,
    )

    audit_ai_event(
        company=conversation.company,
        user=conversation.user,
        event_type='action_proposed',
        title=f'Action proposée : {title}',
        payload={'action_id': action.id, 'action_code': action_code},
    )

    return action


@transaction.atomic
def execute_ai_read_tool(*, conversation, user, tool_name, arguments):
    tool = get_ai_tool(tool_name)

    if not tool:
        raise RuntimeError(f'Outil IA inconnu : {tool_name}')

    if tool['is_write_action']:
        raise RuntimeError("Les outils d'écriture doivent passer par une action confirmée.")

    company = conversation.company

    tool_call = OrionAIToolCall.objects.create(
        conversation=conversation,
        tool_name=tool_name,
        arguments=redact_payload(arguments),
        status='running',
        is_write_action=False,
        is_dangerous_action=False,
        executed_by=user,
    )

    try:
        result = tool['func'](company=company, user=user, **arguments)
        tool_call.status = 'success'
        tool_call.result = redact_payload(result)
        tool_call.finished_at = timezone.now()
        tool_call.save()
        return result
    except Exception as exc:
        tool_call.status = 'failed'
        tool_call.error_message = str(exc)
        tool_call.finished_at = timezone.now()
        tool_call.save()
        raise
