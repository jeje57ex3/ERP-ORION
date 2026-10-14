"""Bascule automatique, sous condition de majorité.

Cette fonction décidait auparavant sur la seule vue du serveur qui l'exécute :
« le serveur actif est périmé, donc je prends la main ». Ce raisonnement est
juste quand le principal est tombé, et faux quand c'est le réseau qui s'est
coupé — or le serveur isolé ne peut pas distinguer les deux cas, qui lui
apparaissent de la même façon.

Lors d'une partition, chaque serveur isolé tenait donc ce raisonnement en même
temps. Deux serveurs actifs, deux bases acceptant des écritures, aucune
réconciliation automatique possible : des devis et des factures différents
portant les mêmes numéros. C'est pour cela que la bascule automatique est
restée délibérément inopérante jusqu'ici, et qu'elle passe désormais par une
élection (voir election.py).

Deux autres défauts corrigés au même endroit :

- `select_best_failover_target()` était appelé sans `automatic=True`, si bien
  que le drapeau `allow_auto_failover` de chaque serveur — la case « ce
  serveur peut-il être promu sans intervention humaine » — n'était pas
  consulté. Un serveur explicitement exclu pouvait être choisi.
- un refus n'était jamais journalisé. Une bascule automatique qui ne se
  produit pas, sans que rien ne dise pourquoi, est aussi gênante qu'une
  bascule à tort : on ne sait pas si le mécanisme a jugé, ou s'il dort.
"""

import logging

from apps.high_availability.election import conduire_election
from apps.high_availability.failover import run_manual_failover_to_node
from apps.high_availability.models import OrionHAFailoverEvent, OrionHASettings
from apps.high_availability.services import (
    get_active_node,
    select_best_failover_target,
)

logger = logging.getLogger(__name__)


def _journaliser_refus(raison, candidat=None, compte_rendu=None):
    """Garde la trace d'une bascule automatique envisagée puis écartée.

    Sans cette trace, la seule façon de savoir si le mécanisme a jugé est de
    constater, après coup, qu'il n'a rien fait — ce qui ne distingue pas un
    refus raisonné d'une panne du mécanisme lui-même.
    """
    details = raison
    if compte_rendu:
        details = '%s\n\nVoix : %s/%s (requis %s), époque %s.' % (
            raison,
            compte_rendu.get('voix'),
            compte_rendu.get('total_serveurs'),
            compte_rendu.get('voix_requises'),
            compte_rendu.get('epoque'),
        )
        for detail in compte_rendu.get('details', []):
            details += '\n  - %s : %s %s' % (
                detail.get('serveur'),
                'pour' if detail.get('accordee') else 'contre',
                detail.get('raison') or '',
            )

    try:
        OrionHAFailoverEvent.objects.create(
            event_type='automatic_failover',
            status='refused',
            # Le champ s'appelle to_node, et non target_node : ce dernier est
            # le nom du PARAMÈTRE de run_manual_failover_to_node. L'erreur
            # était invisible, un « except Exception: pass » l'avalant --
            # aucun refus n'était journalisé, et la seule trace du mécanisme
            # disparaissait silencieusement.
            to_node=candidat,
            reason=details[:2000],
        )
    except Exception:
        # La journalisation ne doit jamais empêcher la décision elle-même.
        # Mais elle ne doit pas non plus se taire : un défaut avalé ici a
        # déjà masqué une erreur de nom de champ, et rendu le mécanisme muet.
        logger.exception('Journalisation du refus de bascule impossible.')


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

    # `automatic=True` : seuls les serveurs dont l'exploitant a autorisé la
    # promotion sans intervention humaine sont candidats.
    target = select_best_failover_target(automatic=True)
    if not target:
        raison = (
            'Aucun serveur éligible à une promotion automatique : vérifiez '
            '« bascule automatique autorisée » sur les serveurs secondaires, '
            'leur état de santé et leur retard de réplication.'
        )
        _journaliser_refus(raison)
        return {'skipped': True, 'reason': raison}

    # L'arbitrage. C'est ici que se joue la différence entre une bascule et
    # une divergence.
    compte_rendu = conduire_election(target, primaire_injoignable=True)
    if not compte_rendu['elu']:
        _journaliser_refus(compte_rendu['raison'], target, compte_rendu)
        return {
            'skipped': True,
            'reason': compte_rendu['raison'],
            'election': compte_rendu,
        }

    event = run_manual_failover_to_node(
        target_node=target,
        started_by=None,
        reason=(
            'Failover automatique : serveur actif indisponible. %s'
            % compte_rendu['raison']
        ),
    )
    return {
        'ok': True,
        'event_id': event.id,
        'target_node': target.node_id,
        'election': compte_rendu,
    }
