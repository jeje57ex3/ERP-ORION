from django.urls import path

from apps.system_updates import views

app_name = 'system_updates'

urlpatterns = [
    path('orion-admin/system-updates/', views.updates_dashboard, name='dashboard'),
    path('orion-admin/system-updates/check/', views.check_updates_view, name='check'),
    path('orion-admin/system-updates/confirm/', views.update_confirm_view, name='confirm'),
    path('orion-admin/system-updates/<int:pk>/', views.update_detail_view, name='update_detail'),
    path('orion-admin/system-updates/<int:pk>/logs/', views.update_logs_view, name='logs'),
    path('orion-admin/system-updates/<int:pk>/rollback/', views.rollback_confirm_view, name='rollback'),

    path('orion-admin/system-updates/serveur/redemarrer/', views.server_reboot_confirm, name='server_reboot'),
    path('orion-admin/system-updates/serveur/eteindre/', views.server_shutdown_confirm, name='server_shutdown'),
    path('orion-admin/system-updates/serveur/annuler/', views.server_action_cancel, name='server_action_cancel'),
]
