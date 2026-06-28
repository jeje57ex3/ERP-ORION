from django.urls import path
from . import views

app_name = 'crm'

urlpatterns = [
    path('', views.index, name='index'),

    # Customers
    path('clients/', views.customer_list, name='customer_list'),
    path('clients/nouveau/', views.customer_create, name='customer_create'),
    path('clients/<int:pk>/', views.customer_detail, name='customer_detail'),
    path('clients/<int:pk>/modifier/', views.customer_edit, name='customer_edit'),
    path('clients/<int:pk>/supprimer/', views.customer_delete, name='customer_delete'),

    # Prospects
    path('prospects/', views.prospect_list, name='prospect_list'),
    path('prospects/nouveau/', views.prospect_create, name='prospect_create'),
    path('prospects/<int:pk>/', views.prospect_detail, name='prospect_detail'),
    path('prospects/<int:pk>/modifier/', views.prospect_edit, name='prospect_edit'),
    path('prospects/<int:pk>/supprimer/', views.prospect_delete, name='prospect_delete'),
    path('prospects/<int:pk>/convertir/', views.prospect_convert, name='prospect_convert'),

    # Opportunities
    path('opportunites/', views.opportunity_list, name='opportunity_list'),
    path('opportunites/nouvelle/', views.opportunity_create, name='opportunity_create'),
    path('opportunites/<int:pk>/', views.opportunity_detail, name='opportunity_detail'),
    path('opportunites/<int:pk>/modifier/', views.opportunity_edit, name='opportunity_edit'),
    path('opportunites/<int:pk>/supprimer/', views.opportunity_delete, name='opportunity_delete'),
    path('opportunites/<int:pk>/gagnee/', views.opportunity_mark_won, name='opportunity_mark_won'),
    path('opportunites/<int:pk>/perdue/', views.opportunity_mark_lost, name='opportunity_mark_lost'),

    # Contacts
    path('contacts/', views.contact_list, name='contact_list'),
    path('contacts/nouveau/', views.contact_create, name='contact_create'),
    path('contacts/<int:pk>/modifier/', views.contact_edit, name='contact_edit'),
    path('contacts/<int:pk>/supprimer/', views.contact_delete, name='contact_delete'),
    path('clients/exporter/', views.customer_export, name='customer_export'),
    path('clients/importer/', views.customer_import, name='customer_import'),
    path('contacts/exporter/', views.contact_export, name='contact_export'),
    path('opportunites/exporter/', views.opportunity_export, name='opportunity_export'),
    path('prospects/exporter/', views.prospect_export, name='prospect_export'),
    path('prospects/convertir-selection/', views.prospect_convert_bulk, name='prospect_convert_bulk'),]

