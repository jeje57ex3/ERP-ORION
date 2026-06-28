from django.urls import path
from . import views

app_name = 'api_webhooks'

urlpatterns = [
    path('', views.endpoint_list, name='list'),
    path('creer/', views.create_endpoint_view, name='create'),
    path('<int:pk>/', views.endpoint_detail, name='detail'),
    path('<int:pk>/toggle/', views.toggle_endpoint, name='toggle'),
]
