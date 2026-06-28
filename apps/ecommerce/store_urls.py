from django.urls import path
from . import store_views

app_name = 'store'

urlpatterns = [
    path('', store_views.store_home, name='store_home'),
    path('recherche/', store_views.store_search, name='store_search'),
    path('categorie/<slug:slug>/', store_views.store_category, name='store_category'),
    path('produit/<slug:slug>/', store_views.store_product_detail, name='store_product_detail'),

    # Panier
    path('panier/', store_views.cart_view, name='cart'),
    path('panier/ajouter/', store_views.cart_add, name='cart_add'),
    path('panier/modifier/', store_views.cart_update, name='cart_update'),
    path('panier/supprimer/', store_views.cart_remove, name='cart_remove'),
    path('panier/code-promo/', store_views.cart_apply_coupon, name='cart_apply_coupon'),

    # Checkout
    path('commande/', store_views.checkout_view, name='checkout'),
    path('commande/confirmation/', store_views.checkout_success, name='checkout_success'),

    # Compte client
    path('connexion/', store_views.customer_login, name='customer_login'),
    path('inscription/', store_views.customer_register, name='customer_register'),
    path('deconnexion/', store_views.customer_logout, name='customer_logout'),
    path('mon-compte/', store_views.customer_account, name='customer_account'),
    path('mon-compte/commandes/', store_views.customer_orders, name='customer_orders'),
    path('mon-compte/commandes/<int:pk>/', store_views.customer_order_detail, name='customer_order_detail'),
    path('mon-compte/retours/', store_views.customer_returns, name='customer_returns'),

    # Suivi
    path('suivi/', store_views.order_tracking, name='order_tracking'),
]
