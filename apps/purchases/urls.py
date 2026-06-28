from django.urls import path
from . import views

app_name = 'purchases'

urlpatterns = [
    path('', views.index, name='index'),

    # Suppliers
    path('fournisseurs/', views.supplier_list, name='supplier_list'),
    path('fournisseurs/nouveau/', views.supplier_create, name='supplier_create'),
    path('fournisseurs/<int:pk>/', views.supplier_detail, name='supplier_detail'),
    path('fournisseurs/<int:pk>/modifier/', views.supplier_edit, name='supplier_edit'),
    path('fournisseurs/<int:pk>/supprimer/', views.supplier_delete, name='supplier_delete'),

    # Purchase Orders
    path('commandes/', views.order_list, name='order_list'),
    path('commandes/nouvelle/', views.order_create, name='order_create'),
    path('commandes/<int:pk>/', views.order_detail, name='order_detail'),
    path('commandes/<int:pk>/modifier/', views.order_edit, name='order_edit'),
    path('commandes/<int:pk>/supprimer/', views.order_delete, name='order_delete'),
    path('commandes/<int:pk>/recevoir/', views.order_receive, name='order_receive'),

    # Supplier Invoices
    path('factures/', views.supplier_invoice_list, name='supplier_invoice_list'),
    path('factures/nouvelle/', views.supplier_invoice_create, name='supplier_invoice_create'),
    path('factures/<int:pk>/', views.supplier_invoice_detail, name='supplier_invoice_detail'),
    path('factures/<int:pk>/modifier/', views.supplier_invoice_edit, name='supplier_invoice_edit'),
    path('factures/<int:pk>/supprimer/', views.supplier_invoice_delete, name='supplier_invoice_delete'),
    path('factures/<int:pk>/approuver/', views.supplier_invoice_approve, name='supplier_invoice_approve'),
    path('factures/<int:pk>/payee/', views.supplier_invoice_mark_paid, name='supplier_invoice_mark_paid'),
]
