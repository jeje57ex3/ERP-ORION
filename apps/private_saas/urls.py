from django.urls import path
from . import views

app_name = 'private_saas'

urlpatterns = [
    # ─── Super Admin ─────────────────────────────────────────────────────────
    path('', views.super_admin_dashboard, name='dashboard'),
    path('entreprises/', views.company_list, name='company_list'),
    path('entreprises/nouvelle/', views.company_create, name='company_create'),
    path('entreprises/<int:pk>/', views.company_detail, name='company_detail'),
    path('entreprises/<int:pk>/modules/', views.company_modules, name='company_modules'),
    path('entreprises/<int:pk>/utilisateurs/', views.company_users, name='company_users'),
    path('entreprises/<int:pk>/statut/', views.company_toggle_status, name='company_toggle_status'),
    path('sante/', views.company_health, name='health'),
    path('parametres/', views.saas_settings, name='saas_settings'),
]
