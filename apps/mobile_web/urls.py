from django.urls import path

from apps.mobile_web import views

app_name = 'mobile_web'

urlpatterns = [
    path('m/', views.accueil, name='accueil'),
    path('m/photo/', views.photo, name='photo'),
    path('m/serveurs/', views.serveurs, name='serveurs'),
]
