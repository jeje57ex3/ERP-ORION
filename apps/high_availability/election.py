"""Arbitrage de la bascule automatique : élection par quorum.

Le problème que ce module résout
--------------------------------

La bascule automatique décidait sur la seule vue du serveur qui l'exécute :
« je ne joins plus le principal, donc je prends la main ». Ce raisonnement est
juste quand le principal est réellement tombé, et faux quand c'est le réseau
qui s'est coupé — cas que le serveur isolé ne peut pas distinguer du premier,
puisque les deux lui apparaissent de la même façon.

Lors d'une partition, chaque serveur tient donc ce raisonnement en même temps.
Deux serveurs se croient actifs, deux bases acceptent des écritures, et aucune
réconciliation automatique ne pourra les fusionner : des devis, des factures et
des pointages différents portant les mêmes numéros. C'est la divergence
(split-brain), et elle est bien pire qu'une panne — une panne s'attend, une
divergence se répare à la main, ligne par ligne.

La règle qui l'empêche
----------------------

Un candidat ne prend la main que s'il obtient la voix d'une **majorité
stricte** des serveurs de la grappe, et chaque serveur n'accorde **qu'une
voix par époque**. Deux candidats ne peuvent alors pas réunir chacun une
majorité dans la même époque : deux majorités d'un même ensemble ont forcément
un serveur en commun, et celui-ci n'a voté qu'une fois. La divergence devient
structurellement impossible, au lieu d'être simplement improbable.

C'est la propriété de sûreté d'une élection de chef, et elle ne tient qu'à
deux conditions : l'époque est strictement croissante, et la voix est
persistée avant d'être annoncée. Les deux sont tenues ici.

Ce que cela coûte, et qu'il faut savoir
---------------------------------------

Avec **deux** serveurs, une majorité en vaut deux : le principal tombé devrait
voter pour le secondaire. La bascule automatique est donc impossible à deux, et
ce module le dit explicitement au lieu de l'ignorer en silence. Ce n'est pas
une limite de l'implémentation, c'est le théorème : à deux, rien ne permet de
distinguer « l'autre est mort » de « je suis isolé ». Trois serveurs — ou deux
serveurs et un témoin — sont nécessaires, et la bascule manuelle reste
disponible dans tous les cas.
"""

import requests as http_requests
from django.conf import settings
from django.utils import timezone

from apps.high_availability.models import OrionHANode, OrionHASettings

DELAI_VOTE = 8  # secondes ; un serveur qui tarde autant est hors quorum


def identifiant_local():
    return getattr(settings, 'ORION_NODE_ID', '') or ''


def majorite(total_serveurs):
    """Nombre de voix nécessaires : strictement plus de la moitié.

    Pour 3 serveurs, 2 voix ; pour 4, 3 ; pour 5, 3. Jamais la moitié exacte,
    sans quoi deux moitiés disjointes pourraient élire deux chefs.
    """
    if total_serveurs <= 0:
        return 0
    return total_serveurs // 2 + 1


def serveurs_de_la_grappe():
    """Les serveurs qui composent la grappe, y compris celui-ci et le tombé.

    Deux choix dans ce dénominateur, et chacun évite une panne distincte.

    **Les serveurs INJOIGNABLES comptent.** Calculer la majorité sur les seuls
    serveurs joignables permettrait à un serveur isolé de former à lui seul
    « la majorité » de l'ensemble qu'il voit — exactement la divergence que
    l'on cherche à exclure.

    **Les serveurs DÉSACTIVÉS ne comptent pas.** Un serveur désactivé est
    retiré de la grappe par décision de l'exploitant : le balayage de santé ne
    l'interroge plus, et il ne peut plus recevoir la main. Le compter
    reviendrait à exiger la voix d'une machine dont on a décidé qu'elle ne
    participe plus. Une grappe ramenée de trois serveurs à un seul verrait
    alors son unique serveur exiger deux voix — et se clôturer lui-même
    définitivement, sans que rien ne l'explique.
    """
    return list(
        OrionHANode.objects.filter(is_enabled=True).order_by('priority', 'id')
    )


