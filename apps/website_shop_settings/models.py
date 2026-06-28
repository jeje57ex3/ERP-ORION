from django.conf import settings
from django.db import models
from django.utils import timezone


class WebsiteShopSettings(models.Model):
    BRAND_CHOICES = [
        ('siecle', 'SIÈCLE'),
        ('lunea', 'LUNEA'),
    ]

    company = models.ForeignKey(
        'core.Company',
        on_delete=models.CASCADE,
        related_name='website_shop_settings',
    )
    website = models.ForeignKey(
        'websites.Website',
        on_delete=models.CASCADE,
        related_name='shop_settings',
        null=True,
        blank=True,
    )
    brand_key = models.CharField(max_length=40, choices=BRAND_CHOICES)

    site_name = models.CharField(max_length=180)
    site_title = models.CharField(max_length=220, blank=True)
    site_description = models.TextField(blank=True)

    is_site_enabled = models.BooleanField(default=True)
    is_shop_enabled = models.BooleanField(default=True)
    unavailable_message = models.TextField(
        blank=True,
        default='Cette boutique est temporairement indisponible.',
    )

    default_currency = models.CharField(max_length=8, default='EUR')
    default_language = models.CharField(max_length=12, default='fr')
    supported_languages = models.JSONField(default=list, blank=True)

    customer_accounts_enabled = models.BooleanField(default=True)
    guest_checkout_enabled = models.BooleanField(default=True)
    wishlist_enabled = models.BooleanField(default=True)
    reviews_enabled = models.BooleanField(default=True)
    gift_cards_enabled = models.BooleanField(default=False)
    loyalty_enabled = models.BooleanField(default=False)
    private_pricing_enabled = models.BooleanField(default=False)

    order_prefix = models.CharField(max_length=20, default='ORD')
    order_number_padding = models.PositiveIntegerField(default=6)

    support_email = models.EmailField(blank=True)
    contact_email = models.EmailField(blank=True)
    orders_email = models.EmailField(blank=True)
    returns_email = models.EmailField(blank=True)

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='website_shop_settings_updated',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'website_shop_settings'
        unique_together = [('company', 'brand_key')]
        ordering = ['brand_key']

    def __str__(self):
        return f'{self.site_name} — {self.brand_key}'

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('website_shop_settings:general', kwargs={'pk': self.pk})


