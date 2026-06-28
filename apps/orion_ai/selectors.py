from apps.orion_ai.models import (
    OrionAIAuditLog,
    OrionAIConversation,
    OrionAIMessage,
    OrionAIProposedAction,
    OrionAISettings,
    OrionAIMemory,
)


def get_ai_settings(company=None):
    if company:
        return OrionAISettings.get_for_company(company)
    return OrionAISettings.get_global()


def get_conversations(*, company, user, status='active', limit=50):
    return OrionAIConversation.objects.filter(
        company=company,
        user=user,
        status=status,
    )[:limit]


def get_conversation(*, pk, company, user):
    return OrionAIConversation.objects.get(id=pk, company=company, user=user)


def get_conversation_messages(conversation, limit=100):
    return conversation.messages.order_by('created_at')[:limit]


def get_pending_actions(*, company, user):
    return OrionAIProposedAction.objects.filter(
        conversation__company=company,
        conversation__user=user,
        status='pending',
    )


def get_audit_logs(*, company=None, user=None, limit=100):
    qs = OrionAIAuditLog.objects.all()
    if company:
        qs = qs.filter(company=company)
    if user:
        qs = qs.filter(user=user)
    return qs[:limit]


def get_memory_entries(*, company=None, user=None, scope=None):
    qs = OrionAIMemory.objects.filter(is_active=True)
    if company:
        qs = qs.filter(company=company)
    if user:
        qs = qs.filter(user=user)
    if scope:
        qs = qs.filter(scope=scope)
    return qs
