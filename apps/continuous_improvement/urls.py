from django.urls import path

from . import views, api

app_name = 'continuous_improvement'

urlpatterns = [
    # ── ERP web views ──────────────────────────────────────────────────────────
    path('erp/pdca/', views.dashboard, name='dashboard'),
    path('erp/pdca/cycles/', views.cycle_list, name='cycle_list'),
    path('erp/pdca/cycles/nouveau/', views.cycle_create, name='cycle_create'),
    path('erp/pdca/cycles/<int:pk>/', views.cycle_detail, name='cycle_detail'),
    path('erp/pdca/cycles/<int:pk>/modifier/', views.cycle_edit, name='cycle_edit'),
    path('erp/pdca/cycles/<int:pk>/activer/', views.activate_cycle_view, name='activate_cycle'),
    path('erp/pdca/cycles/<int:pk>/avancer/', views.advance_cycle_stage, name='advance_stage'),
    path('erp/pdca/cycles/<int:pk>/annuler/', views.cancel_cycle_view, name='cancel_cycle'),
    path('erp/pdca/cycles/<int:pk>/plan/enregistrer/', views.save_plan, name='save_plan'),
    path('erp/pdca/cycles/<int:pk>/do/enregistrer/', views.save_do, name='save_do'),
    path('erp/pdca/cycles/<int:pk>/check/enregistrer/', views.save_check, name='save_check'),
    path('erp/pdca/cycles/<int:pk>/act/enregistrer/', views.save_act, name='save_act'),
    path('erp/pdca/cycles/<int:pk>/actions/ajouter/', views.add_action_view, name='add_action'),
    path('erp/pdca/actions/<int:action_pk>/terminer/', views.complete_action_view, name='complete_action'),
    path('erp/pdca/cycles/<int:pk>/kpis/ajouter/', views.add_kpi_view, name='add_kpi'),
    path('erp/pdca/standards/', views.standards_list, name='standards_list'),
    path('erp/pdca/modeles/', views.templates_list, name='templates_list'),

    # ── REST API ───────────────────────────────────────────────────────────────
    path('api/v1/pdca/cycles/', api.api_cycles_list, name='api_cycles_list'),
    path('api/v1/pdca/cycles/creer/', api.api_create_cycle, name='api_create_cycle'),
    path('api/v1/pdca/cycles/<int:pk>/', api.api_cycle_detail, name='api_cycle_detail'),
    path('api/v1/pdca/cycles/<int:pk>/activer/', api.api_activate_cycle, name='api_activate_cycle'),
    path('api/v1/pdca/cycles/<int:pk>/avancer/', api.api_advance_stage, name='api_advance_stage'),
    path('api/v1/pdca/cycles/<int:pk>/phase/<str:phase>/', api.api_update_phase, name='api_update_phase'),
    path('api/v1/pdca/cycles/<int:pk>/act/', api.api_record_act, name='api_record_act'),
    path('api/v1/pdca/cycles/<int:pk>/actions/ajouter/', api.api_create_action, name='api_create_action'),
    path('api/v1/pdca/actions/<int:action_pk>/terminer/', api.api_complete_action, name='api_complete_action'),
    path('api/v1/pdca/kpis/<int:kpi_pk>/resultat/', api.api_record_kpi_result, name='api_record_kpi_result'),
    path('api/v1/pdca/stats/', api.api_dashboard_stats, name='api_dashboard_stats'),
    path('api/v1/pdca/mes-actions/', api.api_my_actions, name='api_my_actions'),
]
