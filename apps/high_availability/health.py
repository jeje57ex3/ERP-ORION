from urllib.parse import urlsplit

import requests
from django.conf import settings
from django.db import connection
from django.http import JsonResponse, HttpResponseForbidden
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt


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
    """Etat reel de la replication, delegue au module dedie.

    L'analyse vivait ici sous une forme sommaire et non testable : elle ne
    relevait que le retard et la lecture seule, en recopiant la double
    nomenclature MySQL 8 / MariaDB. Elle est desormais dans
    apps/high_availability/replication.py, en fonction pure, et rapporte en
    plus l'etat des fils de replication, la position dans le journal et les
    erreurs -- ce qu'il faut pour alimenter la page Replication.
    """
    from apps.high_availability.replication import lire_status_local

    try:
        return lire_status_local()
    except Exception:
        # Un bilan de sante ne doit jamais echouer a cause de la replication :
        # c'est precisement quand elle va mal qu'on a besoin du bilan.
        return {
            'is_replica': False, 'read_only': None, 'lag_seconds': None,
            'io_running': False, 'sql_running': False, 'log_file': '',
            'log_position': '', 'source_host': '', 'errors': [],
            'status': 'unknown',
        }


def _build_payload():
    db_status = _check_database()
    replication = _replication_state()

    if replication['is_replica']:
        database_role = 'replica'
    elif replication.get('read_only'):
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
        'read_only': replication.get('read_only'),
        'replication_lag_seconds': replication.get('lag_seconds'),
        # Detail complet, consomme par update_node_from_health pour
        # alimenter OrionHAReplicationStatus -- que rien n'ecrivait.
        'replication': replication,
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


@csrf_exempt
def join_check_view(request):
    """Validation réciproque : ce serveur vérifie qu'il joint le serveur source.

    `csrf_exempt` est nécessaire et sans danger : l'appelant est un autre
    serveur, pas un navigateur, et il n'a aucun cookie de session à présenter.
    L'autorisation repose entièrement sur l'en-tête de secret partagé, vérifié
    ci-dessous avant toute action.

    Sans ce contrôle, l'adhésion à la grappe ne prouve qu'un sens de la
    liaison. Or le cas asymétrique est fréquent et redoutable : le serveur
    principal joint le secondaire, l'enregistre, l'affiche « sain » — mais le
    secondaire ne peut pas joindre le principal. Règles de pare-feu
    unilatérales, tunnel sortant seul, DNS interne partiel, routage NAT. Rien
    ne le signale, jusqu'à la bascule où le nouveau serveur actif se retrouve
    incapable de surveiller l'ancien.

    Le candidat sonde donc le source à son tour, avec SON secret, et rapporte
    le résultat.

    Portée volontairement étroite, car ce point fait émettre une requête vers
    une adresse fournie par l'appelant : il exige le secret partagé, n'accepte
    que POST, ne construit que l'URL « /ha/health/ » sur l'hôte donné, borne
    le délai, et ne renvoie que des booléens et l'identifiant du nœud — jamais
    le corps de la réponse obtenue.
    """
    if request.method != 'POST':
        return JsonResponse({'detail': 'POST attendu'}, status=405)
    if not _check_ha_secret(request):
        return HttpResponseForbidden('Forbidden')

    secret = getattr(settings, 'ORION_HA_SECRET', '')
    # Pas de rstrip('/') ici : retirer les barres finales AVANT de chercher
    # « :// » transformait « pas-une-url:// » en « pas-une-url: », recollé
    # ensuite en « https://pas-une-url: » — le contrôle de schéma ci-dessous
    # ne pouvait donc jamais se déclencher. Seuls le schéma et l'hôte sont
    # utilisés de toute façon, le reste est écarté par construction.
    source = (request.POST.get('source_url') or '').strip()

    resultat = {
        'node_id': getattr(settings, 'ORION_NODE_ID', ''),
        'source_url': source,
        'source_reachable': False,
        'secret_match': False,
        'source_node_id': '',
        'detail': '',
    }

    if not source:
        resultat['detail'] = "Aucune adresse source fournie."
        return JsonResponse(resultat, status=400)

    decoupe = urlsplit(source if '://' in source else f'https://{source}')
    if decoupe.scheme not in ('http', 'https') or not decoupe.hostname:
        resultat['detail'] = 'Adresse source illisible.'
        return JsonResponse(resultat, status=400)

    try:
        reponse = requests.get(
            f'{decoupe.scheme}://{decoupe.netloc}/ha/health/',
            headers={'X-Orion-HA-Secret': secret},
            timeout=6,
        )
    except requests.RequestException as exc:
        resultat['detail'] = f'Serveur source injoignable depuis ici : {exc}'
        return JsonResponse(resultat)

    resultat['source_reachable'] = True

    if reponse.status_code == 403:
        resultat['detail'] = (
            'Le serveur source refuse notre secret : ORION_HA_SECRET diffère '
            'entre les deux machines.'
        )
        return JsonResponse(resultat)

    if reponse.status_code != 200:
        resultat['detail'] = (
            f'Le serveur source répond HTTP {reponse.status_code} sur son '
            'point de santé.'
        )
        return JsonResponse(resultat)

    resultat['secret_match'] = True
    try:
        resultat['source_node_id'] = (reponse.json().get('node_id') or '').strip()
    except ValueError:
        resultat['detail'] = 'Réponse du serveur source illisible.'
        return JsonResponse(resultat)

    resultat['detail'] = 'Liaison vérifiée dans les deux sens.'
    return JsonResponse(resultat)


def public_health_view(request):
    payload = _build_payload()
    return JsonResponse({
        'status': payload['status'],
        'node_id': payload['node_id'],
        'role': payload['role'],
    })
