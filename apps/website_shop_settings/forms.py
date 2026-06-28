from django import forms

from apps.website_shop_settings.crypto import encrypt_secret
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


class WebsiteShopSettingsForm(forms.ModelForm):
    class Meta:
        model = WebsiteShopSettings
        fields = [
            'site_name', 'site_title', 'site_description',
            'is_site_enabled', 'is_shop_enabled', 'unavailable_message',
            'default_currency', 'default_language',
            'customer_accounts_enabled', 'guest_checkout_enabled',
            'wishlist_enabled', 'reviews_enabled', 'gift_cards_enabled',
            'loyalty_enabled', 'private_pricing_enabled',
            'order_prefix', 'order_number_padding',
            'support_email', 'contact_email', 'orders_email', 'returns_email',
        ]


class PaymentSettingsForm(forms.ModelForm):
    stripe_secret_key = forms.CharField(
        required=False,
        widget=forms.PasswordInput(render_value=False),
        label='Clé secrète Stripe',
        help_text='Laisser vide pour conserver la clé existante.',
    )
    stripe_webhook_secret = forms.CharField(
        required=False,
        widget=forms.PasswordInput(render_value=False),
        label='Secret webhook Stripe',
        help_text='Laisser vide pour conserver le secret existant.',
    )

    class Meta:
        model = PaymentSettings
        fields = [
            'payments_enabled', 'default_provider',
            'stripe_enabled', 'stripe_mode', 'stripe_publishable_key',
            'stripe_success_url', 'stripe_cancel_url',
            'allow_card_payments', 'allow_apple_pay', 'allow_google_pay',
            'payment_capture_mode',
            'minimum_order_amount', 'maximum_order_amount',
            'payment_failed_message',
        ]

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.cleaned_data.get('stripe_secret_key'):
            instance.stripe_secret_key_encrypted = encrypt_secret(
                self.cleaned_data['stripe_secret_key']
            )
        if self.cleaned_data.get('stripe_webhook_secret'):
            instance.stripe_webhook_secret_encrypted = encrypt_secret(
                self.cleaned_data['stripe_webhook_secret']
            )
        if commit:
            instance.save()
        return instance


class CheckoutSettingsForm(forms.ModelForm):
    class Meta:
        model = CheckoutSettings
        exclude = ['shop_settings', 'updated_at']


class ShippingSettingsForm(forms.ModelForm):
    class Meta:
        model = ShippingSettings
        exclude = ['shop_settings', 'updated_at']


class ReturnSettingsForm(forms.ModelForm):
    class Meta:
        model = ReturnSettings
        exclude = ['shop_settings', 'updated_at']


class TaxSettingsForm(forms.ModelForm):
    class Meta:
        model = TaxSettings
        exclude = ['shop_settings', 'updated_at']


class EmailSettingsForm(forms.ModelForm):
    class Meta:
        model = EmailSettings
        exclude = ['shop_settings', 'updated_at']


class LegalSettingsForm(forms.ModelForm):
    class Meta:
        model = LegalSettings
        exclude = ['shop_settings', 'updated_at']
        widgets = {
            'cgv_content': forms.Textarea(attrs={'rows': 12}),
            'privacy_policy_content': forms.Textarea(attrs={'rows': 12}),
            'cookie_policy_content': forms.Textarea(attrs={'rows': 12}),
            'legal_notice_content': forms.Textarea(attrs={'rows': 12}),
            'shipping_returns_content': forms.Textarea(attrs={'rows': 12}),
        }


class SEOSettingsForm(forms.ModelForm):
    class Meta:
        model = SEOSettings
        exclude = ['shop_settings', 'updated_at']


class CookieSettingsForm(forms.ModelForm):
    class Meta:
        model = CookieSettings
        exclude = ['shop_settings', 'updated_at']


class StockSettingsForm(forms.ModelForm):
    class Meta:
        model = StockSettings
        exclude = ['shop_settings', 'updated_at']


class SiteMaintenanceSettingsForm(forms.ModelForm):
    class Meta:
        model = SiteMaintenanceSettings
        exclude = ['shop_settings', 'updated_at']
        widgets = {
            'starts_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'ends_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }


class ShopSecuritySettingsForm(forms.ModelForm):
    class Meta:
        model = ShopSecuritySettings
        exclude = ['shop_settings', 'updated_at']


class ShippingMethodForm(forms.ModelForm):
    class Meta:
        model = ShippingMethod
        exclude = ['shop_settings']
