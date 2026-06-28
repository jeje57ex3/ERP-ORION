from django.urls import path
from . import views

app_name = 'documents'

urlpatterns = [
    path('', views.index, name='index'),
    path('liste/', views.document_list, name='document_list'),
    path('nouveau/', views.document_create, name='document_create'),
    path('<int:pk>/', views.document_detail, name='document_detail'),
    path('<int:pk>/modifier/', views.document_edit, name='document_edit'),
    path('<int:pk>/supprimer/', views.document_delete, name='document_delete'),
]

