from django.urls import path
from . import views

app_name = 'support'

urlpatterns = [
    path('', views.index, name='index'),
    path('tickets/', views.ticket_list, name='ticket_list'),
    path('tickets/nouveau/', views.ticket_create, name='ticket_create'),
    path('tickets/<int:pk>/', views.ticket_detail, name='ticket_detail'),
    path('tickets/<int:pk>/modifier/', views.ticket_edit, name='ticket_edit'),
    path('tickets/<int:pk>/supprimer/', views.ticket_delete, name='ticket_delete'),
    path('tickets/<int:pk>/resoudre/', views.ticket_resolve, name='ticket_resolve'),
    path('tickets/<int:pk>/fermer/', views.ticket_close, name='ticket_close'),
    path('reclamations/', views.claim_list, name='claim_list'),
]

