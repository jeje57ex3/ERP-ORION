from django.contrib import admin

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


class PaymentSettingsInline(admin.StackedInline):
    model = PaymentSettings
    extra = 0
    readonly_fields = ['updated_at']
    exclude = ['stripe_secret_key_encrypted', 'stripe_webhook_secret_encrypted']


class CheckoutSettingsInline(admin.StackedInline):
    model = CheckoutSettings
    extra = 0
    readonly_fields = ['updated_at']


class ShippingSettingsInline(admin.StackedInline):
    model = ShippingSettings
    extra = 0
    readonly_fields = ['updated_at']


class ShippingMethodInline(admin.TabularInline):
    model = ShippingMethod
    extra = 0


class ReturnSettingsInline(admin.StackedInline):
    model = ReturnSettings
    extra = 0
    readonly_fields = ['updated_at']


class TaxSettingsInline(admin.StackedInline):
    model = TaxSettings
    extra = 0
    readonly_fields = ['updated_at']


class EmailSettingsInline(admin.StackedInline):
    model = EmailSettings
    extra = 0
    readonly_fields = ['updated_at']


class SiteMaintenanceInline(admin.StackedInline):
    model = SiteMaintenanceSettings
    extra = 0
    readonly_fields = ['updated_at']


@admin.register(WebsiteShopSettings)
class WebsiteShopSettingsAdmin(admin.ModelAdmin):
    list_display = ['brand_key', 'site_name', 'company', 'is_site_enabled', 'is_shop_enabled', 'updated_at']
    list_filter = ['brand_key', 'is_site_enabled', 'is_shop_enabled']
    search_fields = ['site_name', 'brand_key']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [
        PaymentSettingsInline,
        CheckoutSettingsInline,
        ShippingSettingsInline,
        ShippingMethodInline,
        ReturnSettingsInline,
        TaxSettingsInline,
        EmailSettingsInline,
        SiteMaintenanceInline,
    ]


@admin.register(ShippingMethod)
class ShippingMethodAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'price', 'is_active', 'sort_order']
    list_filter = ['is_active', 'shop_settings__brand_key']
