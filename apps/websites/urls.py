from django.urls import path, include
from . import views

app_name = 'websites'

urlpatterns = [
    path('', views.index, name='index'),

    # ─── Sites web ────────────────────────────────────────────────────────────
    path('sites/', views.website_list, name='website_list'),
    path('sites/nouveau/', views.website_create, name='website_create'),
    path('sites/nouveau/vitrine/', views.website_create_showcase, name='website_create_showcase'),
    path('sites/nouveau/boutique/', views.website_create_store, name='website_create_store'),
    path('sites/<int:pk>/', views.website_detail, name='website_detail'),
    path('sites/<int:pk>/modifier/', views.website_edit, name='website_edit'),
    path('sites/<int:pk>/publier/', views.website_publish, name='website_publish'),
    path('sites/<int:pk>/depublier/', views.website_unpublish, name='website_unpublish'),
    path('sites/<int:pk>/archiver/', views.website_archive, name='website_archive'),
    path('sites/<int:pk>/dupliquer/', views.website_duplicate, name='website_duplicate'),

    # ─── Pages ────────────────────────────────────────────────────────────────
    path('pages/', views.page_list, name='page_list'),
    path('pages/nouvelle/', views.page_create, name='page_create'),
    path('pages/<int:pk>/modifier/', views.page_edit, name='page_edit'),

    # ─── Blog ─────────────────────────────────────────────────────────────────
    path('blog/', views.blog_list, name='blog_list'),
    path('blog/nouveau/', views.blog_create, name='blog_create'),
    path('blog/<int:pk>/modifier/', views.blog_edit, name='blog_edit'),

    # ─── Messages & Devis ─────────────────────────────────────────────────────
    path('messages/', views.message_list, name='message_list'),
    path('devis/', views.quote_request_list, name='quote_request_list'),

    # ─── Dashboard boutique ───────────────────────────────────────────────────
    path('sites/<int:pk>/boutique/', views.store_dashboard, name='store_dashboard'),

    # ─── Catégories boutique ──────────────────────────────────────────────────
    path('sites/<int:pk>/boutique/categories/', views.store_category_list, name='store_category_list'),
    path('sites/<int:pk>/boutique/categories/nouvelle/', views.store_category_create, name='store_category_create'),
    path('sites/<int:pk>/boutique/categories/<int:cat_pk>/modifier/', views.store_category_edit, name='store_category_edit'),

    # ─── Produits boutique ────────────────────────────────────────────────────
    path('sites/<int:pk>/boutique/produits/', views.store_product_list, name='store_product_list'),
    path('sites/<int:pk>/boutique/produits/nouveau/', views.store_product_create, name='store_product_create'),
    path('sites/<int:pk>/boutique/produits/importer-erp/', views.store_product_import_erp, name='store_product_import_erp'),
    path('sites/<int:pk>/boutique/produits/<int:prod_pk>/modifier/', views.store_product_edit, name='store_product_edit'),
    path('sites/<int:pk>/boutique/produits/<int:prod_pk>/supprimer/', views.store_product_delete, name='store_product_delete'),
    path('sites/<int:pk>/boutique/produits/<int:prod_pk>/toggle/', views.store_product_toggle_status, name='store_product_toggle'),

    # ─── Commandes boutique ───────────────────────────────────────────────────
    path('sites/<int:pk>/boutique/commandes/', views.store_order_list, name='store_order_list'),
    path('sites/<int:pk>/boutique/commandes/<int:order_pk>/', views.store_order_detail, name='store_order_detail'),

    # ─── Domaines ────────────────────────────────────────────────────────────
    path('sites/<int:pk>/domaines/', views.domain_settings, name='domain_settings'),

    # Module gestion domaines — dashboard global multi-sites
    path('domaines/', include('apps.websites.urls_domains')),

    # ─── Cloudflare (comptes) ─────────────────────────────────────────────────
    path('cloudflare/', include('apps.websites.urls_cloudflare')),

    # ─── Tunnels Cloudflare ───────────────────────────────────────────────────
    path('tunnels/', include('apps.websites.urls_tunnel')),

    #─── Médiathèque ──────────────────────────────────────────────────────────
    path('sites/<int:pk>/medias/', views.media_library, name='media_library'),

    # ─── Page builder ─────────────────────────────────────────────────────────
    path('sites/<int:pk>/pages/<int:page_pk>/builder/', views.page_builder, name='page_builder'),

    # ─── Checklist publication ────────────────────────────────────────────────
    path('sites/<int:pk>/publier/', views.publish_checklist, name='publish_checklist'),

    # ─── SEO ─────────────────────────────────────────────────────────────────
    path('sites/<int:pk>/seo/', views.seo_dashboard, name='seo_dashboard'),
    path('sites/<int:pk>/seo/pages/<int:page_pk>/', views.seo_page_edit, name='seo_page_edit'),
    path('sites/<int:pk>/sitemap.xml', views.sitemap_view, name='sitemap'),
    path('sites/<int:pk>/robots.txt', views.robots_view, name='robots'),

    # ─── Analytics ────────────────────────────────────────────────────────────
    path('sites/<int:pk>/analytics/', views.website_analytics, name='website_analytics'),

    # ─── Thèmes ───────────────────────────────────────────────────────────────
    path('sites/<int:pk>/themes/', views.theme_list, name='theme_list'),
    path('sites/<int:pk>/themes/<int:theme_pk>/appliquer/', views.theme_apply, name='theme_apply'),
    path('sites/<int:pk>/themes/parametres/', views.theme_settings, name='theme_settings'),

    # ─── Prévisualisation ────────────────────────────────────────────────────
    path('sites/<int:pk>/preview/', views.website_preview, name='website_preview'),
]
