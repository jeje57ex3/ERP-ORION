from django.urls import path
from . import views

app_name = 'workflow_center'

urlpatterns = [
    path('', views.instance_list, name='list'),
    path('<int:pk>/', views.instance_detail, name='detail'),
    path('<int:pk>/approve/', views.instance_approve, name='approve'),
    path('<int:pk>/reject/', views.instance_reject, name='reject'),
]
