from django.apps import AppConfig


class OrionOpsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.orion_ops'
    verbose_name = 'Orion Ops — Observabilité & Fiabilité'

    def ready(self):
        pass