class PaymentSettings(models.Model):
    PAYMENT_PROVIDER_CHOICES = [
        ('stripe', 'Stripe'),
        ('manual', 'Paiement manuel'),
        ('disabled', 'Désactivé'),
    ]
    STRIPE_MODE_CHOICES = [
        ('test', 'Test'),
        ('live', 'Live'),
    ]

    shop_settings = models.OneToOneField(
        WebsiteShopSettings,
        on_delete=models.CASCADE,
        related_name='payment_settings',
    )
    payments_enabled = models.BooleanField(default=False)
    default_provider = models.CharField(
        max_length=40, choices=PAYMENT_PROVIDER_CHOICES, default='stripe',
    )
    stripe_enabled = models.BooleanField(default=False)
    stripe_mode = models.CharField(max_length=20, choices=STRIPE_MODE_CHOICES, default='test')
    stripe_publishable_key = models.CharField(max_length=255, blank=True)
    stripe_secret_key_encrypted = models.TextField(blank=True)
    stripe_webhook_secret_encrypted = models.TextField(blank=True)
    stripe_success_url = models.URLField(blank=True)
    stripe_cancel_url = models.URLField(blank=True)
    allow_card_payments = models.BooleanField(default=True)
    allow_apple_pay = models.BooleanField(default=False)
    allow_google_pay = models.BooleanField(default=False)
    payment_capture_mode = models.CharField(
        max_length=40, default='automatic',
        choices=[('automatic', 'Capture automatique'), ('manual', 'Capture manuelle')],
    )
    minimum_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    maximum_order_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
    )
    payment_failed_message = models.TextField(
        blank=True,
        default="Votre paiement n'a pas abouti. Vous pouvez réessayer.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'website_shop_settings'

    def __str__(self):
        return f'Paiements — {self.shop_settings.brand_key}'


class CheckoutSettings(models.Model):
    shop_settings = models.OneToOneField(
        WebsiteShopSettings,
        on_delete=models.CASCADE,
        related_name='checkout_settings',
    )
    checkout_enabled = models.BooleanField(default=True)
    require_customer_account = models.BooleanField(default=False)
    allow_guest_checkout = models.BooleanField(default=True)
    require_phone = models.BooleanField(default=True)
    require_billing_address = models.BooleanField(default=True)
    require_shipping_address = models.BooleanField(default=True)
    allow_different_billing_address = models.BooleanField(default=True)
    terms_acceptance_required = models.BooleanField(default=True)
    privacy_acceptance_required = models.BooleanField(default=True)
    marketing_optin_enabled = models.BooleanField(default=True)
    cart_expiration_hours = models.PositiveIntegerField(default=72)
    abandoned_cart_enabled = models.BooleanField(default=False)
    abandoned_cart_delay_hours = models.PositiveIntegerField(default=24)
    success_page_url = models.CharField(max_length=255, blank=True)
    cancel_page_url = models.CharField(max_length=255, blank=True)
    checkout_note_enabled = models.BooleanField(default=True)
    gift_message_enabled = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'website_shop_settings'

    def __str__(self):
        return f'Checkout — {self.shop_settings.brand_key}'


class ShippingSettings(models.Model):
    shop_settings = models.OneToOneField(
        WebsiteShopSettings,
        on_delete=models.CASCADE,
        related_name='shipping_settings',
    )
    shipping_enabled = models.BooleanField(default=True)
    default_country = models.CharField(max_length=80, default='France')
    allowed_countries = models.JSONField(default=list, blank=True)
    preparation_delay_min_days = models.PositiveIntegerField(default=2)
    preparation_delay_max_days = models.PositiveIntegerField(default=5)
    delivery_delay_min_days = models.PositiveIntegerField(default=3)
    delivery_delay_max_days = models.PositiveIntegerField(default=7)
    free_shipping_enabled = models.BooleanField(default=False)
    free_shipping_threshold = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    default_shipping_price = models.DecimalField(max_digits=10, decimal_places=2, default=4.90)
    pickup_enabled = models.BooleanField(default=False)
    shipping_message = models.TextField(
        blank=True,
        default='Les commandes sont préparées sous 2 à 5 jours ouvrés.',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'website_shop_settings'

    def __str__(self):
        return f'Livraison — {self.shop_settings.brand_key}'


class ShippingMethod(models.Model):
    shop_settings = models.ForeignKey(
        WebsiteShopSettings,
        on_delete=models.CASCADE,
        related_name='shipping_methods',
    )
    name = models.CharField(max_length=180)
    code = models.SlugField(max_length=80)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_order_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
    )
    countries = models.JSONField(default=list, blank=True)
    estimated_min_days = models.PositiveIntegerField(default=3)
    estimated_max_days = models.PositiveIntegerField(default=7)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=100)

    class Meta:
        app_label = 'website_shop_settings'
        unique_together = [('shop_settings', 'code')]
        ordering = ['sort_order', 'name']

    def __str__(self):
        return f'{self.name} — {self.shop_settings.brand_key}'


