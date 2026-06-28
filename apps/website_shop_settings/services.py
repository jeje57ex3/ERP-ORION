from decimal import Decimal

from apps.website_shop_settings.defaults import DEFAULT_SHOP_SETTINGS
from apps.website_shop_settings.models import (
    CheckoutSettings,
    CookieSettings,
    EmailSettings,
    LegalSettings,
    PaymentSettings,
    ReturnSettings,
    SEOSettings,
    ShippingMethod,
    ShippingSettings,
    ShopSecuritySettings,
    SiteMaintenanceSettings,
    StockSettings,
    TaxSettings,
    WebsiteShopSettings,
)


def create_default_shop_settings(company, brand_key, website=None, updated_by=None):
    defaults = DEFAULT_SHOP_SETTINGS.get(brand_key, {})

    shop_settings, created = WebsiteShopSettings.objects.get_or_create(
        company=company,
        brand_key=brand_key,
        defaults={
            'website': website,
            'site_name': defaults.get('site_name', brand_key.upper()),
            'site_title': defaults.get('site_title', ''),
            'site_description': defaults.get('site_description', ''),
            'order_prefix': defaults.get('order_prefix', 'ORD'),
            'default_currency': defaults.get('default_currency', 'EUR'),
            'default_language': defaults.get('default_language', 'fr'),
            'support_email': defaults.get('support_email', ''),
            'contact_email': defaults.get('contact_email', ''),
            'orders_email': defaults.get('orders_email', ''),
            'returns_email': defaults.get('returns_email', ''),
            'updated_by': updated_by,
        },
    )

    PaymentSettings.objects.get_or_create(shop_settings=shop_settings)
    CheckoutSettings.objects.get_or_create(shop_settings=shop_settings)
    ShippingSettings.objects.get_or_create(shop_settings=shop_settings)
    ReturnSettings.objects.get_or_create(shop_settings=shop_settings)
    TaxSettings.objects.get_or_create(shop_settings=shop_settings)
    SEOSettings.objects.get_or_create(shop_settings=shop_settings)
    CookieSettings.objects.get_or_create(shop_settings=shop_settings)
    StockSettings.objects.get_or_create(shop_settings=shop_settings)
    SiteMaintenanceSettings.objects.get_or_create(shop_settings=shop_settings)
    ShopSecuritySettings.objects.get_or_create(shop_settings=shop_settings)

    sender_email = defaults.get('orders_email', '') or defaults.get('contact_email', '')
    EmailSettings.objects.get_or_create(
        shop_settings=shop_settings,
        defaults={
            'sender_name': shop_settings.site_name,
            'sender_email': sender_email or 'no-reply@example.com',
        },
    )

    LegalSettings.objects.get_or_create(
        shop_settings=shop_settings,
        defaults={'company_name': ''},
    )

    ShippingMethod.objects.get_or_create(
        shop_settings=shop_settings,
        code='standard',
        defaults={
            'name': 'Livraison standard',
            'description': 'Livraison standard à domicile.',
            'price': Decimal('4.90'),
            'estimated_min_days': 3,
            'estimated_max_days': 7,
            'is_active': True,
            'sort_order': 100,
        },
    )

    return shop_settings


def ensure_all_related_settings(shop_settings):
    """Create missing related settings objects for an existing WebsiteShopSettings."""
    PaymentSettings.objects.get_or_create(shop_settings=shop_settings)
    CheckoutSettings.objects.get_or_create(shop_settings=shop_settings)
    ShippingSettings.objects.get_or_create(shop_settings=shop_settings)
    ReturnSettings.objects.get_or_create(shop_settings=shop_settings)
    TaxSettings.objects.get_or_create(shop_settings=shop_settings)
    SEOSettings.objects.get_or_create(shop_settings=shop_settings)
    CookieSettings.objects.get_or_create(shop_settings=shop_settings)
    StockSettings.objects.get_or_create(shop_settings=shop_settings)
    SiteMaintenanceSettings.objects.get_or_create(shop_settings=shop_settings)
    ShopSecuritySettings.objects.get_or_create(shop_settings=shop_settings)
    EmailSettings.objects.get_or_create(
        shop_settings=shop_settings,
        defaults={
            'sender_name': shop_settings.site_name,
            'sender_email': shop_settings.orders_email or 'no-reply@example.com',
        },
    )
    LegalSettings.objects.get_or_create(
        shop_settings=shop_settings,
        defaults={'company_name': ''},
    )
