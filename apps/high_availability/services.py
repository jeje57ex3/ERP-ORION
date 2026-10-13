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


ETATS_SAINS = ('healthy', 'passive', 'warning', 'active')


def update_node_from_health(node, payload):
    node.status = payload.get('status', 'unknown')
    node.last_heartbeat_at = timezone.now()
    node.last_health_payload = payload
    node.database_status = payload.get('database', node.database_status)
    node.database_role = payload.get('database_role', node.database_role)
    node.replication_lag_seconds = payload.get('replication_lag_seconds')
    node.app_version = payload.get('app_version', node.app_version)
    node.git_commit = payload.get('git_commit', node.git_commit)

    # Horodate le DÉBUT du bon état courant, sans l'écraser aux bilans
    # suivants : c'est la durée de stabilité, pas la fraîcheur du dernier
    # battement, qui autorise un retour de la main.
    if node.status in ETATS_SAINS:
        if not node.healthy_since:
            node.healthy_since = timezone.now()
    else:
        node.healthy_since = None

    node.save()
    return node


def check_node_health(node):
    try:
        payload = fetch_node_health(node)
        update_node_from_health(node, payload)
        return {'node': node, 'ok': True, 'payload': payload}
    except Exception as exc:
        node.status = 'down'
        # La stabilité repart de zéro : sans cette remise à zéro, un serveur
        # qui oscille accumulerait une ancienneté qu'il n'a jamais eue.
        node.healthy_since = None
        node.save(update_fields=['status', 'healthy_since', 'updated_at'])
        return {'node': node, 'ok': False, 'error': str(exc)}


def check_all_ha_nodes(apply_failback=True):
    """Interroge tous les serveurs, puis applique la règle de retour.

    C'est ici que « quand un serveur revient » se joue : le balayage de santé
    est le seul moment où l'on constate qu'un serveur tombé répond de nouveau.

    Le parcours suit l'ordre du modèle (`priority`, puis nom), donc le serveur
    le mieux classé est examiné le premier — ce qui rend le résultat
    déterministe quand plusieurs revenants sont mieux classés que l'actif.

    Sous la politique par défaut (« manuel »), rien n'est décidé ici : la
    règle se contente de proposer.
    """
    results = []
    for node in OrionHANode.objects.filter(is_enabled=True):
        results.append(check_node_health(node))

    # Import tardif : takeover importe failover, qui importe ce module.
    from apps.high_availability.takeover import evaluate_returning_node

    for resultat in results:
        if not resultat['ok']:
            continue
        try:
            resultat['takeover'] = evaluate_returning_node(
                resultat['node'], apply=apply_failback,
            )
        except Exception as exc:
            # Un retour de main refusé ne doit pas faire échouer la
            # surveillance : le reste du bilan garde sa valeur.
            resultat['takeover'] = {'error': str(exc)}

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


def select_best_failover_target(automatic=False):
    """Serveur qui prend le dessus, dans l'ordre de préséance.

    `automatic=True` écarte en plus les serveurs dont la promotion automatique
    est interdite. Ce drapeau existait sur le modèle sans être lu nulle part :
    le décocher ne protégeait de rien.
    """
    settings_obj = OrionHASettings.get_solo()

    def acceptable(node):
        if not node.can_be_failover_target:
            return False
        if automatic and not node.allow_auto_failover:
            return False
        lag = node.replication_lag_seconds
        return lag is None or lag <= settings_obj.max_allowed_replication_lag_seconds

    preferred = settings_obj.preferred_secondary_node
    if preferred and acceptable(preferred):
        return preferred

    for node in get_failover_candidates():
        if acceptable(node):
            return node

    return None


@transaction.atomic
def set_active_node(node, lock_token=''):
    """Donne la main à `node` et RÉTROGRADE tous les autres.

    La rétrogradation n'était pas faite : le nouveau serveur prenait le rôle
    « principal » sans que l'ancien le perde. Après une seule bascule, deux
    serveurs portaient donc le rôle principal, et l'ancien se retrouvait
    définitivement exclu — `can_be_failover_target` et
    `get_failover_candidates()` exigent tous deux le rôle « secondaire ».
    Autrement dit, le retour d'un serveur était structurellement impossible,
    indépendamment de toute politique.

    Un serveur rétrogradé devient par conséquent éligible à recevoir la main :
    il l'a déjà portée, rien ne justifie de l'écarter. Son rang de préséance,
    lui, ne change pas — c'est ce qui le désigne pour la reprendre.
    """
    OrionHANode.objects.select_for_update().all()

    for autre in OrionHANode.objects.exclude(pk=node.pk):
        champs = ['is_current_active', 'updated_at']
        autre.is_current_active = False
        if autre.role == 'primary':
            autre.role = 'secondary'
            autre.is_failover_target = True
            champs += ['role', 'is_failover_target']
        # Un serveur injoignable reste « hors ligne » : le repasser en
        # « passif » laisserait croire qu'il est disponible.
        if autre.status == 'active':
            autre.status = 'passive'
            champs.append('status')
        autre.save(update_fields=champs)

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
