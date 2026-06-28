from django.urls import path
from . import views

app_name = 'sales'

urlpatterns = [
    path('', views.index, name='index'),

    # Devis
    path('devis/', views.quote_list, name='quote_list'),
    path('devis/nouveau/', views.quote_create, name='quote_create'),
    path('devis/<int:pk>/', views.quote_detail, name='quote_detail'),
    path('devis/<int:pk>/modifier/', views.quote_edit, name='quote_edit'),
    path('devis/<int:pk>/supprimer/', views.quote_delete, name='quote_delete'),
    path('devis/<int:pk>/envoyer/', views.quote_send, name='quote_send'),
    path('devis/<int:pk>/accepter/', views.quote_accept, name='quote_accept'),
    path('devis/<int:pk>/convertir-commande/', views.quote_convert_order, name='quote_convert_order'),

    # Commandes
    path('commandes/', views.order_list, name='order_list'),
    path('commandes/nouvelle/', views.order_create, name='order_create'),
    path('commandes/<int:pk>/', views.order_detail, name='order_detail'),
    path('commandes/<int:pk>/statut/<str:new_status>/', views.order_update_status, name='order_update_status'),

    # Factures
    path('factures/', views.invoice_list, name='invoice_list'),
    path('factures/nouvelle/', views.invoice_create, name='invoice_create'),
    path('factures/<int:pk>/', views.invoice_detail, name='invoice_detail'),
    path('factures/<int:pk>/modifier/', views.invoice_edit, name='invoice_edit'),
    path('factures/<int:pk>/supprimer/', views.invoice_delete, name='invoice_delete'),
    path('factures/<int:pk>/payee/', views.invoice_mark_paid, name='invoice_mark_paid'),
    path('factures/<int:pk>/envoyer/', views.invoice_send, name='invoice_send'),
]
