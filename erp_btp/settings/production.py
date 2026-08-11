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
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

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
