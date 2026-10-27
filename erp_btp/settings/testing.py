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

# Désactiver les logs pendant les tests.
#
# `disable_existing_loggers` est à False, comme dans development.py et
# production.py, et ce n'est pas un détail de confort.
#
# À True, tout logger déjà créé passe à `disabled = True` dès que
# `dictConfig` est rappelé — et il l'est : visiter
# /admin/django_celery_beat/periodictask/add/ fait appeler `django.setup()`
# une seconde fois par le correctif Django de Celery
# (celery/fixups/django.py), donc `configure_logging`, donc `dictConfig`.
#
# Conséquence mesurée : tout test employant `caplog` cessait de voir les
# messages dès qu'un test précédent avait visité cette page d'admin. Le
# parcours complet de l'ERP l'a révélé en faisant tomber
# test_une_source_en_echec_est_journalisee_et_non_avalee — un test juste,
# rendu faux par l'ordre d'exécution.
#
# Le handler nul suffit à garder les tests silencieux ; désactiver les
# loggers par-dessus n'apportait rien et rendait la suite dépendante de son
# ordre.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'null': {'class': 'logging.NullHandler'}},
    'root': {'handlers': ['null']},
}

# Whitenoise ne fonctionne pas en mode test SQLite
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'
