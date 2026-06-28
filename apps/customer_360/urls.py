from django.urls import path
from . import views

app_name = 'customer_360'

urlpatterns = [
    path('<int:customer_pk>/', views.customer_360, name='view'),
    path('<int:customer_pk>/scores/', views.refresh_scores, name='refresh_scores'),
    path('<int:customer_pk>/note/', views.add_note, name='add_note'),
]
