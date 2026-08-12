"""
apps/system_health/urls.py — URLs montées sous /orion-admin/sante-systeme/
"""
from django.urls import path
from . import views

app_name = 'system_health'

_P = 'orion-admin/sante-systeme/'

urlpatterns = [
    # Tableau de bord principal
    path(_P, views.dashboard, name='dashboard'),
    path(_P + 'api/dashboard/', views.dashboard_api, name='dashboard_api'),

    # Rapports d'erreurs
    path(_P + 'erreurs/', views.error_list, name='error_list'),
    path(_P + 'erreurs/<int:pk>/', views.error_detail, name='error_detail'),

    # Capteurs et snapshots
    path(_P + 'capteurs/', views.sensor_dashboard, name='sensor_dashboard'),
    path(_P + 'api/capteurs/', views.sensor_api, name='sensor_api'),
    path(_P + 'api/capteurs/<str:sensor_type>/historique/', views.sensor_history_api, name='sensor_history_api'),
    path(_P + 'api/snapshots/', views.snapshot_history_api, name='snapshot_history_api'),

    # Disques & stockage
    path(_P + 'disques/', views.disk_dashboard, name='disk_dashboard'),
    path(_P + 'api/disques/', views.disk_api, name='disk_api'),

    # Registre des risques
    path(_P + 'risques/', views.risk_list, name='risk_list'),
    path(_P + 'risques/nouveau/', views.risk_create, name='risk_create'),
    path(_P + 'risques/<int:pk>/', views.risk_detail, name='risk_detail'),

    # Seuils d'alerte
    path(_P + 'seuils/', views.threshold_list, name='threshold_list'),
    path(_P + 'seuils/nouveau/', views.threshold_edit, name='threshold_create'),
    path(_P + 'seuils/<int:pk>/modifier/', views.threshold_edit, name='threshold_edit'),

    # Incidents
    path(_P + 'incidents/', views.incident_list, name='incident_list'),
    path(_P + 'incidents/nouveau/', views.incident_create, name='incident_create'),
    path(_P + 'incidents/<int:pk>/', views.incident_detail, name='incident_detail'),

    # Administration permissions
    path(_P + 'permissions/', views.permissions_admin, name='permissions_admin'),
    path(_P + 'permissions/<int:user_id>/', views.permission_edit, name='permission_edit'),

    # Journal d'audit
    path(_P + 'audit/', views.health_audit_log, name='audit_log'),
]
