from django.core.exceptions import ObjectDoesNotExist

from apps.website_shop_settings.models import WebsiteShopSettings


_SELECT_RELATED = [
    'payment_settings',
    'checkout_settings',
    'shipping_settings',
    'return_settings',
    'tax_settings',
    'email_settings',
    'legal_settings',
    'seo_settings',
    'cookie_settings',
    'stock_settings',
    'maintenance_settings',
    'security_settings',
]


def get_shop_settings(company, brand_key):
    return (
        WebsiteShopSettings.objects
        .select_related(*_SELECT_RELATED)
        .get(company=company, brand_key=brand_key)
    )


def get_shop_settings_by_pk(pk):
    return (
        WebsiteShopSettings.objects
        .select_related(*_SELECT_RELATED)
        .get(pk=pk)
    )


def list_shop_settings_for_company(company):
    return (
        WebsiteShopSettings.objects
        .filter(company=company)
        .select_related(*_SELECT_RELATED)
        .order_by('brand_key')
    )


def get_public_shop_settings(company, brand_key):
    s = get_shop_settings(company, brand_key)
    return {
        'brand_key': s.brand_key,
        'site_name': s.site_name,
        'site_title': s.site_title,
        'site_description': s.site_description,
        'is_site_enabled': s.is_site_enabled,
        'is_shop_enabled': s.is_shop_enabled,
        'unavailable_message': s.unavailable_message,
        'default_currency': s.default_currency,
        'default_language': s.default_language,
        'supported_languages': s.supported_languages,
        'customer_accounts_enabled': s.customer_accounts_enabled,
        'guest_checkout_enabled': s.guest_checkout_enabled,
        'wishlist_enabled': s.wishlist_enabled,
        'reviews_enabled': s.reviews_enabled,
        'gift_cards_enabled': s.gift_cards_enabled,
        'loyalty_enabled': s.loyalty_enabled,
    }


def get_checkout_public_settings(company, brand_key):
    s = get_shop_settings(company, brand_key)
    c = s.checkout_settings
    p = s.payment_settings
    sh = s.shipping_settings
    r = s.return_settings
    t = s.tax_settings
    return {
        'checkout_enabled': c.checkout_enabled,
        'allow_guest_checkout': c.allow_guest_checkout,
        'require_customer_account': c.require_customer_account,
        'require_phone': c.require_phone,
        'require_billing_address': c.require_billing_address,
        'terms_acceptance_required': c.terms_acceptance_required,
        'privacy_acceptance_required': c.privacy_acceptance_required,
        'cart_expiration_hours': c.cart_expiration_hours,
        'payments_enabled': p.payments_enabled,
        'stripe_enabled': p.stripe_enabled,
        'stripe_publishable_key': p.stripe_publishable_key,
        'stripe_mode': p.stripe_mode,
        'allow_card_payments': p.allow_card_payments,
        'allow_apple_pay': p.allow_apple_pay,
        'allow_google_pay': p.allow_google_pay,
        'minimum_order_amount': str(p.minimum_order_amount),
        'shipping_enabled': sh.shipping_enabled,
        'free_shipping_enabled': sh.free_shipping_enabled,
        'free_shipping_threshold': str(sh.free_shipping_threshold),
        'default_shipping_price': str(sh.default_shipping_price),
        'returns_enabled': r.returns_enabled,
        'return_period_days': r.return_period_days,
        'taxes_enabled': t.taxes_enabled,
        'prices_include_tax': t.prices_include_tax,
        'default_tax_rate': str(t.default_tax_rate),
    }
