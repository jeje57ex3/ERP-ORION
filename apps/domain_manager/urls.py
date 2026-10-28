from django.urls import path

from apps.domain_manager import views

app_name = 'domain_manager'

urlpatterns = [
    path('erp/domains/', views.domain_list_view, name='list'),
    path('erp/domains/new/', views.domain_create_view, name='create'),
    path('erp/domains/<int:pk>/', views.domain_detail_view, name='detail'),
    path('erp/domains/<int:pk>/verify/', views.domain_verify_view, name='verify'),
    path('erp/domains/<int:pk>/make-primary/', views.domain_make_primary_view, name='make_primary'),
    path('erp/domains/<int:pk>/delete/', views.domain_delete_view, name='delete'),
]
