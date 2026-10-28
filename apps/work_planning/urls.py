from django.urls import path
from . import views, api

app_name = 'work_planning'

urlpatterns = [
    # ── Dashboard ─────────────────────────────────────────────────────────────
    path('erp/planning/', views.dashboard, name='dashboard'),

    # ── Planning hebdomadaire ─────────────────────────────────────────────────
    path('erp/planning/semaine/', views.weekly_planning, name='weekly_planning'),

    # ── Missions ──────────────────────────────────────────────────────────────
    path('erp/planning/missions/', views.mission_list, name='mission_list'),
    path('erp/planning/missions/nouvelle/', views.mission_create, name='mission_create'),
    path('erp/planning/missions/<int:pk>/', views.mission_detail, name='mission_detail'),
    path('erp/planning/missions/<int:pk>/modifier/', views.mission_edit, name='mission_edit'),
    path('erp/planning/missions/<int:pk>/supprimer/', views.mission_delete, name='mission_delete'),

    # ── Tâches ────────────────────────────────────────────────────────────────
    path('erp/planning/missions/<int:mission_pk>/taches/nouvelle/', views.task_create, name='task_create'),
    path('erp/planning/taches/<int:pk>/modifier/', views.task_edit, name='task_edit'),
    path('erp/planning/taches/<int:pk>/supprimer/', views.task_delete, name='task_delete'),

    # ── Employés ──────────────────────────────────────────────────────────────
    path('erp/planning/equipe/', views.employee_list, name='employee_list'),
    path('erp/planning/equipe/ajouter/', views.employee_create, name='employee_create'),
    path('erp/planning/equipe/<int:pk>/modifier/', views.employee_edit, name='employee_edit'),
    path('erp/planning/equipe/<int:pk>/contraintes/', views.employee_constraints, name='employee_constraints'),
    path('erp/planning/equipe/<int:pk>/contraintes/nouvelle/', views.employee_constraint_create, name='employee_constraint_create'),

    # ── Contraintes salarié ───────────────────────────────────────────────────
    path('erp/planning/contraintes/', views.all_employee_constraints, name='all_employee_constraints'),
    path('erp/planning/contraintes/<int:constraint_pk>/modifier/', views.employee_constraint_edit, name='employee_constraint_edit'),
    path('erp/planning/contraintes/<int:constraint_pk>/supprimer/', views.employee_constraint_delete, name='employee_constraint_delete'),

    # ── Blocs de temps ────────────────────────────────────────────────────────
    path('erp/planning/heures/saisir/', views.time_block_create, name='time_block_create'),
    path('erp/planning/heures/<int:pk>/modifier/', views.time_block_edit, name='time_block_edit'),
    path('erp/planning/heures/<int:pk>/supprimer/', views.time_block_delete, name='time_block_delete'),

    # ── Demandes clients ──────────────────────────────────────────────────────
    path('erp/planning/demandes/', views.customer_request_list, name='customer_request_list'),
    path('erp/planning/demandes/nouvelle/', views.customer_request_create, name='customer_request_create'),
    path('erp/planning/demandes/<int:pk>/', views.customer_request_detail, name='customer_request_detail'),
    path('erp/planning/demandes/<int:pk>/modifier/', views.customer_request_edit, name='customer_request_edit'),
    path('erp/planning/demandes/<int:pk>/convertir/', views.customer_request_convert, name='customer_request_convert'),
    path('erp/planning/demandes/<int:pk>/supprimer/', views.customer_request_delete, name='customer_request_delete'),

    # ── Planification automatique ─────────────────────────────────────────────
    path('erp/planning/auto/', views.auto_schedule, name='auto_schedule'),

    # ── API JSON ──────────────────────────────────────────────────────────────
    path('api/v1/planning/week/', api.api_weekly_data, name='api_weekly_data'),
    path('api/v1/planning/missions/', api.api_missions, name='api_missions'),
    path('api/v1/planning/tasks/', api.api_tasks, name='api_tasks'),
    path('api/v1/planning/blocks/', api.api_create_block, name='api_create_block'),
    path('api/v1/planning/blocks/<int:pk>/', api.api_delete_block, name='api_delete_block'),
    path('api/v1/planning/customer-requests/', api.api_customer_requests, name='api_customer_requests'),
    path('api/v1/planning/auto-schedule/', api.api_auto_schedule, name='api_auto_schedule'),
    path('api/v1/planning/employee-constraints/', api.api_employee_constraints, name='api_employee_constraints'),
]
