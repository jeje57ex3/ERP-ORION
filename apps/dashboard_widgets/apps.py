from django.apps import AppConfig


class DashboardWidgetsConfig(AppConfig):
    name = 'apps.dashboard_widgets'
    verbose_name = 'Dashboard Widgets'

    def ready(self):
        import apps.dashboard_widgets.widgets  # noqa — registers all widgets
