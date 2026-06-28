from django.urls import path
from . import views

app_name = 'smart_automations'

urlpatterns = [
    path('', views.rule_list, name='list'),
    path('creer/', views.rule_create, name='create'),
    path('<int:pk>/modifier/', views.rule_edit, name='edit'),
    path('<int:pk>/activer/', views.rule_toggle, name='toggle'),
    path('<int:pk>/executer/', views.rule_run, name='run'),
    path('<int:pk>/historique/', views.run_list, name='run_list'),
]
