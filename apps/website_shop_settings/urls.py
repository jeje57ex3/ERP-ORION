from django.urls import path

from apps.website_shop_settings import views, api

app_name = 'website_shop_settings'

urlpatterns = [
    # ERP admin views
    path('erp/websites/shop-settings/', views.shop_settings_dashboard, name='dashboard'),
    path('erp/websites/shop-settings/<int:pk>/general/', views.general_settings_view, name='general'),
    path('erp/websites/shop-settings/<int:pk>/payments/', views.payment_settings_view, name='payments'),
    path('erp/websites/shop-settings/<int:pk>/checkout/', views.checkout_settings_view, name='checkout'),
    path('erp/websites/shop-settings/<int:pk>/shipping/', views.shipping_settings_view, name='shipping'),
    path('erp/websites/shop-settings/<int:pk>/returns/', views.return_settings_view, name='returns'),
    path('erp/websites/shop-settings/<int:pk>/taxes/', views.tax_settings_view, name='taxes'),
    path('erp/websites/shop-settings/<int:pk>/emails/', views.email_settings_view, name='emails'),
    path('erp/websites/shop-settings/<int:pk>/legal/', views.legal_settings_view, name='legal'),
    path('erp/websites/shop-settings/<int:pk>/seo/', views.seo_settings_view, name='seo'),
    path('erp/websites/shop-settings/<int:pk>/cookies/', views.cookie_settings_view, name='cookies'),
    path('erp/websites/shop-settings/<int:pk>/stock/', views.stock_settings_view, name='stock'),
    path('erp/websites/shop-settings/<int:pk>/maintenance/', views.maintenance_settings_view, name='maintenance'),
    path('erp/websites/shop-settings/<int:pk>/security/', views.security_settings_view, name='security'),

    # Public API
    path('api/v1/websites/<str:brand_key>/public-settings/', api.public_shop_settings_api, name='api_public_settings'),
    path('api/v1/websites/<str:brand_key>/checkout-settings/', api.checkout_settings_api, name='api_checkout_settings'),
    path('api/v1/websites/<str:brand_key>/shipping-methods/', api.shipping_methods_api, name='api_shipping_methods'),
    path('api/v1/websites/<str:brand_key>/legal-pages/', api.legal_pages_api, name='api_legal_pages'),
]
