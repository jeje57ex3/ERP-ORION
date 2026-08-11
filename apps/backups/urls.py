from django.urls import path
from . import views

app_name = 'backups'

urlpatterns = [
    path('',                     views.dashboard,           name='dashboard'),
    path('liste/',               views.backup_list,         name='list'),
    path('creer/',               views.backup_create,       name='create'),
    path('exporter/',            views.backup_export,       name='export'),
    path('importer/',            views.backup_import,       name='import'),
    path('<int:pk>/',            views.backup_detail,       name='detail'),
    path('<int:pk>/telecharger/',views.backup_download,     name='download'),
    path('<int:pk>/restaurer/',  views.restore_backup_view, name='restore'),
    path('<int:pk>/supprimer/',  views.backup_delete,       name='delete'),
    path('planification/',       views.backup_schedules,    name='schedules'),
    path('planification/creer/', views.schedule_create,     name='schedule_create'),
    path('parametres/',          views.backup_settings,     name='settings'),
]
