from django.urls import path
from . import views
from . import guided_quote_erp_views as gq

app_name = 'btp'

urlpatterns = [
    path('', views.index, name='index'),

    # Projects (Chantiers)
    path('chantiers/', views.project_list, name='project_list'),
    path('chantiers/nouveau/', views.project_create, name='project_create'),
    path('chantiers/<int:pk>/', views.project_detail, name='project_detail'),
    path('chantiers/<int:pk>/modifier/', views.project_edit, name='project_edit'),
    path('chantiers/<int:pk>/supprimer/', views.project_delete, name='project_delete'),

    # BTP Quotes
    path('devis/', views.quote_list, name='quote_list'),
    path('devis/nouveau/', views.quote_create, name='quote_create'),
    path('devis/<int:pk>/', views.quote_detail, name='quote_detail'),
    path('devis/<int:pk>/modifier/', views.quote_edit, name='quote_edit'),
    path('devis/<int:pk>/supprimer/', views.quote_delete, name='quote_delete'),

    # Situations
    path('situations/', views.situation_list, name='situation_list'),
    path('situations/nouvelle/', views.situation_create, name='situation_create'),
    path('situations/<int:pk>/', views.situation_detail, name='situation_detail'),
    path('situations/<int:pk>/supprimer/', views.situation_delete, name='situation_delete'),

    # Timesheets
    path('pointage/', views.timesheet_list, name='timesheet_list'),
    path('pointage/nouveau/', views.timesheet_create, name='timesheet_create'),

    # â”€â”€â”€ Demandes guidÃ©es â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    path('demandes-guidees/', gq.guided_quote_list, name='guided_quote_list'),
    path('demandes-guidees/<int:pk>/', gq.guided_quote_detail, name='guided_quote_detail'),

    # BibliothÃ¨que de prix Ã©lectricitÃ©
    path('tarifs-electricite/', gq.price_library_list, name='price_library_list'),
    path('tarifs-electricite/nouveau/', gq.price_library_create, name='price_library_create'),
    path('tarifs-electricite/<int:pk>/modifier/', gq.price_library_edit, name='price_library_edit'),
    path('tarifs-electricite/<int:pk>/supprimer/', gq.price_library_delete, name='price_library_delete'),

    # Dashboard responsable chantier
    path('responsable/', gq.site_manager_dashboard, name='site_manager_dashboard'),

    # Messagerie client (vue ERP)
    path('messages-clients/', gq.client_messages_list, name='client_messages_list'),
    path('messages-clients/<int:pk>/', gq.client_conversation_detail, name='client_conversation_detail'),

    # Heures visibles client
    path('heures-chantiers/', gq.time_entry_list, name='time_entry_list'),
    path('heures/<int:pk>/toggle-visible/', gq.time_entry_toggle_visible, name='time_entry_toggle_visible'),

    # RÃ©serves
    path('reserves/', gq.reservations_list, name='reservations_list'),
    path('reserves/<int:pk>/statut/', gq.reservation_update_status, name='reservation_update_status'),
    path('devis/<int:pk>/envoyer/', views.quote_send, name='quote_send'),
    path('devis/<int:pk>/convertir/', views.quote_convert, name='quote_convert'),
    path('pointages/<int:pk>/', views.timesheet_detail, name='timesheet_detail'),
    path('pointages/<int:pk>/valider/', views.timesheet_validate, name='timesheet_validate'),
    path('pointages/<int:pk>/refuser/', views.timesheet_reject, name='timesheet_reject'),
    path('pointages/valider-selection/', views.timesheet_validate_bulk, name='timesheet_validate_bulk'),]