def accorder_une_voix(epoque, candidat_id, primaire_injoignable):
    """Décision de CE serveur sur une demande de voix.

    Les trois refus possibles sont distincts, et chacun a sa raison d'être :

    - époque dépassée : une demande en retard ne doit pas défaire un vote déjà
      accordé pour une époque plus récente ;
    - voix déjà donnée dans cette époque : c'est la règle qui rend deux
      majorités simultanées impossibles ;
    - principal encore joignable de ce point de vue : refuser alors évite
      qu'un serveur momentanément isolé fasse basculer une grappe saine.
    """
    reglages = OrionHASettings.get_solo()
    candidat_id = (candidat_id or '').strip()

    if not candidat_id:
        return {'accordee': False, 'raison': 'Candidat non identifié.',
                'epoque': reglages.vote_epoch}

    if candidat_id == identifiant_local():
        # Un serveur vote pour lui-même en local, sans passer par ici.
        return {'accordee': False,
                'raison': 'Demande adressée au candidat lui-même.',
                'epoque': reglages.vote_epoch}

    try:
        epoque = int(epoque)
    except (TypeError, ValueError):
        return {'accordee': False, 'raison': 'Époque illisible.',
                'epoque': reglages.vote_epoch}

    if epoque <= 0:
        return {'accordee': False, 'raison': 'Époque invalide.',
                'epoque': reglages.vote_epoch}

    if epoque < reglages.vote_epoch:
        return {
            'accordee': False,
            'raison': (
                'Époque %s dépassée : ce serveur a déjà voté pour l’époque %s.'
                % (epoque, reglages.vote_epoch)
            ),
            'epoque': reglages.vote_epoch,
        }

    if epoque == reglages.vote_epoch and reglages.vote_node_id:
        # Une voix déjà accordée est rappelée telle quelle : si le candidat est
        # le même, sa demande a simplement été réémise (réseau instable), et il
        # doit pouvoir la recompter sans que cela constitue une seconde voix.
        accordee = reglages.vote_node_id == candidat_id
        return {
            'accordee': accordee,
            'raison': ('Voix déjà accordée à %s pour cette époque.'
                       % reglages.vote_node_id),
            'epoque': reglages.vote_epoch,
            'deja': True,
        }

    if not primaire_injoignable:
        return {
            'accordee': False,
            'raison': 'Le serveur principal reste joignable depuis ce serveur.',
            'epoque': reglages.vote_epoch,
        }

    # Persistée AVANT d'être annoncée : une voix annoncée puis perdue (coupure
    # de courant) pourrait être accordée une seconde fois dans la même époque,
    # et deux majorités deviendraient possibles.
    reglages.vote_epoch = epoque
    reglages.vote_node_id = candidat_id
    reglages.vote_at = timezone.now()
    reglages.save(update_fields=['vote_epoch', 'vote_node_id', 'vote_at'])

    return {'accordee': True, 'raison': 'Voix accordée.', 'epoque': epoque}


def _demander_voix(serveur, epoque, candidat_id):
    """Demande sa voix à un autre serveur. Toute panne vaut un refus."""
    base = (serveur.base_url or '').rstrip('/')
    if not base:
        return {'accordee': False, 'raison': 'Aucune adresse connue.'}

    secret = getattr(settings, 'ORION_HA_SECRET', '')
    try:
        reponse = http_requests.post(
            base + '/ha/vote/',
            data={'epoch': epoque, 'candidate_id': candidat_id},
            headers={'X-Orion-HA-Secret': secret},
            timeout=DELAI_VOTE,
        )
    except http_requests.exceptions.RequestException as erreur:
        # Un serveur injoignable ne vote pas. Il n'est pas pour autant compté
        # comme opposé : il manque simplement à la majorité, ce qui suffit à
        # bloquer une bascule dans le doute.
        return {'accordee': False, 'raison': 'Injoignable (%s).' % erreur.__class__.__name__}

    if reponse.status_code != 200:
        return {'accordee': False,
                'raison': 'Réponse HTTP %s.' % reponse.status_code}

    try:
        donnees = reponse.json()
    except ValueError:
        return {'accordee': False, 'raison': 'Réponse illisible.'}

    return {
        'accordee': bool(donnees.get('accordee')),
        'raison': donnees.get('raison') or '',
    }


def conduire_election(candidat, primaire_injoignable=True):
    """Tente de faire élire `candidat`. Ne modifie aucun rôle.

    Renvoie un compte-rendu complet — voix obtenues, majorité requise, motif
    de chaque refus — parce qu'une bascule refusée doit pouvoir s'expliquer.
    Une bascule automatique qui ne se produit pas, sans que rien ne dise
    pourquoi, est aussi gênante qu'une bascule à tort.
    """
    serveurs = serveurs_de_la_grappe()
    total = len(serveurs)
    requis = majorite(total)

    compte_rendu = {
        'elu': False,
        'candidat': getattr(candidat, 'node_id', ''),
        'total_serveurs': total,
        'voix_requises': requis,
        'voix': 0,
        'epoque': 0,
        'details': [],
        'raison': '',
    }

    if total < 3:
        # Dit explicitement, et non ignoré : à deux serveurs, la majorité vaut
        # deux, donc le principal tombé devrait voter. C'est le théorème, pas
        # une limite de code.
        compte_rendu['raison'] = (
            'Bascule automatique impossible avec %s serveur(s) : une majorité '
            'en exigerait %s, et le serveur tombé ne peut pas voter. À deux '
            'serveurs, rien ne distingue « l’autre est mort » de « je suis '
            'isolé ». Ajoutez un troisième serveur, ou basculez manuellement.'
            % (total, requis)
        )
        return compte_rendu

    reglages = OrionHASettings.get_solo()
    # Époque strictement croissante : elle départage les élections, et une
    # demande d'une époque antérieure ne peut pas défaire un vote plus récent.
    epoque = max(reglages.election_epoch, reglages.vote_epoch) + 1
    reglages.election_epoch = epoque
    reglages.save(update_fields=['election_epoch'])
    compte_rendu['epoque'] = epoque

    # Le candidat vote pour lui-même, et cette voix est persistée comme les
    # autres : sans cela, il pourrait voter pour un autre candidat dans la
    # même époque, et deux majorités redeviendraient possibles.
    reglages.vote_epoch = epoque
    reglages.vote_node_id = candidat.node_id
    reglages.vote_at = timezone.now()
    reglages.save(update_fields=['vote_epoch', 'vote_node_id', 'vote_at'])

    voix = 1
    compte_rendu['details'].append({
        'serveur': candidat.node_id,
        'accordee': True,
        'raison': 'Voix du candidat lui-même.',
    })

    for serveur in serveurs:
        if serveur.node_id == candidat.node_id:
            continue
        resultat = _demander_voix(serveur, epoque, candidat.node_id)
        compte_rendu['details'].append({
            'serveur': serveur.node_id,
            'accordee': resultat['accordee'],
            'raison': resultat['raison'],
        })
        if resultat['accordee']:
            voix += 1

    compte_rendu['voix'] = voix
    compte_rendu['elu'] = voix >= requis

    if compte_rendu['elu']:
        compte_rendu['raison'] = (
            '%s voix sur %s serveurs (%s requises) : majorité obtenue.'
            % (voix, total, requis)
        )
    else:
        compte_rendu['raison'] = (
            '%s voix sur %s serveurs, %s requises : pas de majorité. Aucune '
            'bascule, pour ne pas risquer deux serveurs actifs.'
            % (voix, total, requis)
        )

    return compte_rendu


