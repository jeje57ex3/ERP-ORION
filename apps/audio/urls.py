from django.urls import path
from . import views

app_name = 'audio'

urlpatterns = [
    path('', views.index, name='index'),
    # Events
    path('evenements/', views.event_list, name='event_list'),
    path('evenements/nouveau/', views.event_create, name='event_create'),
    path('evenements/<int:pk>/', views.event_detail, name='event_detail'),
    path('evenements/<int:pk>/modifier/', views.event_edit, name='event_edit'),
    # Equipment
    path('materiel/', views.equipment_list, name='equipment_list'),
    path('materiel/nouveau/', views.equipment_create, name='equipment_create'),
    path('materiel/<int:pk>/', views.equipment_detail, name='equipment_detail'),
    path('materiel/<int:pk>/modifier/', views.equipment_edit, name='equipment_edit'),
    # Reservations
    path('reservations/', views.reservation_list, name='reservation_list'),
    path('reservations/nouvelle/', views.reservation_create, name='reservation_create'),
    # Technicians
    path('techniciens/', views.technician_list, name='technician_list'),
    path('techniciens/nouveau/', views.technician_create, name='technician_create'),
]

