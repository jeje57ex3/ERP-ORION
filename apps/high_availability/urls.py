from django.urls import path
from apps.high_availability.health import health_view, public_health_view
from apps.high_availability import views

app_name = 'high_availability'

urlpatterns = [
    # Health endpoints (no auth — secret header)
    path('ha/health/', health_view, name='health'),
    path('ha/public-health/', public_health_view, name='public_health'),

    # Super Admin UI
    path('orion-admin/ha/settings/', views.ha_settings_view, name='admin_settings'),
    path('orion-admin/ha/nodes/', views.ha_nodes_view, name='admin_nodes'),
    path('orion-admin/ha/nodes/<int:pk>/', views.ha_node_detail_view, name='admin_node_detail'),
    path('orion-admin/ha/replication/', views.ha_replication_view, name='admin_replication'),
    path('orion-admin/ha/failover/', views.ha_failover_view, name='admin_failover'),
    path('orion-admin/ha/failover/run/', views.ha_run_failover_view, name='admin_run_failover'),
    path('orion-admin/ha/events/', views.ha_events_view, name='admin_events'),
    path('orion-admin/ha/check-nodes/', views.ha_check_nodes_view, name='admin_check_nodes'),
]
