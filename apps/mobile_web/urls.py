from django.urls import path

from apps.mobile_web import views

app_name = 'mobile_web'

urlpatterns = [
    path('m/', views.accueil, name='accueil'),
    path('m/photo/', views.photo, name='photo'),
    path('m/serveurs/', views.serveurs, name='serveurs'),

    # Installation sur le telephone. L'agent de service est servi DEPUIS /m/
    # pour que sa portee se limite a ces pages : place a la racine, il
    # prendrait tout l'ERP en charge.
    path('m/manifest.webmanifest', views.manifeste, name='manifeste'),
    path('m/sw.js', views.agent_de_service, name='agent_de_service'),
    path('m/hors-ligne/', views.hors_ligne, name='hors_ligne'),
]
