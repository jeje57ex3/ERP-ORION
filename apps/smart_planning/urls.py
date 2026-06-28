from django.urls import path
from . import views

app_name = 'smart_planning'

urlpatterns = [
    path('', views.planning_view, name='planning'),
    path('evenement/<int:pk>/', views.event_detail, name='event_detail'),
]
