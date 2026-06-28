from django.urls import path
from . import views

app_name = 'ecommerce'

urlpatterns = [
    path('', views.index, name='index'),

    # Dashboard
    path('tableau-de-bord/', views.ecommerce_dashboard, name='dashboard'),

    # Commandes web
    path('commandes/', views.order_list, name='order_list'),
    path('commandes/nouvelle/', views.order_create, name='order_create'),
    path('commandes/<int:pk>/', views.order_detail, name='order_detail'),
    path('commandes/<int:pk>/modifier/', views.order_edit, name='order_edit'),
    path('commandes/<int:pk>/expedier/', views.order_ship, name='order_ship'),

    # Catalogue produits
    path('catalogue/', views.product_list, name='product_list'),

    # ExpÃ©ditions & retours
    path('expeditions/', views.shipment_list, name='shipment_list'),
    path('retours/', views.return_list, name='return_list'),
    path('retours/<int:pk>/', views.return_detail, name='return_detail'),

    # Canaux de vente
    path('canaux/', views.sales_channel_list, name='sales_channel_list'),
    path('canaux/nouveau/', views.sales_channel_create, name='sales_channel_create'),
    path('canaux/<int:pk>/modifier/', views.sales_channel_edit, name='sales_channel_edit'),
    path('canaux/<int:pk>/supprimer/', views.sales_channel_delete, name='sales_channel_delete'),

    # Boutique en ligne
    path('boutique-admin/', views.online_store_form, name='online_store_create'),
    path('boutique-admin/<int:pk>/', views.online_store_detail, name='online_store_detail'),
    path('boutique-admin/<int:pk>/modifier/', views.online_store_form, name='online_store_edit'),

    # Synchronisation
    path('synchronisation/', views.sync_dashboard, name='sync_dashboard'),

    # Promotions
    path('promotions/', views.promotion_list, name='promotion_list'),
    path('promotions/nouvelle/', views.promotion_create, name='promotion_create'),
    path('promotions/<int:pk>/modifier/', views.promotion_edit, name='promotion_edit'),
    path('promotions/<int:pk>/toggle/', views.promotion_toggle, name='promotion_toggle'),
    path('promotions/<int:promo_pk>/codes/nouveau/', views.coupon_create, name='coupon_create'),

    # Paiements
    path('paiements/', views.payment_list, name='payment_list'),
    path('paiements/fournisseurs/', views.payment_provider_list, name='payment_provider_list'),
    path('paiements/fournisseurs/nouveau/', views.payment_provider_form, name='payment_provider_create'),
    path('paiements/fournisseurs/<int:pk>/modifier/', views.payment_provider_form, name='payment_provider_edit'),

    # Transporteurs
    path('transporteurs/', views.carrier_list, name='carrier_list'),
    path('transporteurs/nouveau/', views.carrier_create, name='carrier_create'),
    path('transporteurs/<int:pk>/modifier/', views.carrier_edit, name='carrier_edit'),
    path('transporteurs/<int:carrier_pk>/modes/nouveau/', views.shipping_method_create, name='shipping_method_create'),

    # CRM client e-commerce
    path('clients/', views.customer_profile_list, name='customer_profile_list'),
    path('clients/<int:pk>/', views.customer_profile_detail, name='customer_profile_detail'),
    path('clients/segments/', views.customer_segment_list, name='customer_segment_list'),
    path('clients/segments/nouveau/', views.customer_segment_create, name='customer_segment_create'),
    path('clients/segments/<int:pk>/modifier/', views.customer_segment_edit, name='customer_segment_edit'),
    path('clients/paniers-abandonnes/', views.abandoned_cart_list, name='abandoned_cart_list'),

    # Marketplaces
    path('marketplaces/', views.marketplace_list, name='marketplace_list'),
    path('marketplaces/nouveau/', views.marketplace_create, name='marketplace_create'),
    path('marketplaces/<int:pk>/modifier/', views.marketplace_edit, name='marketplace_edit'),
    path('marketplaces/listings/nouveau/', views.marketplace_listing_form, name='marketplace_listing_create'),
    path('marketplaces/listings/<int:pk>/modifier/', views.marketplace_listing_form, name='marketplace_listing_edit'),

    # Click & Collect
    path('click-collect/', views.pickup_point_list, name='pickup_point_list'),
    path('click-collect/nouveau/', views.pickup_point_form, name='pickup_point_create'),
    path('click-collect/<int:pk>/modifier/', views.pickup_point_form, name='pickup_point_edit'),
    path('commandes/exporter/', views.order_export, name='order_export'),
    path('commandes/importer/', views.order_import, name='order_import'),
    path('commandes/<int:pk>/preparer/', views.order_prepare, name='order_prepare'),
    path('commandes/<int:pk>/rembourser/', views.order_refund, name='order_refund'),
    path('produits/nouveau/', views.product_create, name='product_create'),
    path('produits/<int:pk>/', views.product_detail, name='product_detail'),
    path('produits/<int:pk>/modifier/', views.product_edit, name='product_edit'),
    path('produits/importer/', views.product_import, name='product_import'),
    path('produits/<int:pk>/publier/', views.product_publish, name='product_publish'),
    path('produits/publier-selection/', views.product_publish_bulk, name='product_publish_bulk'),
    path('produits/synchroniser/', views.product_sync, name='product_sync'),
    path('retours/nouveau/', views.return_create, name='return_create'),
    path('retours/<int:pk>/accepter/', views.return_accept, name='return_accept'),
    path('retours/accepter-selection/', views.return_accept_bulk, name='return_accept_bulk'),
    path('retours/<int:pk>/rembourser/', views.return_refund, name='return_refund'),
    path('retours/rembourser-selection/', views.return_refund_bulk, name='return_refund_bulk'),
    path('expeditions/nouveau/', views.shipment_create, name='shipment_create'),
    path('expeditions/<int:pk>/etiquette/', views.shipment_label, name='shipment_label'),
    path('expeditions/<int:pk>/notifier/', views.shipment_notify, name='shipment_notify'),
    path('expeditions/<int:pk>/litige/', views.shipment_dispute, name='shipment_dispute'),
    path('expeditions/exporter/', views.shipment_export, name='shipment_export'),]

