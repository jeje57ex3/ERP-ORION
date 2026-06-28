from django.urls import path
from . import views

app_name = 'predictive_analytics'

urlpatterns = [
    path('', views.analytics_dashboard, name='dashboard'),
    path('insight/<int:pk>/ignorer/', views.dismiss_insight_view, name='dismiss_insight'),
]
