from django import forms
from .models import (
    WebOrder, SalesChannel, OnlineStore, StoreConnector, Promotion, CouponCode,
    PaymentProvider, Carrier, ShippingMethod, ReturnRequest, CustomerSegment,
    MarketplaceAccount, MarketplaceListing, StorePickupPoint, ClickAndCollectOrder,
    CustomerStoreAccount,
)


def _apply_css(form):
    for field in form.fields.values():
        w = field.widget
        if isinstance(w, forms.CheckboxInput):
            w.attrs.setdefault('class', 'form-check-input')
        elif isinstance(w, forms.Select):
            w.attrs.setdefault('class', 'form-select form-select-sm')
        elif isinstance(w, forms.Textarea):
            w.attrs.setdefault('class', 'form-control form-control-sm')
            w.attrs.setdefault('rows', 3)
        else:
            w.attrs.setdefault('class', 'form-control form-control-sm')


class WebOrderForm(forms.ModelForm):
    class Meta:
        model = WebOrder
        fields = [
            'customer', 'customer_name', 'customer_email', 'customer_phone',
            'shipping_address', 'status', 'payment_status', 'payment_method',
            'subtotal', 'shipping_cost', 'total_ttc', 'channel',
            'tracking_number', 'notes',
        ]
        widgets = {
            'shipping_address': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company:
            from apps.crm.models import Customer
            self.fields['customer'].queryset = Customer.objects.filter(company=company)
            self.fields['customer'].required = False
        _apply_css(self)


class SalesChannelForm(forms.ModelForm):
    class Meta:
        model = SalesChannel
        fields = ['name', 'channel_type', 'status', 'currency', 'language', 'country', 'url']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_css(self)


class OnlineStoreForm(forms.ModelForm):
    class Meta:
        model = OnlineStore
        fields = [
            'name', 'domain', 'currency', 'language', 'support_email', 'support_phone',
            'terms_conditions', 'return_policy', 'shipping_policy',
            'meta_title', 'meta_description', 'google_analytics_id', 'facebook_pixel_id',
            'is_active', 'maintenance_mode',
        ]
        widgets = {
            'terms_conditions': forms.Textarea(attrs={'rows': 5}),
            'return_policy': forms.Textarea(attrs={'rows': 4}),
            'shipping_policy': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_css(self)


class StoreConnectorForm(forms.ModelForm):
    class Meta:
        model = StoreConnector
        fields = [
            'sales_channel', 'connector_type', 'api_url',
            'api_key', 'api_secret', 'access_token',
        ]
        widgets = {
            'api_secret': forms.PasswordInput(render_value=True),
            'access_token': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company:
            self.fields['sales_channel'].queryset = SalesChannel.objects.filter(company=company)
        _apply_css(self)


class PromotionForm(forms.ModelForm):
    class Meta:
        model = Promotion
        fields = [
            'name', 'description', 'discount_type', 'discount_value',
            'min_cart_amount', 'min_quantity', 'max_uses',
            'applies_to_channel', 'applies_to_product',
            'status', 'starts_at', 'ends_at',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
            'starts_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'ends_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company:
            self.fields['applies_to_channel'].queryset = SalesChannel.objects.filter(company=company)
            from apps.inventory.models import Product
            self.fields['applies_to_product'].queryset = Product.objects.filter(company=company)
        self.fields['applies_to_channel'].required = False
        self.fields['applies_to_product'].required = False
        _apply_css(self)


class CouponCodeForm(forms.ModelForm):
    class Meta:
        model = CouponCode
        fields = ['code', 'max_uses_per_customer', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_css(self)


class PaymentProviderForm(forms.ModelForm):
    class Meta:
        model = PaymentProvider
        fields = [
            'name', 'provider_type', 'public_key', 'secret_key',
            'webhook_secret', 'is_active', 'test_mode',
        ]
        widgets = {
            'secret_key': forms.PasswordInput(render_value=True),
            'webhook_secret': forms.PasswordInput(render_value=True),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_css(self)


class CarrierForm(forms.ModelForm):
    class Meta:
        model = Carrier
        fields = [
            'name', 'carrier_type', 'tracking_url_template', 'api_endpoint', 'api_key',
            'is_active', 'is_free_for_amount', 'estimated_days_min', 'estimated_days_max',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_css(self)


class ShippingMethodForm(forms.ModelForm):
    class Meta:
        model = ShippingMethod
        fields = ['carrier', 'name', 'description', 'base_price', 'free_above', 'weight_limit_kg', 'estimated_days', 'is_active', 'order']

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company:
            self.fields['carrier'].queryset = Carrier.objects.filter(company=company)
        _apply_css(self)


class ReturnRequestAdminForm(forms.ModelForm):
    class Meta:
        model = ReturnRequest
        fields = ['reason', 'description', 'status', 'refund_amount', 'refund_method', 'staff_notes']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
            'staff_notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_css(self)


class CustomerSegmentForm(forms.ModelForm):
    class Meta:
        model = CustomerSegment
        fields = ['name', 'segment_type', 'description', 'color', 'min_orders', 'min_spent', 'is_auto']
        widgets = {'description': forms.Textarea(attrs={'rows': 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_css(self)


class MarketplaceAccountForm(forms.ModelForm):
    class Meta:
        model = MarketplaceAccount
        fields = ['marketplace_type', 'account_name', 'seller_id', 'status', 'commission_rate']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_css(self)


class MarketplaceListingForm(forms.ModelForm):
    class Meta:
        model = MarketplaceListing
        fields = ['marketplace', 'product', 'external_sku', 'external_asin', 'status', 'price_override', 'stock_override']

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company:
            self.fields['marketplace'].queryset = MarketplaceAccount.objects.filter(company=company)
            from apps.inventory.models import Product
            self.fields['product'].queryset = Product.objects.filter(company=company)
        _apply_css(self)


class StorePickupPointForm(forms.ModelForm):
    class Meta:
        model = StorePickupPoint
        fields = ['name', 'store', 'address', 'city', 'phone', 'opening_hours', 'is_active', 'max_reservation_days']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 2}),
            'opening_hours': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company:
            try:
                from apps.commerce.models import Store
                self.fields['store'].queryset = Store.objects.filter(company=company)
            except Exception:
                pass
        _apply_css(self)


class CustomerStoreAccountForm(forms.ModelForm):
    class Meta:
        model = CustomerStoreAccount
        fields = ['email', 'first_name', 'last_name', 'phone', 'newsletter_opt_in', 'marketing_opt_in', 'is_active', 'loyalty_points', 'segment']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_css(self)
