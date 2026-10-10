from django.apps import AppConfig


class ConfiguratorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.configurator'
    label = 'configurator'
    verbose_name = 'Configurateur métier'
