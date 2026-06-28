"""
ERP BTP Starter — Configuration principale Django
"""
import os
from pathlib import Path
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY', default='django-insecure-erp-btp-dev-key-change-in-production')
DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1').split(',')

# ─── Applications ─────────────────────────────────────────────────────────────
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
]

THIRD_PARTY_APPS = [
    'crispy_forms',
    'crispy_bootstrap5',
    'widget_tweaks',
    'django_filters',
    'django_extensions',
    'simple_history',
    'rest_framework',
    'corsheaders',
    'import_export',
]

LOCAL_APPS = [
    'apps.core',
    'apps.private_saas.apps.PrivateSaaSConfig',
    'apps.accounts',
    'apps.access_control',
    'apps.crm',
    'apps.sales',
    'apps.accounting',
    'apps.purchases',
    'apps.inventory',
    'apps.documents',
    'apps.hr',
    'apps.payroll',
    'apps.support',
    'apps.workflow',
    'apps.portals',
    'apps.btp',
    'apps.ecommerce',
    'apps.commerce',
    'apps.production',
    'apps.audio',
    'apps.bi',
    'apps.api',
    'apps.websites',
    'apps.dashboard',
    'apps.translations',
    'apps.lunea.apps.LuneaConfig',

]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ─── Middleware ────────────────────────────────────────────────────────────────
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'simple_history.middleware.HistoryRequestMiddleware',
    'apps.core.middleware.BrandContextMiddleware',
    'apps.core.middleware.CompanyMiddleware',
    'apps.core.middleware.AuditLogMiddleware',
    'apps.translations.middleware.OrionLanguageMiddleware',
    # Résolution domaine → site web public (doit être après les middlewares ERP)
    'apps.websites.middleware.WebsiteResolverMiddleware',
]

ROOT_URLCONF = 'erp_btp.urls'

# ─── Templates ────────────────────────────────────────────────────────────────
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.core.context_processors.erp_context',
                'apps.core.context_processors.navigation_context',
                'apps.access_control.context_processors.available_modules',
                'apps.access_control.context_processors.current_company_permissions',
                'apps.core.context_processors.brand_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'erp_btp.wsgi.application'

# ─── Base de données MySQL (XAMPP) ────────────────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': config('DB_ENGINE', default='django.db.backends.mysql'),
        'NAME': config('DB_NAME', default='erp_btp'),
        'USER': config('DB_USER', default='root'),
        'PASSWORD': config('DB_PASSWORD', default=''),
        'HOST': config('DB_HOST', default='127.0.0.1'),
        'PORT': config('DB_PORT', default='3306'),
        'OPTIONS': {
            'charset': 'utf8mb4',
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

# ─── Routage multi-base (une base dédiée par entreprise) ──────────────────────
DATABASE_ROUTERS = ['apps.core.db_router.CompanyDatabaseRouter']

# Les bases entreprises sont chargées dynamiquement au démarrage via AppConfig

# ─── Auth ─────────────────────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

# ─── Internationalisation ─────────────────────────────────────────────────────
LANGUAGE_CODE = 'fr'
TIME_ZONE = 'Europe/Paris'
USE_I18N = True
USE_L10N = True
USE_TZ = True

LANGUAGES = [
    ('fr', 'Français'),
    ('en', 'English'),
    ('es', 'Español'),
    ('de', 'Deutsch'),
    ('it', 'Italiano'),
    ('nl', 'Nederlands'),
    ('pt', 'Português'),
]

LOCALE_PATHS = [BASE_DIR / 'locale']

# ─── Fichiers statiques ───────────────────────────────────────────────────────
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ─── SaaS Privé Multi-Entreprises ────────────────────────────────────────────
ORION_PRIVATE_SAAS_MODE       = True
ORION_PUBLIC_SIGNUP_ENABLED   = False
ORION_SUPER_ADMIN_REQUIRED    = True

# ─── Gestion des domaines Orion ERP ──────────────────────────────────────────
# IP publique du serveur Orion ERP (enregistrement A des domaines racine)
ORION_PUBLIC_IP = config('ORION_PUBLIC_IP', default='0.0.0.0')
# CNAME pour les sous-domaines et domaines www
ORION_SITES_CNAME = config('ORION_SITES_CNAME', default='sites.orion-erp.com')
# CNAME pour l'ERP
ORION_ERP_CNAME = config('ORION_ERP_CNAME', default='erp.orion-erp.com')
# CNAME pour le portail client
ORION_CLIENT_PORTAL_CNAME = config('ORION_CLIENT_PORTAL_CNAME', default='client.orion-erp.com')
# Préfixe du token de vérification de propriété
ORION_DOMAIN_VERIFICATION_PREFIX = 'orion-verification'
# Domaine de prévisualisation temporaire (avant connexion d'un domaine réel)
ORION_TEMP_DOMAIN_SUFFIX = config('ORION_TEMP_DOMAIN_SUFFIX', default='orion-sites.local')

# ─── Crispy Forms ─────────────────────────────────────────────────────────────
CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK = 'bootstrap5'

# ─── Email ────────────────────────────────────────────────────────────────────
EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='localhost')
EMAIL_PORT = config('EMAIL_PORT', default=25, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=False, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')

# ─── DRF ──────────────────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 25,
}

# ─── CORS ─────────────────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://127.0.0.1:3000',
]

# ─── Session ──────────────────────────────────────────────────────────────────
SESSION_COOKIE_AGE = 86400 * 30  # 30 jours
SESSION_SAVE_EVERY_REQUEST = True

# ─── Messages ─────────────────────────────────────────────────────────────────
MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'

# ─── Logging ──────────────────────────────────────────────────────────────────
import os as _os
_LOG_DIR = BASE_DIR / 'logs'
_LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {module} — {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': str(_LOG_DIR / 'orion.log'),
            'maxBytes': 5 * 1024 * 1024,
            'backupCount': 5,
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'orion': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

# ─── Sécurité ─────────────────────────────────────────────────────────────────
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SESSION_COOKIE_HTTPONLY = True

# ─── Répertoires ──────────────────────────────────────────────────────────────
BACKUP_DIR = BASE_DIR / 'backups'
LOG_DIR = BASE_DIR / 'logs'
