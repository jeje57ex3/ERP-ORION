"""
Orion ERP — Configuration développement local (SQLite, sans MySQL)
"""
from .base import *

DEBUG = True

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db_local.sqlite3',
    }
}

DATABASE_ROUTERS = []

STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'
