from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    path('', views.index, name='index'),

    # Products
    path('produits/', views.product_list, name='product_list'),
    path('produits/nouveau/', views.product_create, name='product_create'),
    path('produits/<int:pk>/', views.product_detail, name='product_detail'),
    path('produits/<int:pk>/modifier/', views.product_edit, name='product_edit'),
    path('produits/<int:pk>/supprimer/', views.product_delete, name='product_delete'),

    # Warehouses
    path('entrepots/', views.warehouse_list, name='warehouse_list'),
    path('entrepots/nouveau/', views.warehouse_create, name='warehouse_create'),
    path('entrepots/<int:pk>/', views.warehouse_detail, name='warehouse_detail'),
    path('entrepots/<int:pk>/modifier/', views.warehouse_edit, name='warehouse_edit'),
    path('entrepots/<int:pk>/supprimer/', views.warehouse_delete, name='warehouse_delete'),

    # Movements
    path('mouvements/', views.movement_list, name='movement_list'),
    path('mouvements/nouveau/', views.movement_create, name='movement_create'),
]
