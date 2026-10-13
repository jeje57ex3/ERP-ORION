"""Bascule du cluster Orion (haute disponibilité).

Redirection du trafic — modèle d'indirection. Tous les domaines publics (ERP,
boutiques, vitrines, domaines clients) pointent par CNAME vers UN SEUL nom
d'indirection, réglable par `cloudflare_record_name` (« actif » par défaut).
Ce nom pointe à son tour vers le sous-domaine propre du serveur actif, celui
que porte le champ `base_url` du nœud :

    erp.exemple.fr     ─┐
    siecle.exemple.fr  ─┤                              serveur1.exemple.fr
    lunea.exemple.fr   ─┼─ CNAME ─→ actif.exemple.fr ─→
    ns.exemple.fr      ─┤                   ↑           serveur2.exemple.fr
    + domaines clients ─┘        seul enregistrement
                                 modifié à la bascule

La bascule ne touche donc qu'un enregistrement, et jamais les domaines
eux-mêmes. Les repointer un par un aurait imposé autant d'appels API que de
domaines, sans transaction possible : un échec au milieu de la série laisse
une partie du trafic sur le serveur mort et l'autre sur le vivant. Ici, le
seul appel réussit ou échoue en bloc.

Le sous-domaine par nœud sert de cible stable : contrairement à une IP
publique, il ne bouge pas quand le bail DHCP de la machine change.
"""

from urllib.parse import urlsplit

from django.db import connection, transaction
from django.utils import timezone

from apps.high_availability.models import (
    OrionHANode,
    OrionHASettings,
    OrionHAFailoverEvent,
)
from apps.high_availability.services import set_active_node


class FailoverPromotionError(RuntimeError):
    """La base cible est restée en lecture seule : rien n'a basculé."""


class FailoverTrafficError(RuntimeError):
    """La base est promue mais le trafic n'a pas pu être redirigé.

    Distincte de FailoverPromotionError parce que la conduite à tenir diffère :
    ici le nœud cible est inscriptible, mais les domaines continuent de pointer
    vers l'ancien. Il faut repointer l'enregistrement d'indirection, pas
    relancer la bascule.
    """


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
    """Arrête la réplication, lève la lecture seule, puis VÉRIFIE le résultat.

    Les deux familles de commandes sont tentées volontairement : MySQL 8 a
    renommé STOP SLAVE en STOP REPLICA, MariaDB ne connaît que l'ancien nom.
    L'une des deux échoue donc toujours, d'où l'absorption commande par
    commande.

    Mais le résultat, lui, est contrôlé. Sans cette vérification finale, une
    promotion refusée faute de privilège SUPER passait totalement inaperçue :
    la bascule se déclarait réussie sur une base toujours en lecture seule, et
    la panne n'apparaissait qu'à la première écriture d'un utilisateur.
    """
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

        try:
            cursor.execute('SELECT @@global.read_only')
            ligne = cursor.fetchone()
        except Exception:
            # Moteur sans réplication MySQL (SQLite en test) : rien à vérifier.
            return

    if ligne and str(ligne[0]).upper() not in ('0', 'OFF', 'FALSE'):
        raise FailoverPromotionError(
            'La base cible est restée en lecture seule après la promotion. '
            "Vérifiez que l'utilisateur MySQL possède le privilège SUPER, "
            'puis relancez la bascule.'
        )


def _hote_du_noeud(node):
    """Hôte du sous-domaine propre au nœud, extrait de `base_url`.

    Accepte une URL complète comme un nom nu : le champ est un URLField, mais
    une valeur saisie à la main peut arriver sans schéma.
    """
    brut = (node.base_url or '').strip()
    if not brut:
        return ''
    if '://' not in brut:
        brut = f'//{brut}'
    return (urlsplit(brut).hostname or '').strip('.').lower()


