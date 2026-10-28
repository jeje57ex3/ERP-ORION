from django.apps import AppConfig


class SiteCustomizationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.site_customization'
    label = 'site_customization'
    verbose_name = 'Personnalisation des sites'
