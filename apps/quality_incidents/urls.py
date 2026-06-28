from django.urls import path
from . import views

app_name = 'quality_incidents'

urlpatterns = [
    path('', views.incident_list, name='list'),
    path('<int:pk>/', views.incident_detail, name='detail'),
    path('<int:pk>/resoudre/', views.incident_resolve, name='resolve'),
    path('<int:pk>/commentaire/', views.add_comment_view, name='add_comment'),
]
