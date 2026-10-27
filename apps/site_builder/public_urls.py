"""API publique de l'éditeur visuel, montée sous /api/v1/public/.

Pourquoi un fichier à part alors que `apps/ecommerce/public_urls.py` câble
déjà ces trois routes : ce fichier-là importe aussi
`apps.site_customization.public_api`, et `site_customization` est une
autre application non enregistrée. Le monter tel quel réveillerait deux
modules au lieu d'un, dont un que personne n'a relu.

Quand `site_customization` sera branchée à son tour, c'est
`apps/ecommerce/public_urls.py` qu'il faudra monter — et retirer ce
fichier-ci de `erp_btp/urls.py` pour ne pas servir les mêmes routes deux
fois.

Ces routes ne servent que des pages **publiées** : la règle est dans
`selectors.get_published_page`, pas ici.
"""

from django.urls import path

from .public_api import PublicBuilderPageListView, PublicBuilderPageView

app_name = 'public_builder'

urlpatterns = [
    path('<str:site_slug>/builder/pages/',
         PublicBuilderPageListView.as_view(), name='page_list'),
    path('<str:site_slug>/builder/pages/<str:slug>/',
         PublicBuilderPageView.as_view(), name='page_detail'),
]
