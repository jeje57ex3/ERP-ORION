from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'
    verbose_name = 'Core ERP'

    def ready(self):
        import apps.core.signals  # noqa
        # Charge toutes les bases entreprises actives dans settings.DATABASES
        try:
            from .company_database_service import load_all_company_databases
            load_all_company_databases()
        except Exception:
            pass  # DB pas encore prête (première migration)
