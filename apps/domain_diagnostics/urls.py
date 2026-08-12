from django.urls import path

from apps.domain_diagnostics import views

app_name = 'domain_diagnostics'

urlpatterns = [
    path('', views.diagnostics_dashboard, name='dashboard'),
    path('cible/ajouter/', views.target_create, name='target_create'),
    path('cible/<int:pk>/modifier/', views.target_update, name='target_update'),
    path('cible/<int:pk>/scanner/', views.run_scan, name='run_scan'),
    path('scan/<int:run_id>/', views.scan_result, name='scan_result'),
    path('problemes/', views.issue_list, name='issue_list'),
    path('problemes/<int:issue_id>/corriger/', views.repair_issue, name='repair_issue'),
    path('cloudflare/', views.cloudflare_settings, name='cloudflare_settings'),
]
