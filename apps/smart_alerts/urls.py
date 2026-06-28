from django.urls import path
from . import views

app_name = 'smart_alerts'

urlpatterns = [
    path('', views.alert_list, name='list'),
    path('<int:pk>/', views.alert_detail, name='detail'),
    path('<int:pk>/resolve/', views.alert_resolve, name='resolve'),
    path('<int:pk>/acknowledge/', views.alert_acknowledge, name='acknowledge'),
    path('<int:pk>/ignore/', views.alert_ignore, name='ignore'),
    path('api/widget/', views.api_widget_data, name='api_widget'),
]
