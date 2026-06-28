"""
apps/core/db_router.py — Routage multi-base Django
Dirige les requêtes vers la base centrale ou la base dédiée de l'entreprise active.
"""
import threading
from django.conf import settings

_thread_locals = threading.local()


def set_company_db(alias: str | None) -> None:
    """Définit l'alias de base active pour le thread courant."""
    _thread_locals.company_db = alias


def get_company_db() -> str | None:
    """Retourne l'alias de base active pour le thread courant."""
    return getattr(_thread_locals, 'company_db', None)


def clear_company_db() -> None:
    """Efface l'alias de base active (fin de requête)."""
    _thread_locals.company_db = None


# Apps dont les données restent dans la base centrale
CENTRAL_APPS = {
    'core',
    'accounts',
    'access_control',
    'dashboard',
    'private_saas',
    'notifications',
    'translations',
    'api',
    'backups',
    'competitor_intelligence',
    'admin',
    'auth',
    'contenttypes',
    'sessions',
    'messages',
    'staticfiles',
    'simple_history',
    'django_filters',
    'import_export',
    'rest_framework',
}

# Apps dont les données vont dans la base entreprise
COMPANY_APPS = {
    'crm',
    'sales',
    'accounting',
    'purchases',
    'inventory',
    'btp',
    'ecommerce',
    'commerce',
    'production',
    'hr',
    'payroll',
    'documents',
    'websites',
    'support',
    'bi',
    'portals',
    'workflow',
    'audio',
    'reporting',
}


def _app_label(app_label: str) -> str:
    """Normalise le label d'app (supprime le préfixe 'apps.')."""
    return app_label.split('.')[-1] if '.' in app_label else app_label


class CompanyDatabaseRouter:
    """
    Router Django pour l'architecture multi-tenant Orion ERP.

    - Modèles centraux (core, auth, dashboard…) → base 'default'
    - Modèles métier (crm, sales, btp…) → base dédiée de l'entreprise active
    - Si aucune base entreprise n'est définie, fallback sur 'default'
    """

    def _resolve(self, app_label: str):
        """Retourne l'alias cible pour un label d'app."""
        label = _app_label(app_label)
        if label in CENTRAL_APPS:
            return 'default'
        if label in COMPANY_APPS:
            alias = get_company_db()
            return alias if alias else 'default'
        return None  # laisser Django décider

    def db_for_read(self, model, **hints):
        return self._resolve(model._meta.app_label)

    def db_for_write(self, model, **hints):
        return self._resolve(model._meta.app_label)

    def allow_relation(self, obj1, obj2, **hints):
        """Autorise les relations entre objets (y compris cross-base)."""
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Contrôle où les migrations s'exécutent.

        - Sur 'default' : apps centrales toujours ; apps métier seulement si
          aucune base entreprise n'est encore enregistrée (mode dev/mono-base)
        - Sur une base entreprise (company_*) : uniquement les apps métier
        """
        label = _app_label(app_label)

        if db == 'default':
            if label in CENTRAL_APPS:
                return True
            if label in COMPANY_APPS:
                # Si des bases entreprises existent, elles gèrent les apps métier
                company_dbs_exist = any(
                    k.startswith('company_') for k in settings.DATABASES
                )
                return not company_dbs_exist
            return None

        if db.startswith('company_'):
            # Base entreprise : autoriser uniquement les apps métier
            return label in COMPANY_APPS

        return None
