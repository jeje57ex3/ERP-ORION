"""
Orion ERP — Configuration production (sécurité renforcée)
"""
from .base import *
import os

from django.core.exceptions import ImproperlyConfigured

DEBUG = False

# ─── La clef de signature ─────────────────────────────────────────────────────
#
# ON REFUSE DE DÉMARRER PLUTÔT QUE DE SIGNER AVEC LA CLEF DU DÉPÔT.
#
# `base.py` donne à `SECRET_KEY` une valeur de repli, qui convient au
# développement. Sans contrôle ici, un `.env` sans `SECRET_KEY` —
# oubli, fichier écrasé par une réinstallation, variable mal nommée —
# fait démarrer la production avec cette valeur. Tout ce que la clef
# signe devient alors forgeable par quiconque a lu ce dépôt : les
# cookies de session d'abord, c'est-à-dire se connecter en tant que
# n'importe qui sans mot de passe.
#
# `manage.py check --deploy` le dit (security.W009), mais personne ne
# lit cette sortie au démarrage d'un service systemd : le site
# fonctionne, les pages s'affichent, et rien ne signale que la clef est
# publique.
#
# Un service qui refuse de démarrer se voit dans la minute. Une clef par
# défaut ne se voit jamais. C'est le sens dans lequel il faut se tromper.
# LE CONTROLE NE PORTE QUE SUR LE MODULE REELLEMENT ACTIF.
#
# `DJANGO_SETTINGS_MODULE` designe les reglages sous lesquels le
# processus tourne : les quatre unites systemd le posent a
# « erp_btp.settings.production », et `manage.py --settings=X` l'ecrit
# aussi (`handle_default_options`, django/core/management/base.py:92).
#
# Sans cette condition, le seul fait d'IMPORTER ce module pour
# l'inspecter faisait lever -- ce que deux tests font, legitimement, pour
# verifier que la production n'emploie pas un cache par processus. Un
# controle qui empeche de verifier la configuration n'est pas un
# durcissement, c'est une gene : ce qu'on protege, c'est le processus qui
# SERT les requetes, pas celui qui lit le fichier.
_EST_ACTIF = os.environ.get('DJANGO_SETTINGS_MODULE') == __name__

if _EST_ACTIF and (not SECRET_KEY
                   or SECRET_KEY.startswith('django-insecure-')):
    raise ImproperlyConfigured(
        'SECRET_KEY absente ou laissée à la valeur de développement. '
        'Renseignez-la dans /opt/orion/backend/.env avec au moins 50 '
        'caractères aléatoires — par exemple la sortie de '
        '`python -c "import secrets; print(secrets.token_urlsafe(64))"`. '
        'Cette clef signe les cookies de session : avec celle du dépôt, '
        'n’importe qui peut se forger une session d’administrateur.'
    )

if _EST_ACTIF and len(SECRET_KEY) < 50:
    raise ImproperlyConfigured(
        f'SECRET_KEY ne fait que {len(SECRET_KEY)} caractères. Django en '
        'demande au moins 50 : en dessous, la clef est à portée d’une '
        'recherche exhaustive, et elle signe les cookies de session.'
    )

# ─── Les hôtes admis ──────────────────────────────────────────────────────────
#
# Obligatoire en production — configurer via variable d'environnement.
ALLOWED_HOSTS = [h.strip() for h in
                 config('ALLOWED_HOSTS', default='').split(',') if h.strip()]

# `ALLOWED_HOSTS = ['*']` MÉRITE AU MOINS QU'ON LE SIGNALE.
#
# Il laisse Django accepter n'importe quel en-tête « Host », ce qui ouvre
# l'empoisonnement de cache et les liens de réinitialisation de mot de
# passe pointant vers un domaine choisi par l'attaquant. On ne refuse pas
# de démarrer — l'appliance se visite par son adresse IP avant qu'un
# domaine ne pointe dessus, et ce réglage est alors le seul praticable —
# mais on l'écrit dans le journal, pour que ce ne soit pas un oubli
# silencieux.
if '*' in ALLOWED_HOSTS:
    import logging

    logging.getLogger('orion').warning(
        'ALLOWED_HOSTS contient « * » : Django accepte n’importe quel '
        'en-tête Host. À restreindre dès qu’un domaine est en place.')

