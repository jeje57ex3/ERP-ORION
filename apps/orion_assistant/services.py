from django.utils import timezone
from django.conf import settings as dj_settings

from .models import AssistantConversation, AssistantMessage


def start_conversation(company, user, title='', context_module=''):
    return AssistantConversation.objects.create(
        company=company, user=user,
        title=title, context_module=context_module,
    )


def add_message(conversation, role, content, tokens_used=0, metadata=None):
    msg = AssistantMessage.objects.create(
        conversation=conversation, role=role,
        content=content, tokens_used=tokens_used,
        metadata=metadata or {},
    )
    conversation.updated_at = timezone.now()
    conversation.save(update_fields=['updated_at'])
    return msg


def get_conversation_history(conversation, limit=50):
    return conversation.messages.order_by('created_at')[:limit]


def get_user_conversations(company, user, include_archived=False):
    qs = AssistantConversation.objects.filter(company=company, user=user)
    if not include_archived:
        qs = qs.filter(is_archived=False)
    return qs.order_by('-updated_at')


def archive_conversation(conversation):
    conversation.is_archived = True
    conversation.save(update_fields=['is_archived'])
    return conversation


def build_context_prompt(company, context_module=''):
    """Builds a system prompt with company context for the AI."""
    lines = [
        f"Tu es Orion, l'assistant IA de l'ERP Orion pour l'entreprise « {company.name} ».",
        "Tu aides les utilisateurs avec leurs tâches ERP : ventes, comptabilité, RH, projets, etc.",
        "Réponds toujours en français. Sois concis et professionnel.",
    ]
    if context_module:
        lines.append(f"Le contexte actuel est le module : {context_module}.")
    return '\n'.join(lines)


def generate_ai_reply(conversation, user_message):
    if not getattr(dj_settings, 'ORION_AI_ENABLED', False):
        return {
            'content': (
                "L'assistant IA n'est pas activé. "
                "Ajoutez ORION_AI_ENABLED=True et une clé API dans votre fichier .env, "
                "puis redémarrez le serveur."
            ),
            'tokens': 0,
        }

    try:
        from apps.orion_ai.models import OrionAISettings
        from apps.orion_ai.providers import get_ai_provider, AIProviderError
        from apps.orion_ai.prompts import build_system_prompt
        from apps.orion_ai.safety import redact_sensitive_text, redact_payload

        ai_settings = OrionAISettings.get_for_company(conversation.company)

        if not ai_settings.ai_enabled:
            return {'content': "L'assistant IA est désactivé par l'administrateur.", 'tokens': 0}

        system_prompt = build_system_prompt(ai_settings, company=conversation.company)

        messages = [{'role': 'system', 'content': system_prompt}]

        history = list(
            conversation.messages
            .exclude(role='system')
            .order_by('created_at')
        )
        for msg in history[-(ai_settings.max_history_messages):]:
            if msg.role in ('user', 'assistant'):
                messages.append({'role': msg.role, 'content': msg.content})

        messages.append({'role': 'user', 'content': user_message})

        provider = get_ai_provider(ai_settings.default_provider)
        response = provider.generate(
            messages=messages,
            model=ai_settings.default_model,
            temperature=ai_settings.temperature,
        )

        content = redact_sensitive_text(response['content'])
        tokens = response.get('token_input', 0) + response.get('token_output', 0)

        return {'content': content, 'tokens': tokens}

    except Exception as exc:
        return {
            'content': f"Erreur de l'assistant IA : {exc}",
            'tokens': 0,
        }


def get_assistant_stats(company):
    convs = AssistantConversation.objects.filter(company=company)
    msgs = AssistantMessage.objects.filter(conversation__company=company)
    return {
        'total_conversations': convs.count(),
        'active_conversations': convs.filter(is_archived=False).count(),
        'total_messages': msgs.count(),
        'total_tokens': msgs.aggregate(
            t=__import__('django.db.models', fromlist=['Sum']).Sum('tokens_used')
        )['t'] or 0,
    }
