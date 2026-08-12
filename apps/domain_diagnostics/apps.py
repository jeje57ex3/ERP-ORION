from django.apps import AppConfig


class DomainDiagnosticsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.domain_diagnostics'
    label = 'domain_diagnostics'
    verbose_name = 'Diagnostic Domaines & Cloudflare'
