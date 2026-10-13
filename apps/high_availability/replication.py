"""État de la réplication MySQL, relevé et consigné.

Jusqu'ici `OrionHAReplicationStatus` n'était écrit par personne : la page
Réplication affichait un tableau que rien ne remplissait, et
`replication_lag_seconds` était codé en dur à None dans le bilan de santé —
ce qui rendait inertes TOUS les garde-fous de retard, celui de la validation
de cible comme celui du retour de main. Ils laissaient passer un retard
inconnu, c'est-à-dire n'importe quel retard.

Sans réplication, la haute disponibilité est décorative : une bascule
promouvrait une base dépourvue des données de l'autre site.

MySQL 8.0.22 a renommé `SHOW SLAVE STATUS` en `SHOW REPLICA STATUS` **et ses
colonnes** ; MariaDB ne connaît que les anciens noms. L'analyse accepte donc
les deux familles, et la lecture reste une fonction pure — éprouvable sans
serveur ni réplication en place, ce qui est la seule façon raisonnable de
tester ce code.
"""

from django.db import connection
from django.utils import timezone

# Chaque champ accepte le nom MySQL 8 puis l'ancien, dans cet ordre.
COLONNES = {
    'io_running': ('Replica_IO_Running', 'Slave_IO_Running'),
    'sql_running': ('Replica_SQL_Running', 'Slave_SQL_Running'),
    'lag': ('Seconds_Behind_Source', 'Seconds_Behind_Master'),
    'log_file': ('Source_Log_File', 'Master_Log_File'),
    'log_pos': ('Read_Source_Log_Pos', 'Read_Master_Log_Pos'),
    'source_host': ('Source_Host', 'Master_Host'),
    'io_error': ('Last_IO_Error',),
    'sql_error': ('Last_SQL_Error',),
}


def _premiere(donnees, noms):
    for nom in noms:
        if nom in donnees and donnees[nom] not in (None, ''):
            return donnees[nom]
    return None


def _vrai(valeur):
    """« Yes » / « Oui » / 1 / True, selon le serveur et sa langue."""
    if isinstance(valeur, bool):
        return valeur
    return str(valeur or '').strip().lower() in ('yes', 'oui', '1', 'true', 'on')


def parse_replica_status(donnees):
    """Normalise une ligne de SHOW REPLICA STATUS en dictionnaire stable.

    `donnees` associe un nom de colonne à sa valeur. Un dictionnaire vide
    signifie « ce serveur n'est pas un réplica », ce qui n'est pas une erreur :
    c'est l'état normal du serveur principal.
    """
    if not donnees:
        return {
            'is_replica': False,
            'io_running': False,
            'sql_running': False,
            'lag_seconds': None,
            'log_file': '',
            'log_position': '',
            'source_host': '',
            'errors': [],
            'status': 'standalone',
        }

    io_running = _vrai(_premiere(donnees, COLONNES['io_running']))
    sql_running = _vrai(_premiere(donnees, COLONNES['sql_running']))

    lag_brut = _premiere(donnees, COLONNES['lag'])
    try:
        # NULL signifie « réplication arrêtée », pas « aucun retard » : le
        # confondre avec 0 ferait passer une réplication morte pour parfaite.
        lag = int(lag_brut) if lag_brut is not None else None
    except (TypeError, ValueError):
        lag = None

    erreurs = [
        str(donnees[nom]).strip()
        for groupe in ('io_error', 'sql_error')
        for nom in COLONNES[groupe]
        if donnees.get(nom)
    ]

    if erreurs or not (io_running and sql_running):
        statut = 'error'
    elif lag is None:
        statut = 'warning'
    else:
        statut = 'ok'

    return {
        'is_replica': True,
        'io_running': io_running,
        'sql_running': sql_running,
        'lag_seconds': lag,
        'log_file': str(_premiere(donnees, COLONNES['log_file']) or ''),
        'log_position': str(_premiere(donnees, COLONNES['log_pos']) or ''),
        'source_host': str(_premiere(donnees, COLONNES['source_host']) or ''),
        'errors': erreurs,
        'status': statut,
    }


def lire_status_local():
    """Interroge le serveur local et retourne l'état normalisé.

    Les deux formes de la commande sont tentées : l'une des deux échoue
    toujours, selon qu'on est sur MySQL 8 ou MariaDB. Un moteur sans
    réplication du tout (SQLite en test) retourne l'état « autonome ».
    """
    donnees = {}
    lecture_seule = None

    with connection.cursor() as cursor:
        try:
            cursor.execute('SELECT @@global.read_only')
            lecture_seule = bool(int(cursor.fetchone()[0]))
        except Exception:
            pass

        for requete in ('SHOW REPLICA STATUS', 'SHOW SLAVE STATUS'):
            try:
                cursor.execute(requete)
                colonnes = [c[0] for c in cursor.description]
                ligne = cursor.fetchone()
            except Exception:
                continue
            if ligne:
                donnees = dict(zip(colonnes, ligne))
            break

    etat = parse_replica_status(donnees)
    etat['read_only'] = lecture_seule
    return etat


def appliquer_etat(node, etat):
    """Consigne l'état de réplication d'un nœud, pour la page Réplication.

    Appelé à chaque bilan de santé : c'est le seul moment où l'on dispose de
    l'état réel d'un serveur distant, qui ne peut pas s'interroger lui-même
    depuis ici.
    """
    from apps.high_availability.models import OrionHAReplicationStatus

    etat = etat or {}
    statut = etat.get('status') or 'unknown'

    objet, _ = OrionHAReplicationStatus.objects.update_or_create(
        node=node,
        defaults={
            'database_status': statut,
            'io_thread_running': bool(etat.get('io_running')),
            'sql_thread_running': bool(etat.get('sql_running')),
            'seconds_behind_primary': etat.get('lag_seconds'),
            'primary_log_file': (etat.get('log_file') or '')[:180],
            'primary_log_position': str(etat.get('log_position') or '')[:80],
            'payload': {**etat, 'releve_a': timezone.now().isoformat()},
        },
    )
    return objet
