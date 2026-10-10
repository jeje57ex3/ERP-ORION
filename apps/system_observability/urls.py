from django.urls import path
from . import views

app_name = 'system_observability'

urlpatterns = [
    path('', views.observability_dashboard, name='dashboard'),
    path('relancer/', views.run_checks_now, name='run_now'),
    path('historique/<str:check_type>/', views.check_history_view, name='check_history'),
    path('alerte/<int:pk>/acquitter/', views.acknowledge_alert, name='acknowledge'),
    path('api/statut/', views.api_status, name='api_status'),
]
