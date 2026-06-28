"""
Brand-aware e-commerce API endpoints.
Mounted at /api/v1/siecle/ and /api/v1/lunea/store/
"""
from django.urls import path

app_name = 'ecommerce_brand'
from .brand_views import (
    BrandCartView,
    BrandCartAddView,
    BrandCartUpdateView,
    BrandCartRemoveView,
    BrandWishlistView,
    BrandOrdersView,
    BrandRewardsView,
    WatchCustomizationOptionsView,
    SavedWatchConfigView,
    AddCustomWatchToCartView,
)

urlpatterns = [
    # Panier
    path('cart/', BrandCartView.as_view(), name='cart'),
    path('cart/add/', BrandCartAddView.as_view(), name='cart_add'),
    path('cart/update/', BrandCartUpdateView.as_view(), name='cart_update'),
    path('cart/remove/', BrandCartRemoveView.as_view(), name='cart_remove'),
    # Wishlist
    path('wishlist/', BrandWishlistView.as_view(), name='wishlist'),
    # Commandes
    path('orders/', BrandOrdersView.as_view(), name='orders'),
    # Fidélité
    path('rewards/', BrandRewardsView.as_view(), name='rewards'),
    # Montre personnalisée (SIÈCLE uniquement)
    path('watches/options/', WatchCustomizationOptionsView.as_view(), name='watch_options'),
    path('watches/configs/', SavedWatchConfigView.as_view(), name='watch_configs'),
    path('cart/add-custom-watch/', AddCustomWatchToCartView.as_view(), name='cart_add_custom_watch'),
]