def verifier_quorum_local(resultats_de_sante=None):
    """Le serveur actif voit-il encore une majorité de la grappe ?

    Exiger une majorité pour PROMOUVOIR (voir conduire_election) interdit à une
    minorité d'élire un nouveau chef. Cela ne suffit pas : le serveur DÉJÀ
    actif qui se retrouve du mauvais côté d'une coupure continue de se croire
    actif et d'accepter des écritures, pendant que la majorité en élit
    légitimement un autre. Deux serveurs écrivent alors — la divergence, par un
    autre chemin.

    Ce contrôle ferme ce chemin : privé de majorité, le serveur actif refuse
    les écritures jusqu'à la retrouver. Perdre l'écriture sur le serveur isolé
    est le prix, et c'est le bon : une indisponibilité s'attend et se répare,
    une divergence se répare à la main, ligne par ligne.

    `resultats_de_sante` évite de resonder le réseau quand le balayage de
    santé vient de le faire. Chaque entrée porte 'node' et 'ok'.
    """
    reglages = OrionHASettings.get_solo()

    if not reglages.split_brain_protection_enabled:
        # L'exploitant a explicitement levé la protection : on ne la réimpose
        # pas par un autre biais.
        if reglages.quorum_perdu:
            reglages.quorum_perdu = False
            reglages.quorum_perdu_depuis = None
            reglages.save(update_fields=['quorum_perdu', 'quorum_perdu_depuis'])
        return {'applicable': False, 'raison': 'Protection anti-divergence levée.'}

    moi = identifiant_local()
    serveurs = serveurs_de_la_grappe()
    total = len(serveurs)

    actif = next((s for s in serveurs if s.is_current_active), None)
    if actif is None or actif.node_id != moi:
        # Ce serveur n'est pas l'actif : il n'a rien à clôturer, et
        # l'intergiciel lui refuse déjà les écritures.
        return {'applicable': False, 'raison': "Ce serveur n'est pas l'actif."}

    if total < 3:
        # À deux serveurs, la majorité vaut deux : une simple coupure du lien
        # clôturerait l'actif alors qu'il est le seul à pouvoir servir. Le
        # remède serait pire que le mal, et la bascule automatique est de toute
        # façon refusée à deux (voir conduire_election).
        return {
            'applicable': False,
            'raison': ('Grappe de %s serveur(s) : clôture inapplicable, elle '
                       'rendrait le seul serveur utilisable inutilisable.'
                       % total),
        }

    requis = majorite(total)

    if resultats_de_sante:
        joignables = {
            resultat['node'].node_id
            for resultat in resultats_de_sante
            if resultat.get('ok') and resultat.get('node') is not None
        }
    else:
        joignables = {
            serveur.node_id for serveur in serveurs
            if not serveur.is_stale and serveur.status != 'down'
        }
    joignables.add(moi)   # un serveur se voit toujours lui-même

    vus = len(joignables)
    perdu = vus < requis

    if perdu != reglages.quorum_perdu:
        reglages.quorum_perdu = perdu
        reglages.quorum_perdu_depuis = timezone.now() if perdu else None
        reglages.save(update_fields=['quorum_perdu', 'quorum_perdu_depuis'])

    return {
        'applicable': True,
        'quorum_perdu': perdu,
        'vus': vus,
        'requis': requis,
        'total_serveurs': total,
        'raison': (
            '%s serveur(s) vus sur %s, %s requis : écritures refusées jusqu’au '
            'retour de la majorité.' % (vus, total, requis)
        ) if perdu else (
            '%s serveur(s) vus sur %s, majorité tenue.' % (vus, total)
        ),
    }
