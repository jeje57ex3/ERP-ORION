from pathlib import Path

from django.conf import settings
from django.db import connection


def check_database():
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        return {'ok': True, 'message': 'Base de données OK'}
    except Exception as exc:
        return {'ok': False, 'message': str(exc)}


def check_static_files():
    static_root = getattr(settings, 'STATIC_ROOT', '')
    if not static_root:
        return {'ok': True, 'message': 'STATIC_ROOT non configuré, ignoré'}
    path = Path(static_root)
    return {
        'ok': path.exists(),
        'message': 'STATIC_ROOT existe' if path.exists() else 'STATIC_ROOT introuvable',
    }


def run_post_update_health_checks():
    checks = [
        check_database(),
        check_static_files(),
    ]
    return {
        'ok': all(item['ok'] for item in checks),
        'checks': checks,
    }
