import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.high_availability.models import (
    OrionHANode,
    OrionHASettings,
    OrionHAClusterLock,
)


def seed_default_ha_nodes():
    nodes = [
        {
            'node_id': 'orion-primary',
            'name': 'Orion Principal',
            'role': 'primary',
            'priority': 1,
            'base_url': getattr(settings, 'ORION_PRIMARY_URL', ''),
            'is_current_active': True,
            'is_failover_target': False,
        },
        {
            'node_id': 'orion-secondary-1',
            'name': 'Orion Secondaire 1',
            'role': 'secondary',
            'priority': 2,
            'base_url': getattr(settings, 'ORION_SECONDARY_1_URL', ''),
            'is_current_active': False,
            'is_failover_target': True,
        },
        {
            'node_id': 'orion-secondary-2',
            'name': 'Orion Secondaire 2',
            'role': 'secondary',
            'priority': 3,
            'base_url': getattr(settings, 'ORION_SECONDARY_2_URL', ''),
            'is_current_active': False,
            'is_failover_target': True,
        },
    ]

    for node_data in nodes:
        OrionHANode.objects.update_or_create(
            node_id=node_data['node_id'],
            defaults=node_data,
        )

    settings_obj = OrionHASettings.get_solo()
    if not settings_obj.preferred_secondary_node:
        preferred = OrionHANode.objects.filter(node_id='orion-secondary-1').first()
        if preferred:
            settings_obj.preferred_secondary_node = preferred
            settings_obj.save(update_fields=['preferred_secondary_node', 'updated_at'])

    lock = OrionHAClusterLock.get_lock()
    lock.active_node_id = 'orion-primary'
    lock.save(update_fields=['active_node_id', 'updated_at'])


def fetch_node_health(node):
    if not node.base_url:
        raise RuntimeError('URL du serveur manquante.')
    response = requests.get(
        f"{node.base_url.rstrip('/')}/ha/health/",
        headers={'X-Orion-HA-Secret': getattr(settings, 'ORION_HA_SECRET', '')},
        timeout=8,
    )
    response.raise_for_status()
    return response.json()


def update_node_from_health(node, payload):
    node.status = payload.get('status', 'unknown')
    node.last_heartbeat_at = timezone.now()
    node.last_health_payload = payload
    node.database_status = payload.get('database', node.database_status)
    node.database_role = payload.get('database_role', node.database_role)
    node.replication_lag_seconds = payload.get('replication_lag_seconds')
    node.app_version = payload.get('app_version', node.app_version)
    node.git_commit = payload.get('git_commit', node.git_commit)
    node.save()
    return node


def check_node_health(node):
    try:
        payload = fetch_node_health(node)
        update_node_from_health(node, payload)
        return {'node': node, 'ok': True, 'payload': payload}
    except Exception as exc:
        node.status = 'down'
        node.save(update_fields=['status', 'updated_at'])
        return {'node': node, 'ok': False, 'error': str(exc)}


def check_all_ha_nodes():
    results = []
    for node in OrionHANode.objects.filter(is_enabled=True):
        results.append(check_node_health(node))
    return results


def get_active_node():
    return OrionHANode.objects.filter(is_current_active=True).first()


def get_failover_candidates():
    settings_obj = OrionHASettings.get_solo()
    qs = OrionHANode.objects.filter(
        role='secondary',
        is_enabled=True,
        is_failover_target=True,
    ).order_by('priority')
    if not settings_obj.allow_failover_to_secondary_2:
        qs = qs.filter(priority=2)
    return qs


def select_best_failover_target():
    settings_obj = OrionHASettings.get_solo()
    preferred = settings_obj.preferred_secondary_node

    if preferred and preferred.can_be_failover_target:
        lag = preferred.replication_lag_seconds
        if lag is None or lag <= settings_obj.max_allowed_replication_lag_seconds:
            return preferred

    for node in get_failover_candidates():
        if not node.can_be_failover_target:
            continue
        lag = node.replication_lag_seconds
        if lag is not None and lag > settings_obj.max_allowed_replication_lag_seconds:
            continue
        return node

    return None


@transaction.atomic
def set_active_node(node, lock_token=''):
    OrionHANode.objects.select_for_update().all()
    OrionHANode.objects.update(is_current_active=False)
    node.is_current_active = True
    node.status = 'active'
    node.role = 'primary'
    node.save()

    lock = OrionHAClusterLock.get_lock()
    lock.active_node_id = node.node_id
    lock.lock_token = lock_token
    lock.save(update_fields=['active_node_id', 'lock_token', 'updated_at'])
    return node


def count_healthy_secondaries():
    return OrionHANode.objects.filter(
        role='secondary',
        is_enabled=True,
        status__in=['healthy', 'passive', 'warning'],
    ).count()
