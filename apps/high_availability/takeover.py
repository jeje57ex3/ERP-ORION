"""Règles de préséance entre serveurs, et retour d'un serveur tombé.

Deux questions distinctes, longtemps mêlées dans le code :

1. **Qui prend le dessus** quand le serveur actif tombe ? Réponse donnée par
   le rang de préséance (`OrionHANode.priority`, 1 = le mieux classé), corrigé
   par le secondaire préféré des paramètres, et filtré par les autorisations
   de chaque serveur.

2. **Que se passe-t-il quand un serveur revient** ? Réponse donnée par la
   politique de retour (`OrionHASettings.failback_policy`). Sans règle, le
   serveur promu gardait la main indéfiniment et le rang de préséance ne
   servait plus à rien après la première bascule.

Le rang de préséance est volontairement indépendant du rôle courant : le rôle
se déplace à chaque bascule, la préséance est une décision d'exploitation.
C'est ce qui permet à un ancien principal rétrogradé de rester désigné pour
reprendre la main.
"""

from apps.high_availability.failover import run_manual_failover_to_node
from apps.high_availability.models import OrionHANode, OrionHASettings
from apps.high_availability.services import get_active_node

ETATS_DISPONIBLES = ('healthy', 'passive', 'warning')


def preferred_primary():
    """Serveur qui devrait porter le rôle principal en régime normal."""
    return (
        OrionHANode.objects
        .filter(is_enabled=True)
        .order_by('priority', 'node_id')
        .first()
    )


def precedence_order(automatic=False):
    """Ordre de préséance, avec pour chaque serveur s'il peut prendre la main.

    Rendu explicite à destination de l'exploitant : l'ordre était jusqu'ici
    enfoui dans `select_best_failover_target()`, qui renvoyait un serveur ou
    rien — sans jamais dire pourquoi les autres avaient été écartés.

    `automatic=True` applique en plus les restrictions propres à la
    surveillance, plus strictes que celles d'une bascule décidée à la main.
    """
    settings_obj = OrionHASettings.get_solo()
    actif = get_active_node()
    lag_max = settings_obj.max_allowed_replication_lag_seconds
    prefere = settings_obj.preferred_secondary_node

    lignes = []
    for node in OrionHANode.objects.order_by('priority', 'node_id'):
        est_actif = bool(actif and node.pk == actif.pk)
        obstacle = ''

        if est_actif:
            obstacle = 'Serveur actif'
        elif not node.is_enabled:
            obstacle = 'Désactivé'
        elif not node.is_failover_target:
            obstacle = 'Ne peut pas recevoir la main'
        elif automatic and not node.allow_auto_failover:
            obstacle = 'Promotion automatique interdite'
        elif node.role != 'secondary':
            obstacle = f'Rôle « {node.get_role_display()} »'
        elif node.status not in ETATS_DISPONIBLES:
            obstacle = f'État « {node.get_status_display()} »'
        elif node.replication_lag_seconds is not None and node.replication_lag_seconds > lag_max:
            obstacle = f'Réplication en retard de {node.replication_lag_seconds} s'

        lignes.append({
            'node': node,
            'is_active': est_actif,
            'eligible': obstacle == '' and not est_actif,
            'reason': obstacle or 'Peut prendre la main',
            'is_preferred': bool(prefere and node.pk == prefere.pk),
        })

    return lignes


def run_failback_to_node(*, target_node, started_by=None, reason=''):
    """Rend la main à un serveur revenu.

    Mécaniquement identique à une bascule — mêmes validations, même promotion,
    même redirection du trafic — mais tracée comme un retour, pour qu'une
    bascule subie se distingue d'un retour à la normale dans l'audit.
    """
    return run_manual_failover_to_node(
        target_node=target_node,
        started_by=started_by,
        reason=reason or 'Retour de la main au serveur mieux classé',
        event_type='manual_failback',
    )


def evaluate_returning_node(node, started_by=None, apply=True):
    """Applique la politique de retour à un serveur redevenu joignable.

    Ne rend jamais la main de sa propre initiative sous la politique
    « manuel » : elle se contente de proposer (`proposed`), à charge pour
    l'interface de le signaler. Seule la politique « automatique » agit, et
    seulement si toutes les garanties ci-dessous sont réunies.
    """
    settings_obj = OrionHASettings.get_solo()
    actif = get_active_node()

    decision = {
        'node': node.node_id,
        'policy': settings_obj.failback_policy,
        'failback': False,
        'proposed': False,
        'split_brain_suspected': False,
        'reason': '',
    }

    # Avant toute politique : un revenant qui se dit inscriptible sans avoir la
    # main est un début de divergence. Deux bases acceptant des écritures ne se
    # fusionnent pas — il faut arrêter là et alerter, jamais basculer.
    if actif and node.pk != actif.pk and node.claims_to_be_writable:
        decision['split_brain_suspected'] = True
        decision['reason'] = (
            f'Le serveur « {node.node_id} » accepte les écritures alors que la '
            f'main est à « {actif.node_id} ». Repassez sa base en lecture seule '
            'avant toute opération : deux bases divergentes ne se fusionnent pas.'
        )
        return decision

    if not actif:
        decision['reason'] = (
            'Aucun serveur actif : il ne s\'agit pas d\'un retour mais d\'une '
            'bascule ordinaire.'
        )
        return decision

    if node.pk == actif.pk:
        decision['reason'] = 'Ce serveur a déjà la main.'
        return decision

    if not settings_obj.failover_enabled:
        decision['reason'] = 'La bascule est désactivée dans les paramètres.'
        return decision

    if settings_obj.failback_policy == 'never':
        decision['reason'] = (
            f'Politique « jamais » : « {actif.node_id} » garde la main.'
        )
        return decision

    # Le rang décide, pas l'ordre d'arrivée. Un classement égal ne rend pas la
    # main : sans cette stricte inégalité, deux serveurs de même rang se la
    # reprendraient en boucle.
    if node.priority >= actif.priority:
        decision['reason'] = (
            f'Rang {node.priority}, moins bien classé que le serveur actif '
            f'(rang {actif.priority}) : il reste secondaire.'
        )
        return decision

    if not node.can_be_failover_target:
        decision['reason'] = (
            'Mieux classé, mais pas en mesure de reprendre la main '
            f'(état « {node.get_status_display()} », autorisations).'
        )
        return decision

    stable = node.stable_healthy_seconds
    exige = settings_obj.failback_min_stable_seconds
    if stable is None or stable < exige:
        decision['reason'] = (
            f'Mieux classé, mais stable depuis {stable if stable is not None else 0} s '
            f'seulement sur les {exige} s exigées.'
        )
        return decision

    lag = node.replication_lag_seconds
    if lag is not None and lag > settings_obj.max_allowed_replication_lag_seconds:
        decision['reason'] = (
            f'Mieux classé et stable, mais sa réplication a {lag} s de retard.'
        )
        return decision

    if settings_obj.failback_policy == 'manual':
        decision['proposed'] = True
        decision['reason'] = (
            f'« {node.node_id} » est prêt à reprendre la main (rang '
            f'{node.priority} contre {actif.priority}). En attente de '
            "confirmation d'un administrateur."
        )
        return decision

    decision['reason'] = (
        f'Retour automatique de la main à « {node.node_id} » (rang '
        f'{node.priority} contre {actif.priority}, stable depuis {stable} s).'
    )
    if not apply:
        decision['failback'] = True
        return decision

    event = run_failback_to_node(
        target_node=node,
        started_by=started_by,
        reason=decision['reason'],
    )
    decision['failback'] = True
    decision['event_id'] = event.id
    return decision
