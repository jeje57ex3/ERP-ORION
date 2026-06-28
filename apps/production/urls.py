from django.urls import path
from . import views

app_name = 'production'

urlpatterns = [
    path('', views.index, name='index'),
    # Manufacturing Orders
    path('ordres/', views.order_list, name='order_list'),
    path('ordres/nouveau/', views.order_create, name='order_create'),
    path('ordres/<int:pk>/', views.order_detail, name='order_detail'),
    path('ordres/<int:pk>/modifier/', views.order_edit, name='order_edit'),
    # BOM
    path('nomenclatures/', views.bom_list, name='bom_list'),
    path('nomenclatures/nouvelle/', views.bom_create, name='bom_create'),
    path('nomenclatures/<int:pk>/', views.bom_detail, name='bom_detail'),
    path('nomenclatures/<int:pk>/modifier/', views.bom_edit, name='bom_edit'),
    # Work Centers
    path('centres/', views.planning, name='planning'),
    path('centres/nouveau/', views.workcenter_create, name='workcenter_create'),
]

