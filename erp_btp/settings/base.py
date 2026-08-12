"""
Orion ERP — Configuration de base (partagée tous environnements)
"""
from pathlib import Path
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config('SECRET_KEY', default='django-insecure-erp-btp-dev-key-change-in-production')
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1').split(',')
# [o for o in ... if o] : une valeur d'env vide donne [''] via .split(','),
# pas [] — Django (4_0.E001) rejette cette chaîne vide comme origine sans
# schéma. Se produit en pratique sur l'appliance Proxmox quand aucun domaine
# n'est fourni au déploiement (accès par IP uniquement).
CSRF_TRUSTED_ORIGINS = [o for o in config('CSRF_TRUSTED_ORIGINS', default='').split(',') if o]

# ─── Applications ──────────────────────────────────────────────────────────────
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
    'apps.notifications',
    'apps.translations',
    'apps.backups.apps.BackupsConfig',
    'apps.competitor_intelligence.apps.CompetitorIntelligenceConfig',
    'apps.lunea.apps.LuneaConfig',

    # ── Phase 1 — Modules innovants ───────────────────────────────────────────
    'apps.smart_alerts',
    'apps.smart_automations',
    'apps.audit_compliance',
    'apps.customer_360',

    # ── Phase 2 — Opérations & Documents ─────────────────────────────────────
    'apps.workflow_center',
    'apps.smart_documents',
    'apps.smart_planning',
    'apps.quality_incidents',

    # ── Phase 3 — Intelligence & API ─────────────────────────────────────────
    'apps.orion_assistant',
    'apps.predictive_analytics',
    'apps.api_webhooks',
    'apps.integration_center',

    # ── Phase 4 — Système & Infrastructure ───────────────────────────────────
    'apps.backup_center',
    'apps.system_observability',

    # ── Phase 5 — Modules Métier Spécialisés ─────────────────────────────────
    'apps.siecle_creations',
    'apps.lunea_beauty_profile',
    'apps.btp_smart_site_log',

    # ── Launch — Waitlist & Contact ───────────────────────────────────────────
    'apps.launch',

    # ── Infrastructure — Haute disponibilité ─────────────────────────────────
    'apps.high_availability.apps.HighAvailabilityConfig',

    # ── Système — Mises à jour ────────────────────────────────────────────────
    'apps.system_updates.apps.SystemUpdatesConfig',

    # ── Sites web — Paramètres boutique ──────────────────────────────────────
    'apps.website_shop_settings.apps.WebsiteShopSettingsConfig',

    # ── Intelligence Artificielle ─────────────────────────────────────────────
    'apps.orion_ai.apps.OrionAIConfig',

    # ── Amélioration continue PDCA ────────────────────────────────────────────
    'apps.continuous_improvement.apps.ContinuousImprovementConfig',

    # ── Dashboard Widgets ─────────────────────────────────────────────────────
    'apps.dashboard_widgets.apps.DashboardWidgetsConfig',

    # ── Diagnostic Domaines & Cloudflare ──────────────────────────────────────
    'apps.domain_diagnostics.apps.DomainDiagnosticsConfig',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ─── Middleware ────────────────────────────────────────────────────────────────
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'apps.core.middleware.SetupRequiredMiddleware',
    'apps.core.middleware.MaintenanceModeMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'simple_history.middleware.HistoryRequestMiddleware',
    'apps.core.middleware.CompanyMiddleware',
    'apps.core.middleware.AuditLogMiddleware',
    'apps.translations.middleware.OrionLanguageMiddleware',
    'apps.websites.middleware.WebsiteResolverMiddleware',
    'apps.high_availability.middleware.HAActiveNodeWriteProtectionMiddleware',
    'apps.core.middleware.NoCacheMiddleware',
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
                'django.template.context_processors.i18n',
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

# ─── Base de données ──────────────────────────────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': config('DB_ENGINE', default='django.db.backends.mysql'),
        'NAME': config('DB_NAME', default='orion_core'),
        'USER': config('DB_USER', default='root'),
        'PASSWORD': config('DB_PASSWORD', default=''),
        'HOST': config('DB_HOST', default='127.0.0.1'),
        'PORT': config('DB_PORT', default='3306'),
        'OPTIONS': {
            'charset': 'utf8mb4',
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
        'CONN_MAX_AGE': 60,
    }
}

DATABASE_ROUTERS = ['apps.core.db_router.CompanyDatabaseRouter']

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

# ─── Crispy Forms ─────────────────────────────────────────────────────────────
CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK = 'bootstrap5'

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
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
    },
}

