"""Réseau privé entre sites : adresses déduites du rang.

En production, les serveurs ne partagent aucun réseau local. Les relier par
leurs adresses publiques supposerait d'ouvrir des ports à chaque site, de
dépendre d'IP qui changent, et de faire voyager la réplication MySQL en clair
sur Internet — ce dernier point à lui seul l'interdit.

Un réseau privé WireGuard résout tout d'un coup : adresses stables quelles que
soient le fournisseur et le NAT, chiffrement par conception, et MySQL qui peut
écouter sur cette seule adresse sans jamais être public.

L'adresse privée se déduit du rang, exactement comme le nom d'hôte :

    rang 1  ->  serveur1.exemple.fr  ->  10.10.0.1
    rang 2  ->  serveur2.exemple.fr  ->  10.10.0.2

Un seul chiffre par serveur, et les trois identités (nom, rang, adresse
privée) ne peuvent plus se contredire.

Ce module ne contient que la dérivation et la génération de configuration, en
fonctions pures : c'est ce qui permet de les éprouver sans WireGuard installé
ni privilège root. La pose effective est le travail de
`deployment/proxmox-appliance/scripts/orion-mesh.sh`.
"""

import ipaddress

from django.conf import settings

from apps.high_availability.cluster import hote_du_rang
from apps.high_availability.models import OrionHANode, OrionHASettings


class MeshConfigError(ValueError):
    """Réglage de réseau privé inutilisable."""


def reseau(settings_obj):
    """Objet réseau du sous-réseau privé, validé."""
    brut = (settings_obj.mesh_subnet or '').strip()
    if not brut:
        raise MeshConfigError("Aucun sous-réseau privé n'est renseigné.")
    try:
        return ipaddress.ip_network(brut, strict=False)
    except ValueError as exc:
        raise MeshConfigError(f'Sous-réseau privé illisible : {brut} ({exc})') from exc


def adresse_overlay(settings_obj, rang):
    """Adresse privée du serveur de ce rang.

    Le rang sert d'index d'hôte dans le sous-réseau. Le rang 0 est refusé : ce
    serait l'adresse du réseau lui-même, et un rang commence à 1 de toute
    façon.
    """
    if rang is None or int(rang) < 1:
        raise MeshConfigError(f'Rang invalide pour une adresse privée : {rang!r}')

    res = reseau(settings_obj)
    rang = int(rang)

    # `num_addresses - 2` écarte l'adresse de réseau et celle de diffusion.
    if rang > res.num_addresses - 2:
        raise MeshConfigError(
            f'Le rang {rang} ne tient pas dans {res} : élargissez le '
            'sous-réseau privé.'
        )
    return str(res.network_address + rang)


def entrees_hosts(settings_obj=None):
    """Couples (adresse privée, nom d'hôte) pour chaque rang connu.

    Les noms viennent de la convention de nommage, les adresses du rang : la
    résolution privée est donc entièrement déduite, sans table à tenir.
    """
    settings_obj = settings_obj or OrionHASettings.get_solo()
    rangs = sorted({n.priority for n in OrionHANode.objects.all() if n.priority})

    if not rangs:
        rangs = list(range(1, (settings_obj.cluster_max_nodes or 8) + 1))

    entrees = []
    for rang in rangs:
        hote = hote_du_rang(settings_obj, rang)
        if not hote:
            continue
        try:
            entrees.append((adresse_overlay(settings_obj, rang), hote))
        except MeshConfigError:
            continue
    return entrees


def config_locale(settings_obj=None):
    """Valeurs de configuration du réseau privé pour CE serveur.

    Destinées à être sourcées par un script shell : c'est ainsi que
    `orion-mesh.sh` et l'application partagent une seule source de vérité, au
    lieu de dupliquer la dérivation de part et d'autre.
    """
    settings_obj = settings_obj or OrionHASettings.get_solo()
    rang = getattr(settings, 'ORION_NODE_PRIORITY', 1) or 1
    res = reseau(settings_obj)

    return {
        'ORION_MESH_ADDRESS': adresse_overlay(settings_obj, rang),
        'ORION_MESH_PREFIX': str(res.prefixlen),
        'ORION_MESH_SUBNET': str(res),
        'ORION_MESH_PORT': str(settings_obj.mesh_port or 51820),
        'ORION_MESH_RANK': str(rang),
        'ORION_MESH_HOST': hote_du_rang(settings_obj, rang) or '',
    }


def parse_wg_dump(texte):
    """Analyse la sortie de `wg show <iface> dump`.

    Format : la première ligne décrit l'interface, les suivantes un pair
    chacune, en colonnes séparées par des tabulations.

    `latest-handshake` est la valeur qui compte : un pair déclaré mais dont la
    poignée de main vaut 0 n'a JAMAIS répondu. C'est l'exacte différence entre
    « configuré » et « fonctionne », et la confondre fait croire à une liaison
    là où il n'y a qu'une déclaration — précisément le genre de faux positif
    qu'on ne découvre qu'au moment de la bascule.
    """
    lignes = [l for l in (texte or '').splitlines() if l.strip()]
    if not lignes:
        return {'interface': {}, 'pairs': []}

    champs = lignes[0].split('\t')
    interface = {
        'public_key': champs[1] if len(champs) > 1 else '',
        'listen_port': champs[2] if len(champs) > 2 else '',
    }

    pairs = []
    for ligne in lignes[1:]:
        c = ligne.split('\t')
        if len(c) < 5:
            continue

        def _entier(valeur):
            try:
                return int(valeur)
            except (TypeError, ValueError):
                return 0

        poignee = _entier(c[4])
        pairs.append({
            'public_key': c[0],
            'endpoint': '' if c[2] in ('(none)', '') else c[2],
            'allowed_ips': '' if c[3] in ('(none)', '') else c[3],
            'latest_handshake': poignee,
            'a_repondu': poignee > 0,
            'rx': _entier(c[5]) if len(c) > 5 else 0,
            'tx': _entier(c[6]) if len(c) > 6 else 0,
        })

    return {'interface': interface, 'pairs': pairs}


def pairs_attendus(settings_obj=None):
    """Pairs que CE serveur devrait avoir : tous les autres rangs connus.

    Sert au diagnostic — comparer à ce que WireGuard déclare réellement — et à
    rappeler à l'exploitant quelles clés publiques il lui reste à échanger.
    """
    settings_obj = settings_obj or OrionHASettings.get_solo()
    notre_rang = getattr(settings, 'ORION_NODE_PRIORITY', 1) or 1

    pairs = []
    for node in OrionHANode.objects.filter(is_enabled=True).order_by('priority'):
        if not node.priority or node.priority == notre_rang:
            continue
        try:
            adresse = adresse_overlay(settings_obj, node.priority)
        except MeshConfigError:
            continue
        pairs.append({
            'rang': node.priority,
            'node_id': node.node_id,
            'hote': hote_du_rang(settings_obj, node.priority),
            'adresse': adresse,
        })
    return pairs
