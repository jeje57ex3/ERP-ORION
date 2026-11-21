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


def check_media_derriere_django():
    """Nginx sert-il /media/ depuis le disque, en contournant la politique ?

    `apps/core/media_access.py` applique sous /media/ un refus par défaut
    qui tient hors de ce préfixe les bulletins de paie, les relevés
    bancaires, les factures fournisseurs et les photos prises chez des
    clients. Un bloc `location /media/ { alias ...; }` sert ces fichiers
    depuis le disque : la requête n'atteint jamais la politique, et une URL
    devinée suffit, sans compte.

    POURQUOI CE CONTRÔLE EXISTE PLUTÔT QU'UNE SIMPLE CORRECTION. Deux des
    trois gabarits du dépôt portaient ce défaut, et ils sont corrigés — mais
    **une mise à jour ne réécrit pas `/etc/nginx`**. Sur une machine déjà
    installée, le fichier fautif reste en place, et personne ne pense à
    relire une configuration qu'on n'a pas touchée depuis l'installation.
    Ce contrôle lit celle qui est RÉELLEMENT en place.

    N'EMPÊCHE PAS LA MISE À JOUR. Le défaut est antérieur à elle et la
    mise à jour ne l'aggrave pas ; bloquer laisserait l'ERP sur du code plus
    ancien, sans rien fermer. On le dit, fort, à chaque mise à jour.
    """
    try:
        from apps.domain_diagnostics.nginx_checks import \
            media_servi_depuis_le_disque
        fautifs = media_servi_depuis_le_disque()
    except Exception as exc:
        # Un contrôle qui tombe ne doit pas arrêter une mise à jour, mais
        # ne doit pas non plus se taire : ne rien dire se lirait comme
        # « vérifié, tout va bien ».
        return {
            'ok': True,
            'avertissement': True,
            'message': ('Impossible de vérifier la configuration Nginx de '
                        f'/media/ ({exc}). À contrôler à la main : un '
                        '« alias » sous location /media/ publierait les '
                        'bulletins de paie sans authentification.'),
        }

    if fautifs:
        details = ', '.join('%s (%s)' % (item['fichier'], item['directive'])
                            for item in fautifs)
        return {
            'ok': True,
            'avertissement': True,
            'message': (
                'Nginx sert /media/ DEPUIS LE DISQUE : ' + details + '. Les '
                'fichiers téléversés sont donc accessibles sans compte, y '
                'compris les bulletins de paie, relevés bancaires et '
                'factures fournisseurs que la politique de '
                'apps/core/media_access.py tient hors de /media/. '
                'Remplacez ce bloc par le « proxy_pass » du gabarit corrigé '
                '(deployment/quick-install/nginx.conf.tmpl), puis '
                'rechargez Nginx.'),
        }

    return {'ok': True, 'message': '/media/ passe bien par Django'}


def run_pre_update_config_checks():
    """Ce qui doit être vrai AVANT de redémarrer sur le nouveau code.

    Ne touche ni à la base ni aux fichiers : seulement aux réglages et à la
    configuration en place. Un contrôle qui échoue arrête la mise à jour, et
    l'ERP continue de tourner sur l'ancien code ; un contrôle qui avertit la
    laisse passer en le disant.
    """
    controles = [
        check_secret_key(),
        check_allowed_hosts(),
        check_media_derriere_django(),
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
