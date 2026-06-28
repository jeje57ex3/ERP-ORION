from django.urls import path
from . import views

app_name = 'btp_smart_site_log'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('journaux/', views.log_list, name='log_list'),
    path('journaux/<int:pk>/', views.log_detail, name='log_detail'),
    path('incidents/<int:pk>/resoudre/', views.resolve_incident, name='resolve_incident'),
]