def _zone_id_depuis_fqdn(client, fqdn):
    """Zone Cloudflare contenant `fqdn`, par essais du suffixe le plus court.

    Nécessaire parce qu'on ne peut pas deviner le domaine enregistrable par
    simple découpage : « exemple.fr » tient en deux étiquettes, « exemple.co.uk »
    en trois.
    """
    etiquettes = fqdn.split('.')
    for taille in range(2, len(etiquettes) + 1):
        candidat = '.'.join(etiquettes[-taille:])
        zones = client.list_zones(name=candidat)
        if zones:
            return zones[0]['id']
    raise FailoverTrafficError(
        f'Aucune zone Cloudflare ne correspond à {fqdn}. Renseignez '
        "l'identifiant de zone dans les paramètres de haute disponibilité."
    )


def _cible_dns(settings_obj, client):
    """Résout le couple (zone_id, FQDN) de l'enregistrement d'indirection.

    Le réglage `cloudflare_record_name` accepte les deux formes : une étiquette
    seule (« actif »), complétée par le nom de la zone, ou un nom déjà complet
    (« actif.exemple.fr »).
    """
    nom = (settings_obj.cloudflare_record_name or '').strip().strip('.').lower()
    if not nom:
        raise FailoverTrafficError(
            "Le nom de l'enregistrement de bascule n'est pas renseigné dans les "
            'paramètres de haute disponibilité.'
        )

    zone_id = (settings_obj.cloudflare_zone_id or '').strip()

    if '.' in nom:
        return (zone_id or _zone_id_depuis_fqdn(client, nom)), nom

    if not zone_id:
        raise FailoverTrafficError(
            f'« {nom} » est une étiquette seule : renseignez aussi '
            "l'identifiant de zone Cloudflare, ou saisissez le nom complet "
            '(ex. actif.exemple.fr).'
        )

    zone = client.get_zone(zone_id) or {}
    nom_zone = (zone.get('name') or '').strip('.').lower()
    if not nom_zone:
        raise FailoverTrafficError(
            f'Zone Cloudflare {zone_id} introuvable : impossible de compléter '
            f'« {nom} » en nom de domaine.'
        )
    return zone_id, f'{nom}.{nom_zone}'


def _update_dns_or_cloudflare(target_node):
    """Repointe l'enregistrement d'indirection vers le nœud cible.

    Ne modifie que `content` (via PATCH) : le type, le TTL et surtout l'état
    « proxifié » de l'enregistrement sont conservés tels quels. Un PUT complet
    aurait risqué d'éteindre le proxy Cloudflare au passage, ce qui coupe les
    domaines servis par tunnel.
    """
    settings_obj = OrionHASettings.get_solo()
    if not settings_obj.cloudflare_failover_enabled:
        return {'skipped': True, 'reason': 'Cloudflare failover disabled'}

    cible = _hote_du_noeud(target_node)
    if not cible:
        raise FailoverTrafficError(
            f"Le nœud « {target_node.node_id} » n'a pas d'URL de base : "
            'impossible de savoir vers quel hôte rediriger les domaines. '
            'Renseignez son sous-domaine (ex. https://serveur2.exemple.fr).'
        )

    from apps.domain_diagnostics.cloudflare import CloudflareAPIError, CloudflareClient

    try:
        client = CloudflareClient()
        zone_id, fqdn = _cible_dns(settings_obj, client)

        if fqdn == cible:
            raise FailoverTrafficError(
                f"L'enregistrement d'indirection ({fqdn}) et le sous-domaine du "
                'nœud cible sont identiques : le CNAME pointerait sur lui-même. '
                'Donnez au nœud son propre sous-domaine.'
            )

        enregistrements = client.list_dns_records(zone_id, name=fqdn)
        record_fige = (settings_obj.cloudflare_dns_record_id or '').strip()

        record = None
        for candidat in enregistrements:
            if record_fige and candidat.get('id') != record_fige:
                continue
            if candidat.get('type') in ('CNAME', 'A'):
                record = candidat
                break

        if record is None:
            raise FailoverTrafficError(
                f'Aucun enregistrement CNAME ou A nommé {fqdn} dans la zone. '
                'Créez-le une fois, pointé vers le serveur actif : la bascule '
                'se contente ensuite de le déplacer.'
            )

        if record['type'] == 'CNAME':
            contenu = cible
        else:
            # Enregistrement A : pas de tunnel devant, on écrit l'IP. Le nom
            # du nœud ne servirait à rien dans un champ qui attend une adresse.
            if not target_node.public_ip:
                raise FailoverTrafficError(
                    f'{fqdn} est un enregistrement A, mais le nœud '
                    f"« {target_node.node_id} » n'a pas d'IP publique renseignée."
                )
            contenu = str(target_node.public_ip)

        # Relevé AVANT l'appel : le client peut renvoyer, ou réutiliser, le
        # dictionnaire de l'enregistrement, et la valeur précédente serait
        # alors déjà écrasée au moment de la journaliser.
        precedent = record.get('content') or ''

        commun = {
            'zone_id': zone_id,
            'record': fqdn,
            'record_id': record['id'],
            'record_type': record['type'],
            'content': contenu,
            'target_node': target_node.node_id,
        }

        if precedent.strip('.').lower() == contenu.lower():
            return {'changed': False, 'reason': 'Enregistrement déjà à jour', **commun}

        client.patch_dns_record(zone_id, record['id'], content=contenu)
        return {'changed': True, 'previous': precedent, **commun}

    except CloudflareAPIError as exc:
        raise FailoverTrafficError(
            f'Cloudflare a refusé la redirection du trafic : {exc}'
        ) from exc


