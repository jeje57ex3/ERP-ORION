from django.urls import path
from . import views

app_name = 'backup_center'

urlpatterns = [
    path('', views.backup_dashboard, name='dashboard'),
    path('tache/<int:pk>/', views.job_detail, name='job_detail'),
    path('tache/<int:pk>/executer/', views.run_backup, name='run'),
    path('tache/<int:pk>/toggle/', views.toggle_job, name='toggle'),
]
