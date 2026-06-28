from rest_framework import serializers

from apps.website_shop_settings.models import ShippingMethod


class PublicShopSettingsSerializer(serializers.Serializer):
    brand_key = serializers.CharField()
    site_name = serializers.CharField()
    site_title = serializers.CharField()
    site_description = serializers.CharField()
    is_site_enabled = serializers.BooleanField()
    is_shop_enabled = serializers.BooleanField()
    unavailable_message = serializers.CharField()
    default_currency = serializers.CharField()
    default_language = serializers.CharField()
    customer_accounts_enabled = serializers.BooleanField()
    guest_checkout_enabled = serializers.BooleanField()
    wishlist_enabled = serializers.BooleanField()
    reviews_enabled = serializers.BooleanField()
    gift_cards_enabled = serializers.BooleanField()
    loyalty_enabled = serializers.BooleanField()


class CheckoutPublicSettingsSerializer(serializers.Serializer):
    checkout_enabled = serializers.BooleanField()
    allow_guest_checkout = serializers.BooleanField()
    require_customer_account = serializers.BooleanField()
    require_phone = serializers.BooleanField()
    terms_acceptance_required = serializers.BooleanField()
    privacy_acceptance_required = serializers.BooleanField()
    payments_enabled = serializers.BooleanField()
    stripe_enabled = serializers.BooleanField()
    stripe_publishable_key = serializers.CharField()
    stripe_mode = serializers.CharField()
    allow_card_payments = serializers.BooleanField()
    allow_apple_pay = serializers.BooleanField()
    allow_google_pay = serializers.BooleanField()
    minimum_order_amount = serializers.CharField()
    shipping_enabled = serializers.BooleanField()
    free_shipping_enabled = serializers.BooleanField()
    free_shipping_threshold = serializers.CharField()
    default_shipping_price = serializers.CharField()
    returns_enabled = serializers.BooleanField()
    return_period_days = serializers.IntegerField()
    taxes_enabled = serializers.BooleanField()
    prices_include_tax = serializers.BooleanField()
    default_tax_rate = serializers.CharField()


class ShippingMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingMethod
        fields = [
            'name', 'code', 'description', 'price',
            'min_order_amount', 'estimated_min_days', 'estimated_max_days',
        ]
