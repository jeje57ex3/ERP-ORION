"""
Orion ERP — Configuration tests (rapide, sans MySQL)
"""
from .base import *

DEBUG = True

# Hashers rapides pour les tests
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Email en mémoire
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# Base de données de test SQLite (évite MySQL pour les tests unitaires)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

DATABASE_ROUTERS = []

# Désactiver les logs pendant les tests
LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'handlers': {'null': {'class': 'logging.NullHandler'}},
    'root': {'handlers': ['null']},
}

# Whitenoise ne fonctionne pas en mode test SQLite
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'
