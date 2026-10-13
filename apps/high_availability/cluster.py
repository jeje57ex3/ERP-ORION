"""Grappe Orion : adresses déduites d'une convention, et adhésion validée.

Raccorder un serveur demandait de saisir son adresse complète et son rang de
préséance, machine par machine. Deux saisies qui pouvaient se contredire —
rien n'empêchait d'enregistrer « serveur3.exemple.fr » avec le rang 2.

Avec une convention de nommage, les deux se déduisent l'un de l'autre :
« serveur2.exemple.fr » **est** le serveur de rang 2. Il suffit alors du
domaine de la grappe pour chercher tous ses membres.

    rang 1  ->  serveur1.exemple.fr   (principal)
    rang 2  ->  serveur2.exemple.fr
    rang 3  ->  serveur3.exemple.fr
    ...

L'adhésion est validée **dans les deux sens**. Le serveur source sonde le
candidat, puis demande au candidat de le sonder en retour (`/ha/join-check/`).
Sans cette réciprocité, l'enregistrement ne prouve qu'un sens de la liaison,
et le cas asymétrique est aussi courant que redoutable : le principal joint le
secondaire, l'affiche « sain », mais le secondaire ne peut pas joindre le
principal. Pare-feu unilatéral, tunnel sortant seul, DNS interne partiel. Rien
ne le signale — jusqu'à la bascule, où le nouveau serveur actif se découvre
incapable de surveiller l'ancien.
"""

import requests
from django.conf import settings

from apps.high_availability.connection import diagnose_node_connection
from apps.high_availability.models import OrionHANode, OrionHASettings

DELAI_SECONDES = 8


def motif_valide(motif):
    return '{n}' in (motif or '')


def hote_du_rang(settings_obj, rang):
    """Nom d'hôte attendu pour ce rang, ou '' si la grappe n'est pas réglée."""
    base = (settings_obj.cluster_base_domain or '').strip().strip('.').lower()
    motif = (settings_obj.node_name_pattern or '').strip()
    if not base or not motif_valide(motif):
        return ''
    return f"{motif.replace('{n}', str(rang))}.{base}"


def adresse_du_rang(settings_obj, rang):
    hote = hote_du_rang(settings_obj, rang)
    if not hote:
        return ''
    schema = 'https' if settings_obj.cluster_use_https else 'http'
    return f'{schema}://{hote}'


def adresse_de_ce_serveur(settings_obj):
    """Adresse de CE serveur dans la convention, pour la validation réciproque.

    Déduite de son rang configuré (`ORION_NODE_PRIORITY`) plutôt que du nœud
    actif en base : la base peut être vide ou en désaccord, et c'est justement
    dans ces moments-là qu'on raccorde des serveurs.
    """
    rang = getattr(settings, 'ORION_NODE_PRIORITY', 1) or 1
    return adresse_du_rang(settings_obj, rang)


def verifier_reciprocite(candidat_url, source_url):
    """Demande au candidat de sonder le serveur source en retour.

    Retourne un dictionnaire avec `ok`, `detail`, et l'identifiant que le
    candidat a relevé sur le source. Un candidat d'une version antérieure
    n'expose pas ce point : c'est signalé comme tel, et non comme un échec de
    liaison.
    """
    resultat = {'ok': False, 'detail': '', 'source_node_id': '', 'supported': True}

    if not source_url:
        resultat['detail'] = (
            "L'adresse de CE serveur dans la convention est inconnue : "
            'renseignez le domaine de la grappe et son motif de nommage.'
        )
        return resultat

    secret = getattr(settings, 'ORION_HA_SECRET', '')
    if not secret or secret == 'CHANGE_ME':
        resultat['detail'] = "Ce serveur-ci n'a pas de secret de haute disponibilité."
        return resultat

    try:
        reponse = requests.post(
            f"{candidat_url.rstrip('/')}/ha/join-check/",
            headers={'X-Orion-HA-Secret': secret},
            data={'source_url': source_url},
            timeout=DELAI_SECONDES,
        )
    except requests.RequestException as exc:
        resultat['detail'] = f'Candidat injoignable pour la validation : {exc}'
        return resultat

    if reponse.status_code in (404, 405):
        resultat['supported'] = False
        resultat['detail'] = (
            "Ce serveur n'expose pas la validation réciproque : sa version est "
            'antérieure. Mettez-le à jour, ou raccordez-le sans réciprocité.'
        )
        return resultat

    if reponse.status_code == 403:
        resultat['detail'] = (
            'Le candidat refuse notre secret : ORION_HA_SECRET diffère entre '
            'les deux machines.'
        )
        return resultat

    try:
        donnees = reponse.json()
    except ValueError:
        resultat['detail'] = f'Réponse de validation illisible (HTTP {reponse.status_code}).'
        return resultat

    resultat['source_node_id'] = (donnees.get('source_node_id') or '').strip()
    resultat['detail'] = donnees.get('detail') or ''

    if not donnees.get('source_reachable'):
        resultat['detail'] = resultat['detail'] or (
            'Le candidat ne joint pas ce serveur-ci : la liaison ne fonctionne '
            "que dans un sens."
        )
        return resultat

    if not donnees.get('secret_match'):
        return resultat

    resultat['ok'] = True
    return resultat