# ─── CORS ─────────────────────────────────────────────────────────────────────
# Filtre les entrées vides (cf. CSRF_TRUSTED_ORIGINS plus haut) : une valeur
# d'env présente mais vide (ex: CORS_ALLOWED_ORIGINS= dans le .env de
# l'appliance Proxmox sans domaine fourni) N'utilise PAS le default ci-dessous
# — decouple ne retombe sur le default que si la clé est absente, pas vide.
CORS_ALLOWED_ORIGINS = [o for o in config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173'
).split(',') if o]

CORS_ALLOW_CREDENTIALS = True

# ─── Stripe ───────────────────────────────────────────────────────────────────
STRIPE_PUBLIC_KEY     = config('STRIPE_PUBLIC_KEY',     default='')
STRIPE_SECRET_KEY     = config('STRIPE_SECRET_KEY',     default='')
STRIPE_WEBHOOK_SECRET = config('STRIPE_WEBHOOK_SECRET', default='')

# ─── Session ──────────────────────────────────────────────────────────────────
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 86400 * 30
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_HTTPONLY = True

# ─── Messages ─────────────────────────────────────────────────────────────────
MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'

# ─── Email ────────────────────────────────────────────────────────────────────
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='no-reply@orion-erp.local')
EMAIL_HOST = config('EMAIL_HOST', default='localhost')
EMAIL_PORT = config('EMAIL_PORT', default=25, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=False, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')

# ─── Upload fichiers ──────────────────────────────────────────────────────────
FILE_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024  # 20 Mo
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024

# ─── Sécurité commune ─────────────────────────────────────────────────────────
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# ─── Répertoires applicatifs ──────────────────────────────────────────────────
BACKUP_DIR = BASE_DIR / config('BACKUP_DIR', default='backups')
LOG_DIR = BASE_DIR / config('LOG_DIR', default='logs')

# ─── SaaS Privé Multi-Entreprises ────────────────────────────────────────────
ORION_PRIVATE_SAAS_MODE       = True
ORION_PUBLIC_SIGNUP_ENABLED   = False
ORION_SUPER_ADMIN_REQUIRED    = True

# ─── Gestion des domaines Orion ERP ──────────────────────────────────────────
ORION_PUBLIC_IP                    = config('ORION_PUBLIC_IP',                   default='0.0.0.0')
ORION_SITES_CNAME                  = config('ORION_SITES_CNAME',                 default='sites.orion-erp.com')
ORION_ERP_CNAME                    = config('ORION_ERP_CNAME',                   default='erp.orion-erp.com')
ORION_CLIENT_PORTAL_CNAME          = config('ORION_CLIENT_PORTAL_CNAME',         default='client.orion-erp.com')
ORION_DOMAIN_VERIFICATION_PREFIX   = 'orion-verification'
ORION_TEMP_DOMAIN_SUFFIX           = config('ORION_TEMP_DOMAIN_SUFFIX',          default='orion-sites.local')

# ─── Haute disponibilité (HA) ─────────────────────────────────────────────────
ORION_HA_ENABLED    = config('ORION_HA_ENABLED',    default=False, cast=bool)

ORION_NODE_ID       = config('ORION_NODE_ID',       default='orion-primary')
ORION_NODE_ROLE     = config('ORION_NODE_ROLE',     default='primary')
ORION_NODE_PRIORITY = config('ORION_NODE_PRIORITY', default=1, cast=int)
ORION_NODE_REGION   = config('ORION_NODE_REGION',   default='local')

ORION_PRIMARY_URL     = config('ORION_PRIMARY_URL',     default='')
ORION_SECONDARY_1_URL = config('ORION_SECONDARY_1_URL', default='')
ORION_SECONDARY_2_URL = config('ORION_SECONDARY_2_URL', default='')
ORION_PUBLIC_ERP_URL  = config('ORION_PUBLIC_ERP_URL',  default='')

ORION_HA_SECRET = config('ORION_HA_SECRET', default='CHANGE_ME')

ORION_HA_FAILOVER_AFTER_SECONDS         = config('ORION_HA_FAILOVER_AFTER_SECONDS',         default=120,  cast=int)
ORION_HA_MAX_REPLICATION_LAG_SECONDS    = config('ORION_HA_MAX_REPLICATION_LAG_SECONDS',    default=10,   cast=int)
ORION_HA_REQUIRE_MANUAL_CONFIRMATION    = config('ORION_HA_REQUIRE_MANUAL_CONFIRMATION',    default=True, cast=bool)
ORION_HA_AUTOMATIC_FAILOVER_ENABLED     = config('ORION_HA_AUTOMATIC_FAILOVER_ENABLED',     default=False, cast=bool)

ORION_HA_SECONDARY_COUNT = 2

ORION_HA_NODE_URLS = {
    'orion-primary':     ORION_PRIMARY_URL,
    'orion-secondary-1': ORION_SECONDARY_1_URL,
    'orion-secondary-2': ORION_SECONDARY_2_URL,
}

# ─── Mises à jour système ─────────────────────────────────────────────────────
ORION_UPDATES_ENABLED = config('ORION_UPDATES_ENABLED', default=False, cast=bool)
ORION_UPDATE_MODE     = config('ORION_UPDATE_MODE',     default='manual')

ORION_PROJECT_ROOT          = config('ORION_PROJECT_ROOT',          default='')
ORION_BACKEND_PATH          = config('ORION_BACKEND_PATH',          default='')
ORION_FRONTEND_SIECLE_PATH  = config('ORION_FRONTEND_SIECLE_PATH',  default='')
ORION_FRONTEND_LUNEA_PATH   = config('ORION_FRONTEND_LUNEA_PATH',   default='')

ORION_GIT_REMOTE = config('ORION_GIT_REMOTE', default='origin')
ORION_GIT_BRANCH = config('ORION_GIT_BRANCH', default='main')

ORION_UPDATE_REQUIRE_BACKUP       = config('ORION_UPDATE_REQUIRE_BACKUP',       default=True,  cast=bool)
ORION_UPDATE_REQUIRE_HEALTH_CHECK = config('ORION_UPDATE_REQUIRE_HEALTH_CHECK', default=True,  cast=bool)
ORION_UPDATE_ALLOW_ROLLBACK       = config('ORION_UPDATE_ALLOW_ROLLBACK',       default=True,  cast=bool)

ORION_UPDATE_BACKUP_COMMAND           = config('ORION_UPDATE_BACKUP_COMMAND',           default='')
ORION_UPDATE_RESTART_COMMAND          = config('ORION_UPDATE_RESTART_COMMAND',          default='')
ORION_UPDATE_CELERY_RESTART_COMMAND   = config('ORION_UPDATE_CELERY_RESTART_COMMAND',   default='')
ORION_UPDATE_CELERY_BEAT_RESTART_COMMAND = config('ORION_UPDATE_CELERY_BEAT_RESTART_COMMAND', default='')

ORION_UPDATE_FRONTEND_BUILD_ENABLED = config('ORION_UPDATE_FRONTEND_BUILD_ENABLED', default=True, cast=bool)
ORION_UPDATE_FRONTEND_BUILD_COMMAND = config('ORION_UPDATE_FRONTEND_BUILD_COMMAND', default='npm run build')

ORION_UPDATE_LOCK_FILE = config('ORION_UPDATE_LOCK_FILE', default='/tmp/orion_update.lock')

# ─── Chiffrement secrets boutique (Fernet) ────────────────────────────────────
ORION_SECRET_ENCRYPTION_KEY = config('ORION_SECRET_ENCRYPTION_KEY', default='')

# ─── Intelligence Artificielle Orion ─────────────────────────────────────────
ORION_AI_ENABLED                        = config('ORION_AI_ENABLED',                        default=False, cast=bool)
ORION_AI_DEFAULT_PROVIDER               = config('ORION_AI_DEFAULT_PROVIDER',               default='openai')
ORION_AI_DEFAULT_MODEL                  = config('ORION_AI_DEFAULT_MODEL',                  default='gpt-4.1-mini')
ORION_AI_MAX_INPUT_CHARS                = config('ORION_AI_MAX_INPUT_CHARS',                default=20000, cast=int)
ORION_AI_MAX_HISTORY_MESSAGES           = config('ORION_AI_MAX_HISTORY_MESSAGES',           default=20,    cast=int)
ORION_AI_LOG_CONVERSATIONS              = config('ORION_AI_LOG_CONVERSATIONS',              default=True,  cast=bool)
ORION_AI_ALLOW_TOOLS                    = config('ORION_AI_ALLOW_TOOLS',                    default=True,  cast=bool)
ORION_AI_ALLOW_DANGEROUS_ACTIONS        = config('ORION_AI_ALLOW_DANGEROUS_ACTIONS',        default=False, cast=bool)
ORION_AI_SYSTEM_NAME                    = config('ORION_AI_SYSTEM_NAME',                    default='Assistant Orion')
ORION_AI_SUPPORT_EMAIL                  = config('ORION_AI_SUPPORT_EMAIL',                  default='')

OPENAI_API_KEY      = config('OPENAI_API_KEY',      default='')
ANTHROPIC_API_KEY   = config('ANTHROPIC_API_KEY',   default='')
LOCAL_AI_BASE_URL   = config('LOCAL_AI_BASE_URL',   default='http://localhost:11434')
