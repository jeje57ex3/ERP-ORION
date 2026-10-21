from django.urls import path
from . import views
from . import views_planning as planning

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

    # Planning : rythme de travail, arrets, et la vue qui rassemble tout
    #
    # Les conges ne reapparaissent pas ici : ils vivent sous « conges/ »
    # juste au-dessus, et le planning les LIT. Deux endroits pour declarer
    # un conge, c'est un conge sur deux qui manque quelque part.
    path('planning/', planning.planning_equipe_view, name='planning_equipe'),
    path('planning/mon-planning/', planning.mon_planning, name='mon_planning'),
    path('planning/salarie/<int:pk>/', planning.planning_employe_view,
         name='planning_employe'),

    path('planning/rythmes/', planning.schedule_list, name='schedule_list'),
    path('planning/rythmes/nouveau/', planning.schedule_create,
         name='schedule_create'),
    path('planning/rythmes/<int:pk>/modifier/', planning.schedule_edit,
         name='schedule_edit'),
    path('planning/rythmes/<int:pk>/supprimer/', planning.schedule_delete,
         name='schedule_delete'),

    path('planning/arrets/', planning.stoppage_list, name='stoppage_list'),
    path('planning/arrets/nouveau/', planning.stoppage_create,
         name='stoppage_create'),
    path('planning/arrets/<int:pk>/modifier/', planning.stoppage_edit,
         name='stoppage_edit'),
    path('planning/arrets/<int:pk>/supprimer/', planning.stoppage_delete,
         name='stoppage_delete'),

    # Expenses
    path('frais/', views.expense_list, name='expense_list'),

    # Compétences et certifications
    path('salaries/<int:employee_pk>/competences/ajouter/', views.skill_create, name='skill_create'),
    path('salaries/competence/<int:pk>/modifier/', views.skill_edit, name='skill_edit'),
    path('salaries/competence/<int:pk>/supprimer/', views.skill_delete, name='skill_delete'),
    path('salaries/<int:employee_pk>/certifications/ajouter/', views.certification_create, name='certification_create'),
    path('salaries/certification/<int:pk>/modifier/', views.certification_edit, name='certification_edit'),
    path('salaries/certification/<int:pk>/supprimer/', views.certification_delete, name='certification_delete'),
    path('habilitations/echeances/', views.certification_expiring,
         name='certification_expiring'),
    path('salaries/certification/<int:pk>/document/',
         views.certification_download, name='certification_download'),
    path('mes-competences/', views.my_skills_certifications, name='my_skills_certifications'),

    # Dossiers privés salariés
    path('dossiers-prives/', views.private_folder_list, name='private_folder_list'),
    path('dossiers-prives/<int:employee_pk>/', views.private_folder_detail, name='private_folder_detail'),
    path('dossiers-prives/<int:employee_pk>/ajouter/', views.private_document_add, name='private_document_add'),
    path('dossiers-prives/doc/<int:pk>/supprimer/', views.private_document_delete, name='private_document_delete'),
    path('dossiers-prives/doc/<int:pk>/telechargement/', views.private_document_download, name='private_document_download'),
    path('mes-documents/', views.my_private_documents, name='my_private_documents'),
]
