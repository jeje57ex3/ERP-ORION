"""
apps/orion_ops/urls.py — Routes montées sous /orion-admin/ops/
"""
from django.urls import path
from . import views

app_name = 'orion_ops'

urlpatterns = [
    # Tableau de bord
    path('', views.dashboard, name='dashboard'),

    # SLO
    path('slo/', views.slo_list, name='slo_list'),
    path('slo/<slug:slug>/', views.slo_detail, name='slo_detail'),
    path('api/slo/', views.slo_api, name='slo_api'),

    # Cartographie des dépendances
    path('dependances/', views.dependency_map, name='dependency_map'),
    path('api/dependencies/', views.dependency_api, name='dependency_api'),

    # Qualité des données
    path('qualite-donnees/', views.data_quality, name='data_quality'),

    # Déploiements
    path('deploiements/', views.deployment_list, name='deployment_list'),
    path('deploiements/nouveau/', views.deployment_create, name='deployment_create'),

    # Tests de restauration
    path('restauration/', views.restore_test_list, name='restore_test_list'),

    # Prévisions de capacité
    path('capacite/', views.capacity_dashboard, name='capacity'),

    # Tâches Celery échouées
    path('taches-echouees/', views.failed_tasks_list, name='failed_tasks_list'),
    path('taches-echouees/<int:pk>/fermer/', views.failed_task_close, name='failed_task_close'),

    # Règles d'alerte
    path('regles-alertes/', views.alert_rules_list, name='alert_rules_list'),
    path('regles-alertes/<int:pk>/toggle/', views.alert_rule_toggle, name='alert_rule_toggle'),

    # Plan de continuité d'activité (BCP)
    path('bcp/', views.bcp_list, name='bcp_list'),
    path('bcp/nouveau/', views.bcp_create, name='bcp_create'),

    # Tests de défaillance
    path('tests-defaillance/', views.failure_tests_list, name='failure_tests_list'),
    path('tests-defaillance/nouveau/', views.failure_test_create, name='failure_test_create'),

    # API JSON
    path('api/scores/', views.extended_scores_api, name='extended_scores_api'),
]
