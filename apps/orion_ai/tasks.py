import logging

logger = logging.getLogger(__name__)


def cleanup_old_ai_conversations(days=90):
    from django.utils import timezone
    from datetime import timedelta
    from apps.orion_ai.models import OrionAIConversation

    cutoff = timezone.now() - timedelta(days=days)
    old = OrionAIConversation.objects.filter(
        status='active',
        updated_at__lt=cutoff,
    )
    count = old.update(status='archived')
    logger.info(f'orion_ai: {count} conversations archivées (> {days} jours)')
    return count


def cleanup_old_ai_audit_logs(days=180):
    from django.utils import timezone
    from datetime import timedelta
    from apps.orion_ai.models import OrionAIAuditLog

    cutoff = timezone.now() - timedelta(days=days)
    deleted, _ = OrionAIAuditLog.objects.filter(created_at__lt=cutoff).delete()
    logger.info(f'orion_ai: {deleted} logs audit supprimés (> {days} jours)')
    return deleted
