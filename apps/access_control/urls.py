from django.urls import path
from . import views

app_name = 'access_control'

urlpatterns = [
    path('', views.access_dashboard, name='dashboard'),
    path('modules/', views.module_list, name='module_list'),
    path('roles/', views.role_list, name='role_list'),
    path('roles/nouveau/', views.role_create, name='role_create'),
    path('roles/<int:pk>/permissions/', views.role_permissions, name='role_permissions'),
    path('roles/<int:pk>/dupliquer/', views.role_duplicate, name='role_duplicate'),
    path('utilisateurs/', views.user_access_list, name='user_access_list'),
    path('utilisateurs/ajouter/', views.user_access_create, name='user_access_create'),
    path('utilisateurs/<int:pk>/supprimer/', views.user_access_delete, name='user_access_delete'),
    path('overrides/', views.override_list, name='override_list'),
    path('overrides/nouveau/', views.override_create, name='override_create'),
    path('overrides/<int:pk>/supprimer/', views.override_delete, name='override_delete'),
    path('journal/', views.access_log_list, name='access_log'),
]
