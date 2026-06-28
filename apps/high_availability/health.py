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


def _build_payload():
    db_status = _check_database()
    return {
        'status': 'healthy' if db_status == 'ok' else 'down',
        'node_id': getattr(settings, 'ORION_NODE_ID', 'orion-primary'),
        'role': getattr(settings, 'ORION_NODE_ROLE', 'primary'),
        'priority': getattr(settings, 'ORION_NODE_PRIORITY', 1),
        'region': getattr(settings, 'ORION_NODE_REGION', 'local'),
        'database': db_status,
        'database_role': getattr(settings, 'ORION_NODE_ROLE', 'primary'),
        'replication_lag_seconds': None,
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