class ReturnSettings(models.Model):
    shop_settings = models.OneToOneField(
        WebsiteShopSettings,
        on_delete=models.CASCADE,
        related_name='return_settings',
    )
    returns_enabled = models.BooleanField(default=True)
    return_period_days = models.PositiveIntegerField(default=14)
    customer_pays_return_shipping = models.BooleanField(default=True)
    require_return_request = models.BooleanField(default=True)
    allow_exchange = models.BooleanField(default=True)
    allow_refund = models.BooleanField(default=True)
    allow_store_credit = models.BooleanField(default=False)
    exclude_personalized_products = models.BooleanField(default=True)
    exclude_opened_beauty_products = models.BooleanField(default=True)
    return_instructions = models.TextField(
        blank=True,
        default='Pour demander un retour, contactez notre service client.',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'website_shop_settings'

    def __str__(self):
        return f'Retours — {self.shop_settings.brand_key}'


class TaxSettings(models.Model):
    shop_settings = models.OneToOneField(
        WebsiteShopSettings,
        on_delete=models.CASCADE,
        related_name='tax_settings',
    )
    taxes_enabled = models.BooleanField(default=True)
    prices_include_tax = models.BooleanField(default=True)
    default_tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=20)
    tax_label = models.CharField(max_length=80, default='TVA')
    company_vat_number = models.CharField(max_length=80, blank=True)
    show_tax_details_in_checkout = models.BooleanField(default=True)
    show_tax_details_in_invoice = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'website_shop_settings'

    def __str__(self):
        return f'Taxes — {self.shop_settings.brand_key}'


class EmailSettings(models.Model):
    shop_settings = models.OneToOneField(
        WebsiteShopSettings,
        on_delete=models.CASCADE,
        related_name='email_settings',
    )
    emails_enabled = models.BooleanField(default=True)
    sender_name = models.CharField(max_length=180)
    sender_email = models.EmailField()
    reply_to_email = models.EmailField(blank=True)
    order_confirmation_enabled = models.BooleanField(default=True)
    payment_confirmation_enabled = models.BooleanField(default=True)
    shipping_confirmation_enabled = models.BooleanField(default=True)
    password_reset_enabled = models.BooleanField(default=True)
    account_creation_enabled = models.BooleanField(default=True)
    contact_notification_enabled = models.BooleanField(default=True)
    admin_order_notification_enabled = models.BooleanField(default=True)
    admin_notification_email = models.EmailField(blank=True)
    email_footer_text = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'website_shop_settings'

    def __str__(self):
        return f'Emails — {self.shop_settings.brand_key}'


class LegalSettings(models.Model):
    shop_settings = models.OneToOneField(
        WebsiteShopSettings,
        on_delete=models.CASCADE,
        related_name='legal_settings',
    )
    legal_pages_enabled = models.BooleanField(default=True)
    company_name = models.CharField(max_length=180, blank=True)
    company_address = models.TextField(blank=True)
    company_siret = models.CharField(max_length=80, blank=True)
    company_vat_number = models.CharField(max_length=80, blank=True)
    publication_director = models.CharField(max_length=180, blank=True)
    hosting_provider = models.CharField(max_length=180, blank=True)
    hosting_address = models.TextField(blank=True)
    cgv_content = models.TextField(blank=True)
    privacy_policy_content = models.TextField(blank=True)
    cookie_policy_content = models.TextField(blank=True)
    legal_notice_content = models.TextField(blank=True)
    shipping_returns_content = models.TextField(blank=True)
    require_terms_acceptance = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'website_shop_settings'

    def __str__(self):
        return f'Légal — {self.shop_settings.brand_key}'


