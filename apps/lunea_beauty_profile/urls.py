from django.urls import path
from . import views

app_name = 'lunea_beauty_profile'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('profils/', views.profile_list, name='profile_list'),
    path('profils/<int:pk>/', views.profile_detail, name='profile_detail'),
    path('recommandations/<int:pk>/appliquer/', views.mark_applied, name='mark_applied'),
    # Nouvelles pages
    path('recommandations/', views.recommendations_list, name='recommendations_list'),
    path('diagnostics/', views.diagnostics_view, name='diagnostics'),
    path('routines/', views.routines_view, name='routines'),
]
