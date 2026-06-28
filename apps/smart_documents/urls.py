from django.urls import path
from . import views

app_name = 'smart_documents'

urlpatterns = [
    path('', views.document_list, name='list'),
    path('<int:pk>/', views.document_detail, name='detail'),
]
