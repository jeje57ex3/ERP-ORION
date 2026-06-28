from django.urls import path
from . import views

app_name = 'audit_compliance'

urlpatterns = [
    path('', views.audit_log_list, name='list'),
    path('actions-sensibles/', views.sensitive_actions, name='sensitive'),
]
