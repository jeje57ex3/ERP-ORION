"""Routes de l'application PC.

Relatives : le prefixe « orion-admin/application-pc/ » est porte au point de
montage dans erp_btp/urls.py, comme pour apps/core/mail_urls.py.

Le telechargement vit sous le meme prefixe mais n'est PAS reserve au
super-admin : la vue le verifie elle-meme, parce que deposer une version et
en telecharger une sont deux droits differents.
"""
from django.urls import path

from apps.core import application_pc_views as v

app_name = 'core_application_pc'

urlpatterns = [
    path('', v.publier_application, name='publier'),
    path('<int:pk>/basculer/', v.basculer_publication, name='basculer'),
    path('telecharger/', v.telecharger_application, name='telecharger'),
]
