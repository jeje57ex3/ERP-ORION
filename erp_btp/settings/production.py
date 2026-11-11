"""
Orion ERP — Configuration production (sécurité renforcée)
"""
from .base import *
import os

DEBUG = False

# Obligatoire en production — configurer via variable d'environnement
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='').split(',')

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
