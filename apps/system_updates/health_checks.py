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


def check_secret_key():
    """La clef de signature est-elle une vraie clef ?

    `erp_btp/settings/production.py` refuse de démarrer avec la valeur
    de repli de `base.py`, qui est publiée dans ce dépôt. Le contrôle
    est répété ici parce que les réglages sont déjà chargés quand ce
    code tourne : ce qu'on vérifie, c'est la configuration de
    l'installation **avant** de redémarrer dessus.
    """
    cle = getattr(settings, 'SECRET_KEY', '') or ''

    if not cle or cle.startswith('django-insecure-'):
        return {
            'ok': False,
            'message': (
                'SECRET_KEY absente ou laissée à la valeur de '
                'développement, qui figure dans le dépôt. Elle signe les '
                'cookies de session : avec celle-là, n’importe qui peut se '
                'forger une session d’administrateur. Renseignez-la dans '
                '/opt/orion/backend/.env avant de mettre à jour — sans '
                'quoi le service refusera de redémarrer.'),
        }

    if len(cle) < 50:
        return {
            'ok': False,
            'message': (
                f'SECRET_KEY ne fait que {len(cle)} caractères ; Django en '
                'demande au moins 50. En dessous, la clef qui signe les '
                'cookies de session est à portée d’une recherche '
                'exhaustive.'),
        }

    return {'ok': True, 'message': 'SECRET_KEY conforme'}


def check_allowed_hosts():
    """Les hôtes admis sont-ils restreints ?

    `ALLOWED_HOSTS = ['*']` laisse Django accepter n'importe quel
    en-tête « Host », ce qui ouvre l'empoisonnement de cache et les
    liens de réinitialisation de mot de passe pointant vers un domaine
    choisi par l'attaquant.

    N'EMPÊCHE PAS LA MISE À JOUR : l'appliance se visite par son adresse
    IP avant qu'un domaine ne pointe dessus, et ce réglage est alors le
    seul praticable. On le dit, on ne le bloque pas.
    """
    hotes = list(getattr(settings, 'ALLOWED_HOSTS', []) or [])

    if '*' in hotes:
        return {
            'ok': True,
            'avertissement': True,
            'message': (
                'ALLOWED_HOSTS contient « * » : Django accepte n’importe '
                'quel en-tête Host. À restreindre dès qu’un domaine est en '
                'place.'),
        }

    if not hotes:
        return {
            'ok': False,
            'message': (
                'ALLOWED_HOSTS est vide : Django refusera toutes les '
                'requêtes. Renseignez les domaines dans '
                '/opt/orion/backend/.env.'),
        }

    return {'ok': True, 'message': f'{len(hotes)} hôte(s) admis'}


def run_pre_update_config_checks():
    """Ce qui doit être vrai AVANT de redémarrer sur le nouveau code.

    Ne touche ni à la base ni aux fichiers : seulement aux réglages. Un
    contrôle qui échoue arrête la mise à jour, et l'ERP continue de
    tourner sur l'ancien code.
    """
    controles = [
        check_secret_key(),
        check_allowed_hosts(),
    ]
    return {
        'ok': all(item['ok'] for item in controles),
        'checks': controles,
        'messages': [item['message'] for item in controles
                     if not item['ok'] or item.get('avertissement')],
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
