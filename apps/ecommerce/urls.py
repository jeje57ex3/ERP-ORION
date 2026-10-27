from django.urls import path
from . import views
from . import views_siecle as siecle

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
    path('expeditions/exporter/', views.shipment_export, name='shipment_export'),

    # ── Back-office SIECLE ────────────────────────────────────────────────────
    #
    # apps/ecommerce/views_siecle.py portait DIX-HUIT vues et aucune route.
    # Ses huit gabarits existaient et citaient quinze noms d'URL inexistants.
    # Le module n'etait meme pas importable : il reclamait deux modeles
    # (StoreProductVariant, SyncLog) et un formset qui n'existaient nulle
    # part -- tous trois ajoutes avec ces routes.
    #
    # Les noms de parametres (pk, image_pk, variant_pk, log_pk) sont ceux
    # que les gabarits passent en arguments NOMMES ; les renommer casserait
    # a nouveau les memes boutons.
    path('articles/', siecle.article_list, name='article_list'),
    path('articles/nouveau/', siecle.article_create, name='article_create'),
    path('articles/<int:pk>/', siecle.article_detail, name='article_detail'),
    path('articles/<int:pk>/modifier/', siecle.article_edit, name='article_edit'),
    path('articles/<int:pk>/publier/', siecle.article_publish, name='article_publish'),
    path('articles/<int:pk>/images/ajouter/', siecle.article_image_upload, name='article_image_upload'),
    path('articles/<int:pk>/images/<int:image_pk>/supprimer/', siecle.article_image_delete, name='article_image_delete'),
    path('articles/<int:pk>/images/<int:image_pk>/principale/', siecle.article_image_set_primary, name='article_image_set_primary'),
    path('articles/<int:pk>/images/ordre/', siecle.article_image_reorder, name='article_image_reorder'),
    path('articles/<int:pk>/declinaisons/', siecle.article_variants, name='article_variants'),
    path('articles/<int:pk>/declinaisons/ajouter/', siecle.article_variant_add, name='article_variant_add'),
    path('articles/<int:pk>/declinaisons/<int:variant_pk>/supprimer/', siecle.article_variant_delete, name='article_variant_delete'),

    path('synchronisation/journal/', siecle.sync_log_list, name='sync_log_list'),
    path('synchronisation/journal/<int:log_pk>/rejouer/', siecle.sync_retry, name='sync_retry'),

    path('fidelite/', siecle.loyalty_status_list, name='loyalty_status_list'),
    path('fidelite/<int:pk>/', siecle.loyalty_status_detail, name='loyalty_status_detail'),
    path('fidelite/<int:pk>/ajuster/', siecle.loyalty_status_adjust, name='loyalty_status_adjust'),

    path('parrainage/', siecle.referral_list, name='referral_list'),
]

