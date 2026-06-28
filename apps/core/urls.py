from django.urls import path
from . import views
from .search import global_search

app_name = 'core'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('search/', global_search, name='search'),
    # ── Entreprises ────────────────────────────────────────────────────────────
    path('companies/', views.company_list, name='company_list'),
    path('companies/new/', views.company_create, name='company_create'),
    path('companies/<int:pk>/', views.company_detail, name='company_detail'),
    path('companies/<int:pk>/edit/', views.company_edit, name='company_edit'),
    path('companies/<int:company_id>/switch/', views.switch_company, name='switch_company'),
    # ── Bases de données ───────────────────────────────────────────────────────
    path('companies/<int:pk>/database/', views.company_database, name='company_database'),
    path('companies/<int:pk>/database/create/', views.company_database_create, name='company_database_create'),
    path('companies/<int:pk>/database/test/', views.company_database_test, name='company_database_test'),
    path('companies/<int:pk>/database/migrate/', views.company_database_migrate, name='company_database_migrate'),
    path('companies/<int:pk>/database/backup/', views.company_database_backup, name='company_database_backup'),
    path('companies/<int:pk>/database/archive/', views.company_database_archive, name='company_database_archive'),
    path('companies/<int:pk>/database/delete/', views.company_database_delete, name='company_database_delete'),
    # ── Notifications ──────────────────────────────────────────────────────────
    path('notifications/', views.notifications_list, name='notifications'),
    path('notifications/<int:pk>/read/', views.notifications_read, name='notification_read'),
    path('notifications/read-all/', views.notifications_read_all, name='notifications_read_all'),
]
