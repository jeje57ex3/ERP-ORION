from django.conf import settings
from django.db import connection
from django.http import JsonResponse, HttpResponseForbidden
from django.utils import timezone


def _check_ha_secret(request):
    expected = getattr(settings, 'ORION_HA_SECRET', '')
    received = request.headers.get('X-Orion-HA-Secret', '')
    if not expected or expected == 'CHANGE_ME':
        return False
    return received == expected


def _check_database():
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        return 'ok'
    except Exception:
        return 'error'


def _replication_state():
    """État réel de la réplication, et non le rôle déclaré dans le .env.

    `replication_lag_seconds` était auparavant codé en dur à None, ce qui
    rendait inertes tous les garde-fous qui en dépendent : la validation de
    cible comme la règle de retour laissent passer un retard inconnu. Sans
    mesure réelle, elles ne protégeaient donc de rien.

    `read_only` sert à repérer un ancien principal qui revient sans avoir été
    rétrogradé. Il reste à None quand l'information n'est pas disponible :
    « inconnu » ne doit jamais être confondu avec « inscriptible ».
    """
    etat = {'read_only': None, 'replication_lag_seconds': None, 'is_replica': False}

    with connection.cursor() as cursor:
        try:
            cursor.execute('SELECT @@global.read_only')
            etat['read_only'] = bool(int(cursor.fetchone()[0]))
        except Exception:
            pass

        # MySQL 8.0.22 a renommé SHOW SLAVE STATUS en SHOW REPLICA STATUS, et
        # les colonnes avec. MariaDB ne connaît que l'ancienne forme : les deux
        # sont tentées, l'une des deux échoue toujours.
        for requete in ('SHOW REPLICA STATUS', 'SHOW SLAVE STATUS'):
            try:
                cursor.execute(requete)
                colonnes = [c[0] for c in cursor.description]
                ligne = cursor.fetchone()
            except Exception:
                continue
            if not ligne:
                continue
            donnees = dict(zip(colonnes, ligne))
            etat['is_replica'] = True
            for champ in ('Seconds_Behind_Source', 'Seconds_Behind_Master'):
                if donnees.get(champ) is not None:
                    etat['replication_lag_seconds'] = int(donnees[champ])
                    break
            break

    return etat


def _build_payload():
    db_status = _check_database()
    replication = _replication_state()

    if replication['is_replica']:
        database_role = 'replica'
    elif replication['read_only']:
        database_role = 'read_only'
    else:
        database_role = getattr(settings, 'ORION_NODE_ROLE', 'primary')

    return {
        'status': 'healthy' if db_status == 'ok' else 'down',
        'node_id': getattr(settings, 'ORION_NODE_ID', 'orion-primary'),
        'role': getattr(settings, 'ORION_NODE_ROLE', 'primary'),
        'priority': getattr(settings, 'ORION_NODE_PRIORITY', 1),
        'region': getattr(settings, 'ORION_NODE_REGION', 'local'),
        'database': db_status,
        'database_role': database_role,
        'read_only': replication['read_only'],
        'replication_lag_seconds': replication['replication_lag_seconds'],
        'media': 'unknown',
        'redis': 'unknown',
        'celery': 'unknown',
        'app_version': '',
        'git_commit': '',
        'timestamp': timezone.now().isoformat(),
    }


def health_view(request):
    if not _check_ha_secret(request):
        return HttpResponseForbidden('Forbidden')
    return JsonResponse(_build_payload())


def public_health_view(request):
    payload = _build_payload()
    return JsonResponse({
        'status': payload['status'],
        'node_id': payload['node_id'],
        'role': payload['role'],
    })
