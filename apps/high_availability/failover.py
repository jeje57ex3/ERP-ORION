from django.db import connection, transaction
from django.utils import timezone

from apps.high_availability.models import (
    OrionHANode,
    OrionHASettings,
    OrionHAFailoverEvent,
)
from apps.high_availability.services import set_active_node


def validate_failover_target(target_node):
    settings_obj = OrionHASettings.get_solo()

    if not settings_obj.failover_enabled:
        raise RuntimeError('Le failover est désactivé.')
    if not target_node.is_enabled:
        raise RuntimeError('Le serveur cible est désactivé.')
    if target_node.role != 'secondary':
        raise RuntimeError('Le serveur cible doit être un serveur secondaire.')
    if not target_node.is_failover_target:
        raise RuntimeError("Ce serveur n'est pas autorisé comme cible de failover.")
    if target_node.status not in ('healthy', 'passive', 'warning'):
        raise RuntimeError("Le serveur cible n'est pas prêt.")
    if target_node.priority == 3 and not settings_obj.allow_failover_to_secondary_2:
        raise RuntimeError('La bascule vers le secondaire 2 est désactivée.')

    lag = target_node.replication_lag_seconds
    if lag is not None and lag > settings_obj.max_allowed_replication_lag_seconds:
        raise RuntimeError(f'Réplication trop en retard : {lag}s.')

    return True


def _promote_database_to_primary():
    with connection.cursor() as cursor:
        for cmd in (
            'STOP SLAVE',
            'STOP REPLICA',
            'SET GLOBAL read_only = OFF',
            'SET GLOBAL super_read_only = OFF',
        ):
            try:
                cursor.execute(cmd)
            except Exception:
                pass


def _update_dns_or_cloudflare(target_node):
    settings_obj = OrionHASettings.get_solo()
    if not settings_obj.cloudflare_failover_enabled:
        return {'skipped': True, 'reason': 'Cloudflare failover disabled'}
    return {
        'todo': True,
        'message': 'Intégrer Cloudflare DNS update ici.',
        'target_node': target_node.node_id,
        'target_ip': str(target_node.public_ip) if target_node.public_ip else '',
    }


@transaction.atomic
def run_manual_failover_to_node(*, target_node, started_by=None, reason=''):
    current_active = OrionHANode.objects.filter(is_current_active=True).first()

    event = OrionHAFailoverEvent.objects.create(
        event_type='manual_failover',
        status='running',
        from_node=current_active,
        to_node=target_node,
        started_by=started_by,
        reason=reason,
        steps=[],
    )

    steps = []
    try:
        steps.append('Validation du serveur cible')
        validate_failover_target(target_node)

        steps.append('Promotion base de données')
        _promote_database_to_primary()

        steps.append('Mise à jour DNS / Cloudflare')
        dns_payload = _update_dns_or_cloudflare(target_node)

        steps.append('Marquage serveur actif')
        set_active_node(target_node)

        steps.append('Finalisation')
        event.status = 'success'
        event.steps = steps
        event.result_payload = {'dns': dns_payload}
        event.finished_at = timezone.now()
        event.save()
        return event

    except Exception as exc:
        event.status = 'failed'
        event.steps = steps
        event.error_message = str(exc)
        event.finished_at = timezone.now()
        event.save()
        raise
