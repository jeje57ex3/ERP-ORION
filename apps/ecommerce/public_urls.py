from django.urls import path
from .public_api import PublicProductListView
from apps.site_customization.public_api import (
    PublicThemeView,
    PublicPageView,
    PublicPageListView,
)
from apps.site_builder.public_api import (
    PublicBuilderPageListView,
    PublicBuilderPageView,
)

app_name = 'public_store'

urlpatterns = [
    # Produits
    path('<str:site_slug>/products/', PublicProductListView.as_view(), name='product_list'),

    # CMS — thème et pages (site_customization)
    path('<str:site_slug>/theme/',              PublicThemeView.as_view(),       name='site_theme'),
    path('<str:site_slug>/pages/',              PublicPageListView.as_view(),    name='page_list'),
    path('<str:site_slug>/pages/<str:slug>/',   PublicPageView.as_view(),        name='page_detail'),

    # Builder — pages éditées avec l'éditeur visuel
    path('<str:site_slug>/builder/pages/',              PublicBuilderPageListView.as_view(), name='builder_page_list'),
    path('<str:site_slug>/builder/pages/<str:slug>/',   PublicBuilderPageView.as_view(),     name='builder_page_detail'),
]
