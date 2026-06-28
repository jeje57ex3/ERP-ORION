from django.urls import path

from apps.dashboard_widgets import api

app_name = "dashboard_widgets"

urlpatterns = [
    path("api/v1/dashboard/widgets/", api.dashboard_widgets_api, name="api_widgets"),
]