class SEOSettings(models.Model):
    shop_settings = models.OneToOneField(
        WebsiteShopSettings,
        on_delete=models.CASCADE,
        related_name='seo_settings',
    )
    seo_enabled = models.BooleanField(default=True)
    meta_title = models.CharField(max_length=220, blank=True)
    meta_description = models.TextField(blank=True)
    og_title = models.CharField(max_length=220, blank=True)
    og_description = models.TextField(blank=True)
    og_image = models.ImageField(upload_to='seo/og/', null=True, blank=True)
    robots_index = models.BooleanField(default=True)
    robots_follow = models.BooleanField(default=True)
    sitemap_enabled = models.BooleanField(default=True)
    robots_txt_content = models.TextField(blank=True)
    google_site_verification = models.CharField(max_length=255, blank=True)
    meta_pixel_id = models.CharField(max_length=120, blank=True)
    google_analytics_id = models.CharField(max_length=120, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'website_shop_settings'

    def __str__(self):
        return f'SEO — {self.shop_settings.brand_key}'


class CookieSettings(models.Model):
    shop_settings = models.OneToOneField(
        WebsiteShopSettings,
        on_delete=models.CASCADE,
        related_name='cookie_settings',
    )
    cookie_banner_enabled = models.BooleanField(default=True)
    necessary_cookies_always_enabled = models.BooleanField(default=True)
    analytics_cookies_enabled = models.BooleanField(default=False)
    marketing_cookies_enabled = models.BooleanField(default=False)
    require_consent_before_tracking = models.BooleanField(default=True)
    banner_title = models.CharField(max_length=180, default='Gestion des cookies')
    banner_text = models.TextField(
        default='Nous utilisons des cookies pour améliorer votre expérience.',
    )
    accept_button_label = models.CharField(max_length=80, default='Accepter')
    reject_button_label = models.CharField(max_length=80, default='Refuser')
    customize_button_label = models.CharField(max_length=80, default='Personnaliser')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'website_shop_settings'

    def __str__(self):
        return f'Cookies — {self.shop_settings.brand_key}'


class StockSettings(models.Model):
    shop_settings = models.OneToOneField(
        WebsiteShopSettings,
        on_delete=models.CASCADE,
        related_name='stock_settings',
    )
    stock_management_enabled = models.BooleanField(default=True)
    allow_backorders = models.BooleanField(default=False)
    allow_preorders = models.BooleanField(default=False)
    hide_out_of_stock_products = models.BooleanField(default=False)
    low_stock_threshold = models.PositiveIntegerField(default=5)
    show_stock_status = models.BooleanField(default=True)
    show_exact_stock_quantity = models.BooleanField(default=False)
    stock_reserved_on_add_to_cart = models.BooleanField(default=False)
    stock_reserved_on_payment = models.BooleanField(default=True)
    out_of_stock_label = models.CharField(max_length=80, default='Indisponible')
    low_stock_label = models.CharField(max_length=80, default='Stock limité')
    preorder_label = models.CharField(max_length=80, default='Précommande')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'website_shop_settings'

    def __str__(self):
        return f'Stock — {self.shop_settings.brand_key}'


class SiteMaintenanceSettings(models.Model):
    shop_settings = models.OneToOneField(
        WebsiteShopSettings,
        on_delete=models.CASCADE,
        related_name='maintenance_settings',
    )
    maintenance_enabled = models.BooleanField(default=False)
    allow_admin_preview = models.BooleanField(default=True)
    maintenance_title = models.CharField(max_length=180, default='Site en maintenance')
    maintenance_message = models.TextField(default='Nous revenons très bientôt.')
    show_waitlist_form = models.BooleanField(default=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'website_shop_settings'

    def __str__(self):
        return f'Maintenance — {self.shop_settings.brand_key}'

    def is_active_now(self):
        now = timezone.now()
        if not self.maintenance_enabled:
            return False
        if self.starts_at and self.starts_at > now:
            return False
        if self.ends_at and self.ends_at < now:
            return False
        return True


class ShopSecuritySettings(models.Model):
    shop_settings = models.OneToOneField(
        WebsiteShopSettings,
        on_delete=models.CASCADE,
        related_name='security_settings',
    )
    force_https = models.BooleanField(default=True)
    csrf_protection_enabled = models.BooleanField(default=True)
    rate_limit_checkout_enabled = models.BooleanField(default=True)
    max_checkout_attempts_per_hour = models.PositiveIntegerField(default=10)
    rate_limit_login_enabled = models.BooleanField(default=True)
    max_login_attempts_per_hour = models.PositiveIntegerField(default=5)
    block_suspicious_orders = models.BooleanField(default=True)
    require_email_verification = models.BooleanField(default=False)
    allowed_domains = models.JSONField(default=list, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'website_shop_settings'

    def __str__(self):
        return f'Sécurité — {self.shop_settings.brand_key}'
