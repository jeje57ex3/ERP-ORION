from django.urls import path
from . import views

app_name = 'hr'

urlpatterns = [
    path('', views.index, name='index'),

    # Employees
    path('salaries/', views.employee_list, name='employee_list'),
    path('salaries/nouveau/', views.employee_create, name='employee_create'),
    path('salaries/<int:pk>/', views.employee_detail, name='employee_detail'),
    path('salaries/<int:pk>/modifier/', views.employee_edit, name='employee_edit'),
    path('salaries/<int:pk>/supprimer/', views.employee_delete, name='employee_delete'),

    # Leaves
    path('conges/', views.leave_list, name='leave_list'),
    path('conges/nouveau/', views.leave_create, name='leave_create'),
    path('conges/<int:pk>/approuver/', views.leave_approve, name='leave_approve'),
    path('conges/<int:pk>/refuser/', views.leave_refuse, name='leave_refuse'),

    # Expenses
    path('frais/', views.expense_list, name='expense_list'),

    # Dossiers privés salariés
    path('dossiers-prives/', views.private_folder_list, name='private_folder_list'),
    path('dossiers-prives/<int:employee_pk>/', views.private_folder_detail, name='private_folder_detail'),
    path('dossiers-prives/<int:employee_pk>/ajouter/', views.private_document_add, name='private_document_add'),
    path('dossiers-prives/doc/<int:pk>/supprimer/', views.private_document_delete, name='private_document_delete'),
    path('dossiers-prives/doc/<int:pk>/telechargement/', views.private_document_download, name='private_document_download'),
    path('mes-documents/', views.my_private_documents, name='my_private_documents'),
]