def explorer_grappe(settings_obj=None, rangs=None):
    """Sonde chaque rang de la convention et valide ceux qui répondent.

    Un rang absent n'est pas une erreur : la grappe n'a pas besoin d'être
    contiguë, et l'on explore volontairement au-delà du nombre de serveurs
    existants.
    """
    settings_obj = settings_obj or OrionHASettings.get_solo()
    source_url = adresse_de_ce_serveur(settings_obj)
    notre_id = getattr(settings, 'ORION_NODE_ID', '')
    deja = {n.node_id: n for n in OrionHANode.objects.all()}

    if rangs is None:
        rangs = range(1, (settings_obj.cluster_max_nodes or 8) + 1)

    trouves = []
    for rang in rangs:
        url = adresse_du_rang(settings_obj, rang)
        if not url:
            break

        ligne = {
            'rang': rang,
            'url': url,
            'hote': hote_du_rang(settings_obj, rang),
            'present': False,
            'node_id': '',
            'diagnostic': None,
            'reciprocite': None,
            'est_ce_serveur': False,
            'deja_raccorde': False,
            'raccordable': False,
        }

        diagnostic = diagnose_node_connection(url)
        ligne['diagnostic'] = diagnostic
        ligne['node_id'] = diagnostic['node_id']

        # Aucun Orion à ce rang : on le passe en silence, sans le présenter
        # comme un défaut. C'est le cas normal des rangs non pourvus.
        if not diagnostic['node_id']:
            trouves.append(ligne)
            continue

        ligne['present'] = True
        ligne['est_ce_serveur'] = bool(notre_id and diagnostic['node_id'] == notre_id)
        ligne['deja_raccorde'] = diagnostic['node_id'] in deja

        if ligne['est_ce_serveur']:
            # Se valider soi-même en réciprocité n'aurait aucun sens.
            ligne['raccordable'] = True
        else:
            ligne['reciprocite'] = verifier_reciprocite(url, source_url)
            ligne['raccordable'] = bool(
                diagnostic['identity_ok'] and ligne['reciprocite']['ok']
            )

        trouves.append(ligne)

    return {'source_url': source_url, 'rangs': trouves}


def raccorder_grappe(exploration, settings_obj=None):
    """Enregistre les serveurs validés, rang et adresse tirés de la convention.

    `update_or_create` sur `node_id` : relancer une exploration est donc sans
    danger, et corrige au passage l'adresse ou le rang d'un nœud mal saisi
    précédemment.
    """
    settings_obj = settings_obj or OrionHASettings.get_solo()
    actif_existe = OrionHANode.objects.filter(is_current_active=True).exists()

    poses, ignores = [], []
    for ligne in exploration['rangs']:
        if not ligne['present']:
            continue
        if not ligne['raccordable']:
            ignores.append(ligne)
            continue

        est_nous = ligne['est_ce_serveur']
        defauts = {
            'base_url': ligne['url'],
            'priority': ligne['rang'],
            'is_enabled': True,
        }

        # Le nom n'est posé qu'à la création : une exploration ne doit pas
        # effacer celui que l'exploitant a choisi. L'adresse et le rang, eux,
        # viennent de la convention et sont donc remis en accord avec elle.
        existant = OrionHANode.objects.filter(node_id=ligne['node_id']).first()
        if existant is None:
            defauts['name'] = ligne['hote']

        if est_nous:
            defauts.update({
                'role': 'primary',
                'status': 'active',
                'is_failover_target': False,
            })
        else:
            defauts.update({
                'role': 'secondary',
                'status': 'healthy' if ligne['diagnostic']['ok'] else 'warning',
                'is_failover_target': True,
                'allow_auto_failover': True,
            })

        node, cree = OrionHANode.objects.update_or_create(
            node_id=ligne['node_id'], defaults=defauts,
        )

        # Le serveur courant ne devient actif que si PERSONNE ne l'est : on ne
        # déplace jamais la main au détour d'une exploration.
        if est_nous and not actif_existe:
            from apps.high_availability.services import set_active_node
            set_active_node(node)
            actif_existe = True

        poses.append({'node': node, 'cree': cree, 'rang': ligne['rang']})

    return {'poses': poses, 'ignores': ignores}
