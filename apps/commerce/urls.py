from django.urls import path
from . import views

app_name = 'commerce'

urlpatterns = [
    path('', views.index, name='index'),
    # Stores
    path('magasins/', views.store_list, name='store_list'),
    path('magasins/nouveau/', views.store_create, name='store_create'),
    path('magasins/<int:pk>/', views.store_detail, name='store_detail'),
    path('magasins/<int:pk>/modifier/', views.store_edit, name='store_edit'),
    path('magasins/<int:pk>/supprimer/', views.store_delete, name='store_delete'),
    # POS
    path('caisses/', views.pos_list, name='pos_list'),
    path('caisses/nouvelle/', views.pos_session_create, name='pos_session_create'),
    path('caisses/<int:pk>/fermer/', views.pos_session_close, name='pos_session_close'),
    path('tickets/', views.pos_ticket_list, name='pos_ticket_list'),
    # Loyalty
    path('fidelite/', views.loyalty_list, name='loyalty_list'),
    path('caisse/sessions/exporter/', views.pos_session_export, name='pos_session_export'),
]

