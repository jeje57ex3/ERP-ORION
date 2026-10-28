from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    path('', views.order_list, name='order_list'),
    path('<str:order_number>/', views.order_detail, name='order_detail'),
    path('<int:pk>/processing/', views.order_mark_processing, name='order_mark_processing'),
    path('<int:pk>/shipped/', views.order_mark_shipped, name='order_mark_shipped'),
]