def _enregistrer_evenement(**champs):
    """Écrit la trace d'audit de la bascule.

    Isolée dans sa propre transaction : elle est volontairement la DERNIÈRE
    écriture, puisque la base cible n'est inscriptible qu'après promotion.
    """
    with transaction.atomic():
        return OrionHAFailoverEvent.objects.create(
            finished_at=timezone.now(),
            **champs,
        )


def run_manual_failover_to_node(*, target_node, started_by=None, reason='',
                                event_type='manual_failover'):
    """Bascule le cluster vers `target_node`.

    L'ordre des étapes est contraint par la réplication : la base du nœud cible
    est en lecture seule tant qu'elle n'est pas promue, donc AUCUNE écriture ne
    peut précéder la promotion.

    La version précédente créait l'événement d'audit en toute première
    instruction, dans une transaction atomique englobant tout. Elle ne pouvait
    donc jamais aboutir depuis le serveur survivant — le seul endroit d'où une
    bascule ait un sens quand le nœud actif est mort : l'écriture échouait sur
    le réplica en lecture seule, avant même d'atteindre la promotion qui aurait
    levé ce verrou. La trace est désormais écrite à la fin, une fois la base
    redevenue inscriptible.
    """
    current_active = OrionHANode.objects.filter(is_current_active=True).first()
    steps = []
    dns_payload = {}

    try:
        steps.append('Validation du serveur cible')
        validate_failover_target(target_node)

        steps.append('Promotion base de données')
        _promote_database_to_primary()

        # Avant le marquage du nœud actif, à dessein : si le trafic ne peut pas
        # suivre, le cluster reste officiellement sur l'ancien nœud, là où les
        # domaines pointent encore. Mieux vaut une bascule refusée qu'un nœud
        # déclaré actif que personne ne joint.
        steps.append('Redirection du trafic (DNS Cloudflare)')
        dns_payload = _update_dns_or_cloudflare(target_node)

        steps.append('Marquage serveur actif')
        set_active_node(target_node)

    except Exception as exc:
        try:
            _enregistrer_evenement(
                event_type=event_type,
                status='failed',
                from_node=current_active,
                to_node=target_node,
                started_by=started_by,
                reason=reason,
                steps=steps,
                result_payload={'dns': dns_payload},
                error_message=str(exc),
            )
        except Exception:
            # Base injoignable ou encore en lecture seule : on laisse remonter
            # la cause réelle plutôt que de la masquer derrière un échec
            # d'écriture d'audit.
            pass
        raise

    steps.append('Finalisation')
    return _enregistrer_evenement(
        event_type=event_type,
        status='success',
        from_node=current_active,
        to_node=target_node,
        started_by=started_by,
        reason=reason,
        steps=steps,
        result_payload={'dns': dns_payload},
    )
