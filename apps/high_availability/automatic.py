from apps.high_availability.models import OrionHASettings
from apps.high_availability.services import get_active_node, select_best_failover_target
from apps.high_availability.failover import run_manual_failover_to_node


def check_and_run_automatic_failover():
    settings_obj = OrionHASettings.get_solo()

    if not settings_obj.failover_enabled:
        return {'skipped': True, 'reason': 'Failover disabled'}
    if not settings_obj.automatic_failover_enabled:
        return {'skipped': True, 'reason': 'Automatic failover disabled'}
    if settings_obj.require_manual_confirmation:
        return {'skipped': True, 'reason': 'Manual confirmation required'}

    active_node = get_active_node()
    if not active_node:
        return {'skipped': True, 'reason': 'No active node'}
    if not active_node.is_stale and active_node.status != 'down':
        return {'skipped': True, 'reason': 'Active node still healthy'}

    target = select_best_failover_target()
    if not target:
        return {'skipped': True, 'reason': 'No valid failover target'}

    event = run_manual_failover_to_node(
        target_node=target,
        started_by=None,
        reason='Failover automatique : serveur actif indisponible',
    )
    return {'ok': True, 'event_id': event.id, 'target_node': target.node_id}
