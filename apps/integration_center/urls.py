from django.urls import path
from . import views

app_name = 'integration_center'

urlpatterns = [
    path('', views.integration_list, name='list'),
    path('<int:pk>/', views.integration_detail, name='detail'),
    path('<int:pk>/toggle/', views.toggle_integration, name='toggle'),
]
