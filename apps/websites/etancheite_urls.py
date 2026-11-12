"""Adresses du site vitrine Électricité & Étanchéité.

Relatives : le préfixe « sites/<slug>/etancheite/ » est porté au point de
montage, dans erp_btp/urls.py, et placé AVANT l'include générique de
public_urls — dont la première règle « <slug:site_slug>/ » absorberait tout
ce qui suit.

Montées depuis erp_btp/urls.py et non ajoutées à public_urls.py, pour ne pas
avoir à committer le travail en cours qui s'y trouve.
"""
from django.urls import path

from . import etancheite_public_views as vues

app_name = 'etancheite'

urlpatterns = [
    path('', vues.etancheite_home, name='home'),
    path('services/', vues.etancheite_services, name='services'),
    path('services/<slug:service_slug>/', vues.etancheite_service_detail,
         name='service_detail'),
    path('realisations/', vues.etancheite_realisations, name='realisations'),
    path('entreprise/', vues.etancheite_entreprise, name='entreprise'),
    path('contact/', vues.etancheite_contact, name='contact'),
    path('devis/', vues.etancheite_devis, name='devis'),
]