# ─── Sécurité HTTPS ───────────────────────────────────────────────────────────
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
# Configurables (def: True) : un cookie "Secure" n'est envoyé par le
# navigateur que sur HTTPS — en HTTP nu (accès par IP avant configuration
# TLS sur l'appliance Proxmox), le cookie CSRF ne reviendrait jamais et
# toute soumission de formulaire (dont /setup/) échouerait avec un 403.
SESSION_COOKIE_SECURE = config('SESSION_COOKIE_SECURE', default=True, cast=bool)
CSRF_COOKIE_SECURE = config('CSRF_COOKIE_SECURE', default=True, cast=bool)
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False

X_FRAME_OPTIONS = 'DENY'

SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
# Configurable (def: True) : l'appliance Proxmox le désactive dans son .env
# initial pour que l'assistant de premier accès (/setup/) reste joignable en
# HTTP nu avant que TLS (certbot ou Cloudflare Tunnel) ne soit configuré.
SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=True, cast=bool)
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# ─── Fichiers statiques production ────────────────────────────────────────────
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ─── Email SMTP production ────────────────────────────────────────────────────
#
# Cette ligne forcait le SMTP de Django, donc les valeurs EMAIL_* du .env, et
# elle ecrasait la cle EMAIL_BACKEND que le meme .env documentait -- la
# rendant inoperante. base.py installe desormais apps.core.mail, qui lit les
# reglages de /orion-admin/courriels/ et retombe sur le SMTP du .env tant
# qu'aucun n'est actif. Le comportement par defaut est donc inchange, et il
# devient reglable sans terminal.
#
# Rien n'est redeclare ici : base.py suffit. La section reste pour que la
# recherche de « EMAIL » dans ce fichier mene a cette explication.

# ─── Logging production (fichiers rotatifs) ───────────────────────────────────
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {name} {module}:{lineno} — {message}',
            'style': '{',
        },
        'simple': {
            'format': '[{levelname}] {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file_info': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': str(LOG_DIR / 'orion.log'),
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 10,
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
        'file_error': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': str(LOG_DIR / 'errors.log'),
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 10,
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file_info', 'file_error'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['file_error'],
            'level': 'WARNING',
            'propagate': False,
        },
        'orion': {
            'handlers': ['file_info', 'file_error'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# ─── Sessions sécurisées ──────────────────────────────────────────────────────
SESSION_COOKIE_AGE = 86400 * 7  # 7 jours en production

# ─── Cache partage entre les workers ─────────────────────────────────────────
#
# Redis tourne deja sur cette machine, et il ne servait qu'a Celery :
# orion-backend.service l'attend au demarrage
# (« wait_for_port.sh 127.0.0.1 6379 60 », sans le prefixe « - », donc
# bloquant). Le serveur de cache etait donc paye en memoire et personne ne lui
# parlait, pendant que les trois workers gunicorn tenaient chacun son
# LocMemCache. base.py detaille les trois defauts que cela provoquait --
# jetons de reinitialisation perdus, limites de debit triplees,
# invalidations recues par un worker sur trois.
#
# BASE 1, ET PAS 0, et ce n'est pas un detail : Celery tient sa file de taches
# dans la base 0 (CELERY_BROKER_URL ci-dessus). Partager la base melerait le
# cache applicatif et la file, et un vidage de cache -- operation anodine --
# effacerait des taches en attente.
#
# KEY_PREFIX : un prefixe commun permet de reconnaitre les cles de l'ERP si un
# jour la base est partagee avec autre chose, et de les vider seules.
#
# Pas d'IGNORE_EXCEPTIONS : le backend Redis integre a Django n'en a pas, et
# c'est aussi bien. Un cache muet qui avale ses erreurs transformerait une
# panne de Redis en comportements incomprehensibles -- limites de debit
# inoperantes, jetons introuvables -- la ou une erreur franche se diagnostique.
# Redis est de toute facon deja un prerequis bloquant au demarrage.
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': config('CACHE_URL', default='redis://127.0.0.1:6379/1'),
        'KEY_PREFIX': 'orion',
    }
}
