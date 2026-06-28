from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from apps.core.models import Company
from apps.crm.models import Customer
from apps.inventory.models import Product


class WebOrder(models.Model):
    STATUS_CHOICES = [
        ('pending', 'En attente'), ('confirmed', 'Confirmée'), ('processing', 'En préparation'),
        ('shipped', 'Expédiée'), ('delivered', 'Livrée'), ('cancelled', 'Annulée'), ('returned', 'Retournée'),
    ]
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'En attente'), ('paid', 'Payé'), ('failed', 'Échoué'), ('refunded', 'Remboursé'),
    ]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='web_orders')
    brand_key = models.CharField(max_length=20, default='siecle')
    order_number = models.CharField(max_length=30, blank=True)
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True)
    customer_name = models.CharField(max_length=100)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=20, blank=True)
    shipping_address = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    payment_method = models.CharField(max_length=50, blank=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_ttc = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    channel = models.CharField('Canal', max_length=50, default='website')
    notes = models.TextField(blank=True)
    order_date = models.DateTimeField(auto_now_add=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = 'Commande web'
        verbose_name_plural = 'Commandes web'
        ordering = ['-order_date']

    def __str__(self):
        return f'{self.order_number or "WO"} - {self.customer_name}'


class WebOrderLine(models.Model):
    order = models.ForeignKey(WebOrder, on_delete=models.CASCADE, related_name='lines')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, null=True, blank=True)
    product_name = models.CharField(max_length=200)
    product_reference = models.CharField(max_length=100, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        self.total = self.unit_price * self.quantity
        super().save(*args, **kwargs)


class Shipment(models.Model):
    STATUS_CHOICES = [
        ('preparing', 'En préparation'), ('picked', 'Prélevé'), ('packed', 'Emballé'),
        ('shipped', 'Expédié'), ('delivered', 'Livré'), ('failed', 'Échec'),
    ]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='shipments')
    order = models.OneToOneField(WebOrder, on_delete=models.CASCADE, related_name='shipment')
    carrier = models.CharField('Transporteur', max_length=100, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True)
    shipping_label_url = models.URLField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='preparing')
    shipped_at = models.DateTimeField(null=True, blank=True)
    estimated_delivery = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = 'Expédition'

    def __str__(self):
        return f'Expédition - {self.order.order_number}'


class ReturnRequest(models.Model):
    REASON_CHOICES = [
        ('defective', 'Produit défectueux'), ('wrong', 'Mauvais produit'),
        ('wrong_size', 'Mauvaise taille'), ('damaged', 'Endommagé'),
        ('changed_mind', 'Changement d\'avis'), ('late_delivery', 'Retard livraison'), ('other', 'Autre'),
    ]
    STATUS_CHOICES = [
        ('requested', 'Demandé'), ('approved', 'Accepté'), ('refused', 'Refusé'),
        ('awaiting_receipt', 'En attente réception'), ('received', 'Reçu'),
        ('checked', 'Contrôlé'), ('refunded', 'Remboursé'), ('exchanged', 'Échangé'), ('closed', 'Clôturé'),
    ]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='return_requests')
    order = models.ForeignKey(WebOrder, on_delete=models.CASCADE, related_name='returns')
    reason = models.CharField(max_length=20, choices=REASON_CHOICES, default='other')
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='requested')
    refund_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    refund_method = models.CharField(max_length=50, blank=True)
    staff_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Demande de retour'
        ordering = ['-created_at']

    def __str__(self):
        return f'Retour - {self.order.order_number}'


class ReturnItem(models.Model):
    return_request = models.ForeignKey(ReturnRequest, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, null=True, blank=True)
    product_name = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField(default=1)
    reason = models.CharField(max_length=20, choices=ReturnRequest.REASON_CHOICES, default='other')
    condition = models.CharField(max_length=50, blank=True)
    restock = models.BooleanField('Remettre en stock', default=True)

    def __str__(self):
        return f'{self.product_name} x{self.quantity}'


class ExchangeRequest(models.Model):
    STATUS_CHOICES = [('pending', 'En attente'), ('approved', 'Approuvé'), ('shipped', 'Expédié'), ('completed', 'Terminé'), ('cancelled', 'Annulé')]
    return_request = models.OneToOneField(ReturnRequest, on_delete=models.CASCADE, related_name='exchange')
    new_product = models.ForeignKey(Product, on_delete=models.PROTECT, null=True, blank=True)
    new_product_name = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Échange - {self.return_request}'


# ─── CANAUX DE VENTE ───────────────────────────────────────────────────────────

class SalesChannel(models.Model):
    CHANNEL_TYPES = [
        ('erp_store', 'Boutique ERP intégrée'),
        ('shopify', 'Shopify'), ('woocommerce', 'WooCommerce'), ('prestashop', 'PrestaShop'),
        ('magento', 'Magento'), ('amazon', 'Amazon'), ('cdiscount', 'Cdiscount'),
        ('fnac', 'Fnac'), ('mano_mano', 'ManoMano'), ('ebay', 'eBay'),
        ('physical', 'Boutique physique'), ('click_collect', 'Click & Collect'),
        ('b2b', 'Vente B2B'), ('marketplace', 'Marketplace autre'),
    ]
    STATUS_CHOICES = [('active', 'Actif'), ('inactive', 'Inactif'), ('test', 'Test')]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='sales_channels')
    name = models.CharField('Nom du canal', max_length=100)
    channel_type = models.CharField('Type', max_length=20, choices=CHANNEL_TYPES, default='erp_store')
    status = models.CharField('Statut', max_length=10, choices=STATUS_CHOICES, default='active')
    currency = models.CharField('Devise', max_length=3, default='EUR')
    language = models.CharField('Langue', max_length=5, default='fr')
    country = models.CharField('Pays', max_length=100, default='France')
    url = models.URLField('URL', blank=True)
    last_sync = models.DateTimeField('Dernière sync', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Canal de vente'
        verbose_name_plural = 'Canaux de vente'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.get_channel_type_display()})'


class OnlineStore(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='online_stores')
    sales_channel = models.OneToOneField(SalesChannel, on_delete=models.SET_NULL, null=True, blank=True, related_name='store')
    name = models.CharField('Nom boutique', max_length=200)
    domain = models.CharField('Domaine', max_length=200, blank=True)
    logo = models.ImageField('Logo', upload_to='store/logos/', blank=True, null=True)
    currency = models.CharField('Devise', max_length=3, default='EUR')
    language = models.CharField('Langue', max_length=5, default='fr')
    support_email = models.EmailField('Email support', blank=True)
    support_phone = models.CharField('Téléphone support', max_length=20, blank=True)
    terms_conditions = models.TextField('CGV', blank=True)
    return_policy = models.TextField('Politique retour', blank=True)
    shipping_policy = models.TextField('Politique livraison', blank=True)
    meta_title = models.CharField('Meta title', max_length=70, blank=True)
    meta_description = models.CharField('Meta description', max_length=160, blank=True)
    google_analytics_id = models.CharField('GA ID', max_length=30, blank=True)
    facebook_pixel_id = models.CharField('Meta Pixel ID', max_length=30, blank=True)
    is_active = models.BooleanField('Actif', default=True)
    maintenance_mode = models.BooleanField('Mode maintenance', default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Boutique en ligne'

    def __str__(self):
        return self.name


class StoreConnector(models.Model):
    CONNECTOR_TYPES = [
        ('shopify', 'Shopify'), ('woocommerce', 'WooCommerce'), ('prestashop', 'PrestaShop'),
        ('magento', 'Magento'), ('amazon', 'Amazon SP-API'), ('cdiscount', 'Cdiscount'),
        ('fnac', 'Fnac'), ('mano_mano', 'ManoMano'), ('ebay', 'eBay'), ('custom_api', 'API personnalisée'),
    ]
    STATUS_CHOICES = [('active', 'Actif'), ('error', 'Erreur'), ('inactive', 'Inactif'), ('testing', 'Test')]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='store_connectors')
    sales_channel = models.ForeignKey(SalesChannel, on_delete=models.CASCADE, related_name='connectors')
    connector_type = models.CharField('Type', max_length=20, choices=CONNECTOR_TYPES)
    api_url = models.URLField('URL API', blank=True)
    api_key = models.CharField('Clé API', max_length=500, blank=True)
    api_secret = models.CharField('Secret API', max_length=500, blank=True)
    access_token = models.TextField('Token', blank=True)
    status = models.CharField('Statut', max_length=10, choices=STATUS_CHOICES, default='inactive')
    last_sync_products = models.DateTimeField('Sync produits', null=True, blank=True)
    last_sync_stock = models.DateTimeField('Sync stocks', null=True, blank=True)
    last_sync_orders = models.DateTimeField('Sync commandes', null=True, blank=True)
    last_sync_customers = models.DateTimeField('Sync clients', null=True, blank=True)
    last_error = models.TextField('Dernière erreur', blank=True)
    config_json = models.JSONField('Configuration', default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Connecteur boutique'

    def __str__(self):
        return f'{self.get_connector_type_display()} — {self.sales_channel.name}'


class SyncLog(models.Model):
    SYNC_TYPES = [
        ('products', 'Produits'), ('stock', 'Stocks'), ('orders', 'Commandes'),
        ('customers', 'Clients'), ('prices', 'Prix'), ('images', 'Images'),
    ]
    STATUS_CHOICES = [('success', 'Succès'), ('error', 'Erreur'), ('partial', 'Partiel'), ('running', 'En cours')]

    connector = models.ForeignKey(StoreConnector, on_delete=models.CASCADE, related_name='sync_logs')
    sync_type = models.CharField('Type', max_length=20, choices=SYNC_TYPES)
    status = models.CharField('Statut', max_length=10, choices=STATUS_CHOICES, default='running')
    items_processed = models.PositiveIntegerField('Éléments traités', default=0)
    items_success = models.PositiveIntegerField('Succès', default=0)
    items_error = models.PositiveIntegerField('Erreurs', default=0)
    error_details = models.TextField('Détails erreurs', blank=True)
    duration_seconds = models.PositiveIntegerField('Durée (s)', null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Log synchronisation'
        ordering = ['-started_at']

    def __str__(self):
        return f'{self.get_sync_type_display()} — {self.status} — {self.started_at}'


class ProductSyncStatus(models.Model):
    SYNC_STATUS = [
        ('not_published', 'Non publié'), ('pending', 'En attente'), ('published', 'Publié'),
        ('synced', 'Synchronisé'), ('error', 'Erreur'), ('unpublished', 'Dépublié'),
    ]
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='sync_statuses')
    channel = models.ForeignKey(SalesChannel, on_delete=models.CASCADE, related_name='product_statuses')
    external_id = models.CharField('ID externe', max_length=100, blank=True)
    status = models.CharField('Statut', max_length=20, choices=SYNC_STATUS, default='not_published')
    last_synced = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=500, blank=True)
    external_url = models.URLField(blank=True)

    class Meta:
        verbose_name = 'Statut sync produit'
        unique_together = ['product', 'channel']

    def __str__(self):
        return f'{self.product.name} → {self.channel.name}: {self.status}'


# ─── COMPTE CLIENT PUBLIC BOUTIQUE ────────────────────────────────────────────

class CustomerStoreAccount(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='store_accounts')
    crm_customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name='store_account')
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='store_account')
    email = models.EmailField()
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    phone = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    newsletter_opt_in = models.BooleanField('Newsletter', default=False)
    marketing_opt_in = models.BooleanField('Marketing', default=False)
    is_active = models.BooleanField(default=True)
    email_verified = models.BooleanField(default=False)
    total_orders = models.PositiveIntegerField(default=0)
    total_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    loyalty_points = models.PositiveIntegerField(default=0)
    segment = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Compte client boutique'
        unique_together = ['company', 'email']

    def __str__(self):
        return f'{self.first_name} {self.last_name} <{self.email}>'

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'


class CustomerAddress(models.Model):
    ADDRESS_TYPES = [('shipping', 'Livraison'), ('billing', 'Facturation'), ('both', 'Les deux')]
    store_account = models.ForeignKey(CustomerStoreAccount, on_delete=models.CASCADE, related_name='addresses')
    address_type = models.CharField('Type', max_length=10, choices=ADDRESS_TYPES, default='shipping')
    label = models.CharField('Libellé', max_length=50, blank=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    company_name = models.CharField(max_length=100, blank=True)
    address_line1 = models.CharField('Adresse', max_length=200)
    address_line2 = models.CharField('Complément', max_length=200, blank=True)
    zip_code = models.CharField('CP', max_length=10)
    city = models.CharField('Ville', max_length=100)
    country = models.CharField('Pays', max_length=100, default='France')
    phone = models.CharField(max_length=20, blank=True)
    is_default = models.BooleanField('Par défaut', default=False)

    class Meta:
        verbose_name = 'Adresse client'

    def __str__(self):
        return f'{self.first_name} {self.last_name}, {self.address_line1}, {self.city}'


# ─── PROFIL MARQUE CLIENT ──────────────────────────────────────────────────────

BRAND_KEY_CHOICES = [('siecle', 'SIÈCLE'), ('lunea', 'LUNEA')]

THEME_CHOICES = [
    ('siecle-noir-champagne', 'Noir Champagne'),
    ('siecle-bordeaux-nuit', 'Bordeaux Nuit'),
    ('siecle-ivoire-luxe', 'Ivoire Luxe'),
    ('siecle-rouge-signature', 'Rouge Signature'),
    ('lunea-cream-rose', 'Crème Rosé'),
    ('lunea-rose-gold', 'Rose Gold'),
    ('lunea-lunar-black', 'Lunaire Noir'),
    ('lunea-red-velvet', 'Rouge Velours'),
    ('lunea-champagne-light', 'Champagne Clair'),
]

LANGUAGE_CHOICES = [('fr', 'Français'), ('en', 'English'), ('es', 'Español')]

class CustomerBrandProfile(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='customer_brand_profiles')
    store_account = models.ForeignKey(CustomerStoreAccount, on_delete=models.CASCADE, related_name='brand_profiles')
    brand_key = models.CharField(max_length=20, choices=BRAND_KEY_CHOICES, default='siecle')
    preferred_theme = models.CharField(max_length=60, choices=THEME_CHOICES, default='siecle-noir-champagne')
    preferred_language = models.CharField(max_length=10, choices=LANGUAGE_CHOICES, default='fr')
    animations_enabled = models.BooleanField(default=True)
    display_density = models.CharField(max_length=20, default='comfortable', choices=[('comfortable', 'Confortable'), ('compact', 'Compact')])
    marketing_optin = models.BooleanField(default=False)
    newsletter_optin = models.BooleanField(default=False)
    loyalty_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Profil marque client'
        verbose_name_plural = 'Profils marque clients'
        unique_together = [('company', 'store_account', 'brand_key')]

    def __str__(self):
        return f'{self.store_account.email} — {self.brand_key}'

    @classmethod
    def get_or_create_for(cls, store_account, brand_key):
        company = store_account.company
        default_theme = 'siecle-noir-champagne' if brand_key == 'siecle' else 'lunea-cream-rose'
        profile, _ = cls.objects.get_or_create(
            company=company,
            store_account=store_account,
            brand_key=brand_key,
            defaults={'preferred_theme': default_theme},
        )
        return profile


# ─── PANIER & CHECKOUT ─────────────────────────────────────────────────────────

class Cart(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='carts')
    brand_key = models.CharField(max_length=20, choices=BRAND_KEY_CHOICES, default='siecle')
    store_account = models.ForeignKey(CustomerStoreAccount, on_delete=models.SET_NULL, null=True, blank=True, related_name='carts')
    session_key = models.CharField('Clé session', max_length=100, blank=True)
    coupon_code = models.CharField('Code promo', max_length=50, blank=True)
    discount_amount = models.DecimalField('Remise', max_digits=10, decimal_places=2, default=0)
    channel = models.ForeignKey(SalesChannel, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Panier'

    def __str__(self):
        return f'Panier {self.pk}'

    @property
    def subtotal(self):
        return sum(item.total for item in self.items.all())

    @property
    def total(self):
        return max(0, self.subtotal - self.discount_amount)


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Ligne panier'
        unique_together = ['cart', 'product']

    def __str__(self):
        return f'{self.product.name} x{self.quantity}'

    @property
    def total(self):
        return self.unit_price * self.quantity


class CheckoutSession(models.Model):
    STATUS_CHOICES = [
        ('pending', 'En cours'), ('payment_pending', 'Paiement en attente'),
        ('completed', 'Terminé'), ('abandoned', 'Abandonné'), ('failed', 'Échoué'),
    ]
    cart = models.OneToOneField(Cart, on_delete=models.CASCADE, related_name='checkout')
    store_account = models.ForeignKey(CustomerStoreAccount, on_delete=models.SET_NULL, null=True, blank=True)
    shipping_address = models.ForeignKey(CustomerAddress, on_delete=models.SET_NULL, null=True, blank=True, related_name='checkout_shipping')
    billing_address = models.ForeignKey(CustomerAddress, on_delete=models.SET_NULL, null=True, blank=True, related_name='checkout_billing')
    shipping_method_name = models.CharField(max_length=100, blank=True)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_method = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    order = models.OneToOneField(WebOrder, on_delete=models.SET_NULL, null=True, blank=True, related_name='checkout_session')
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Session checkout'

    def __str__(self):
        return f'Checkout {self.pk} — {self.status}'


# ─── PROMOTIONS & CODES PROMO ─────────────────────────────────────────────────

class Promotion(models.Model):
    DISCOUNT_TYPES = [
        ('percentage', 'Pourcentage %'), ('fixed_amount', 'Montant fixe'),
        ('free_shipping', 'Livraison offerte'), ('buy_x_get_y', 'Achetez X, obtenez Y'),
    ]
    STATUS_CHOICES = [
        ('draft', 'Brouillon'), ('active', 'Active'), ('scheduled', 'Planifiée'),
        ('expired', 'Expirée'), ('disabled', 'Désactivée'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='promotions')
    name = models.CharField('Nom', max_length=200)
    description = models.TextField('Description', blank=True)
    discount_type = models.CharField('Type de remise', max_length=20, choices=DISCOUNT_TYPES, default='percentage')
    discount_value = models.DecimalField('Valeur', max_digits=10, decimal_places=2, default=0)
    min_cart_amount = models.DecimalField('Panier minimum', max_digits=10, decimal_places=2, default=0)
    min_quantity = models.PositiveIntegerField('Quantité minimale', default=0)
    max_uses = models.PositiveIntegerField('Utilisations max (0=illimité)', default=0)
    uses_count = models.PositiveIntegerField('Utilisations', default=0)
    applies_to_channel = models.ForeignKey(SalesChannel, on_delete=models.SET_NULL, null=True, blank=True)
    applies_to_category = models.ForeignKey('inventory.ProductCategory', on_delete=models.SET_NULL, null=True, blank=True)
    applies_to_product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField('Statut', max_length=15, choices=STATUS_CHOICES, default='draft')
    starts_at = models.DateTimeField('Début', null=True, blank=True)
    ends_at = models.DateTimeField('Fin', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Promotion'
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class CouponCode(models.Model):
    promotion = models.ForeignKey(Promotion, on_delete=models.CASCADE, related_name='coupon_codes')
    code = models.CharField('Code', max_length=50, unique=True)
    max_uses_per_customer = models.PositiveIntegerField('Max/client', default=1)
    uses_count = models.PositiveIntegerField('Utilisations', default=0)
    is_active = models.BooleanField('Actif', default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Code promo'

    def __str__(self):
        return f'{self.code} ({self.promotion.name})'


class PromotionUsage(models.Model):
    coupon = models.ForeignKey(CouponCode, on_delete=models.CASCADE, related_name='usages')
    order = models.ForeignKey(WebOrder, on_delete=models.CASCADE, related_name='coupon_usages')
    store_account = models.ForeignKey(CustomerStoreAccount, on_delete=models.SET_NULL, null=True, blank=True)
    discount_applied = models.DecimalField(max_digits=10, decimal_places=2)
    used_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Utilisation promotion'

    def __str__(self):
        return f'{self.coupon.code} → {self.order.order_number}'


# ─── PAIEMENTS EN LIGNE ────────────────────────────────────────────────────────

class PaymentProvider(models.Model):
    PROVIDER_TYPES = [
        ('stripe', 'Stripe'), ('paypal', 'PayPal'), ('alma', 'Alma'),
        ('klarna', 'Klarna'), ('bank_transfer', 'Virement bancaire'),
        ('cash_on_delivery', 'Paiement à la livraison'), ('in_store', 'Paiement en magasin'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='payment_providers')
    name = models.CharField('Nom', max_length=100)
    provider_type = models.CharField('Type', max_length=20, choices=PROVIDER_TYPES)
    public_key = models.CharField('Clé publique', max_length=500, blank=True)
    secret_key = models.CharField('Clé secrète', max_length=500, blank=True)
    webhook_secret = models.CharField('Secret webhook', max_length=500, blank=True)
    is_active = models.BooleanField('Actif', default=False)
    test_mode = models.BooleanField('Mode test', default=True)
    config_json = models.JSONField('Configuration', default=dict, blank=True)

    class Meta:
        verbose_name = 'Fournisseur paiement'

    def __str__(self):
        return f'{self.name} ({self.get_provider_type_display()})'


class OnlinePayment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'En attente'), ('authorized', 'Autorisé'), ('paid', 'Payé'),
        ('failed', 'Échoué'), ('cancelled', 'Annulé'), ('refunded', 'Remboursé'),
        ('partially_refunded', 'Partiellement remboursé'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='online_payments')
    order = models.ForeignKey(WebOrder, on_delete=models.CASCADE, related_name='payments')
    provider = models.ForeignKey(PaymentProvider, on_delete=models.PROTECT)
    payment_intent_id = models.CharField('ID intention paiement', max_length=200, blank=True)
    amount = models.DecimalField('Montant', max_digits=12, decimal_places=2)
    currency = models.CharField('Devise', max_length=3, default='EUR')
    status = models.CharField('Statut', max_length=25, choices=STATUS_CHOICES, default='pending')
    payment_method_details = models.CharField('Détails moyen paiement', max_length=200, blank=True)
    receipt_url = models.URLField('URL reçu', blank=True)
    error_message = models.TextField('Erreur', blank=True)
    paid_at = models.DateTimeField('Payé le', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    raw_response = models.JSONField('Réponse brute', default=dict, blank=True)

    class Meta:
        verbose_name = 'Paiement en ligne'
        ordering = ['-created_at']

    def __str__(self):
        return f'Paiement {self.amount}€ — {self.order.order_number} — {self.status}'


class Refund(models.Model):
    REFUND_TYPES = [('full', 'Total'), ('partial', 'Partiel')]
    STATUS_CHOICES = [('pending', 'En attente'), ('processing', 'En cours'), ('completed', 'Terminé'), ('failed', 'Échoué')]

    payment = models.ForeignKey(OnlinePayment, on_delete=models.CASCADE, related_name='refunds')
    return_request = models.ForeignKey(ReturnRequest, on_delete=models.SET_NULL, null=True, blank=True, related_name='refunds')
    refund_type = models.CharField('Type', max_length=10, choices=REFUND_TYPES, default='full')
    amount = models.DecimalField('Montant', max_digits=12, decimal_places=2)
    reason = models.CharField('Raison', max_length=200, blank=True)
    external_refund_id = models.CharField('ID remboursement externe', max_length=200, blank=True)
    status = models.CharField('Statut', max_length=15, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Remboursement'

    def __str__(self):
        return f'Remboursement {self.amount}€ — {self.payment}'


# ─── TRANSPORTEURS & EXPÉDITIONS ──────────────────────────────────────────────

class Carrier(models.Model):
    CARRIER_TYPES = [
        ('colissimo', 'Colissimo'), ('chronopost', 'Chronopost'), ('mondial_relay', 'Mondial Relay'),
        ('dhl', 'DHL'), ('ups', 'UPS'), ('dpd', 'DPD'), ('gls', 'GLS'),
        ('store_pickup', 'Retrait magasin'), ('click_collect', 'Click & Collect'), ('custom', 'Personnalisé'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='carriers')
    name = models.CharField('Nom', max_length=100)
    carrier_type = models.CharField('Type', max_length=20, choices=CARRIER_TYPES, default='custom')
    logo = models.ImageField('Logo', upload_to='carriers/', blank=True, null=True)
    tracking_url_template = models.URLField('URL suivi (use {tracking_number})', blank=True)
    api_endpoint = models.URLField('API endpoint', blank=True)
    api_key = models.CharField('Clé API', max_length=500, blank=True)
    is_active = models.BooleanField('Actif', default=True)
    is_free_for_amount = models.DecimalField('Gratuit à partir de (€)', max_digits=10, decimal_places=2, null=True, blank=True)
    estimated_days_min = models.PositiveIntegerField('Délai min (j)', default=2)
    estimated_days_max = models.PositiveIntegerField('Délai max (j)', default=5)

    class Meta:
        verbose_name = 'Transporteur'

    def __str__(self):
        return self.name


class ShippingMethod(models.Model):
    carrier = models.ForeignKey(Carrier, on_delete=models.CASCADE, related_name='shipping_methods')
    name = models.CharField('Nom', max_length=100)
    description = models.CharField('Description', max_length=200, blank=True)
    base_price = models.DecimalField('Prix de base HT', max_digits=10, decimal_places=2, default=0)
    free_above = models.DecimalField('Gratuit si panier >', max_digits=10, decimal_places=2, null=True, blank=True)
    weight_limit_kg = models.DecimalField('Limite poids (kg)', max_digits=8, decimal_places=3, null=True, blank=True)
    estimated_days = models.PositiveIntegerField('Délai (j)', default=3)
    is_active = models.BooleanField('Actif', default=True)
    order = models.PositiveIntegerField('Ordre affichage', default=0)

    class Meta:
        verbose_name = 'Mode de livraison'
        ordering = ['order', 'base_price']

    def __str__(self):
        return f'{self.carrier.name} — {self.name}'


class TrackingEvent(models.Model):
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name='tracking_events')
    event_date = models.DateTimeField()
    location = models.CharField('Lieu', max_length=200, blank=True)
    description = models.CharField('Description', max_length=300)
    status_code = models.CharField('Code statut', max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Événement suivi'
        ordering = ['-event_date']

    def __str__(self):
        return f'{self.shipment} — {self.description}'


# ─── CRM CLIENT E-COMMERCE ────────────────────────────────────────────────────

class CustomerSegment(models.Model):
    SEGMENT_TYPES = [
        ('new', 'Nouveau client'), ('loyal', 'Client fidèle'), ('vip', 'Client VIP'),
        ('inactive', 'Client inactif'), ('high_value', 'Gros panier'), ('to_reactivate', 'À relancer'),
        ('b2b', 'Client B2B'), ('marketplace', 'Client marketplace'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='customer_segments')
    name = models.CharField('Nom', max_length=100)
    segment_type = models.CharField('Type', max_length=20, choices=SEGMENT_TYPES, default='new')
    description = models.TextField('Description', blank=True)
    color = models.CharField('Couleur', max_length=7, default='#6366F1')
    min_orders = models.PositiveIntegerField('Commandes min', default=0)
    min_spent = models.DecimalField('Dépenses min', max_digits=12, decimal_places=2, default=0)
    is_auto = models.BooleanField('Assignation automatique', default=False)

    class Meta:
        verbose_name = 'Segment client'

    def __str__(self):
        return self.name


class CustomerProfile(models.Model):
    store_account = models.OneToOneField(CustomerStoreAccount, on_delete=models.CASCADE, related_name='profile')
    segment = models.ForeignKey(CustomerSegment, on_delete=models.SET_NULL, null=True, blank=True)
    lifetime_value = models.DecimalField('Valeur vie client', max_digits=12, decimal_places=2, default=0)
    avg_order_value = models.DecimalField('Panier moyen', max_digits=10, decimal_places=2, default=0)
    return_rate = models.DecimalField('Taux retour %', max_digits=5, decimal_places=2, default=0)
    last_order_date = models.DateField('Dernière commande', null=True, blank=True)
    first_order_date = models.DateField('Première commande', null=True, blank=True)
    preferred_channel = models.ForeignKey(SalesChannel, on_delete=models.SET_NULL, null=True, blank=True)
    preferred_categories = models.TextField('Catégories préférées', blank=True)
    acquisition_source = models.CharField('Source acquisition', max_length=100, blank=True)
    notes = models.TextField('Notes internes', blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Profil client e-commerce'

    def __str__(self):
        return f'Profil de {self.store_account}'


class AbandonedCart(models.Model):
    STATUS_CHOICES = [('open', 'Ouvert'), ('reminder_sent', 'Relance envoyée'), ('recovered', 'Récupéré'), ('lost', 'Perdu')]

    cart = models.OneToOneField(Cart, on_delete=models.CASCADE, related_name='abandonment')
    store_account = models.ForeignKey(CustomerStoreAccount, on_delete=models.SET_NULL, null=True, blank=True)
    email = models.EmailField(blank=True)
    cart_value = models.DecimalField('Valeur panier', max_digits=12, decimal_places=2, default=0)
    status = models.CharField('Statut', max_length=20, choices=STATUS_CHOICES, default='open')
    reminder_sent_at = models.DateTimeField(null=True, blank=True)
    recovered_at = models.DateTimeField(null=True, blank=True)
    abandoned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Panier abandonné'
        ordering = ['-abandoned_at']

    def __str__(self):
        return f'Panier abandonné {self.cart_value}€ — {self.email}'


# ─── MARKETPLACES ─────────────────────────────────────────────────────────────

class MarketplaceAccount(models.Model):
    MARKETPLACE_TYPES = [
        ('amazon', 'Amazon'), ('cdiscount', 'Cdiscount'), ('fnac', 'Fnac'),
        ('mano_mano', 'ManoMano'), ('ebay', 'eBay'),
    ]
    STATUS_CHOICES = [('active', 'Actif'), ('suspended', 'Suspendu'), ('inactive', 'Inactif')]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='marketplace_accounts')
    marketplace_type = models.CharField('Marketplace', max_length=20, choices=MARKETPLACE_TYPES)
    account_name = models.CharField('Nom compte', max_length=100)
    seller_id = models.CharField('ID vendeur', max_length=100, blank=True)
    status = models.CharField('Statut', max_length=15, choices=STATUS_CHOICES, default='inactive')
    api_credentials = models.JSONField('Credentials API', default=dict, blank=True)
    commission_rate = models.DecimalField('Taux commission %', max_digits=5, decimal_places=2, default=0)
    last_sync = models.DateTimeField('Dernière sync', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Compte marketplace'

    def __str__(self):
        return f'{self.get_marketplace_type_display()} — {self.account_name}'


class MarketplaceListing(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Brouillon'), ('pending', 'En attente'), ('active', 'Actif'),
        ('inactive', 'Inactif'), ('error', 'Erreur'), ('out_of_stock', 'Rupture'),
    ]

    marketplace = models.ForeignKey(MarketplaceAccount, on_delete=models.CASCADE, related_name='listings')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='marketplace_listings')
    external_sku = models.CharField('SKU externe', max_length=100, blank=True)
    external_asin = models.CharField('ASIN/Ref externe', max_length=100, blank=True)
    status = models.CharField('Statut', max_length=15, choices=STATUS_CHOICES, default='draft')
    price_override = models.DecimalField('Prix spécifique', max_digits=12, decimal_places=2, null=True, blank=True)
    stock_override = models.PositiveIntegerField('Stock spécifique', null=True, blank=True)
    last_synced = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=500, blank=True)

    class Meta:
        verbose_name = 'Listing marketplace'
        unique_together = ['marketplace', 'product']

    def __str__(self):
        return f'{self.product.name} sur {self.marketplace}'


class MarketplaceOrder(models.Model):
    marketplace = models.ForeignKey(MarketplaceAccount, on_delete=models.CASCADE, related_name='orders')
    web_order = models.OneToOneField(WebOrder, on_delete=models.CASCADE, null=True, blank=True, related_name='marketplace_order')
    external_order_id = models.CharField('ID commande externe', max_length=100)
    marketplace_status = models.CharField('Statut marketplace', max_length=50, blank=True)
    commission_amount = models.DecimalField('Commission', max_digits=10, decimal_places=2, default=0)
    imported_at = models.DateTimeField(auto_now_add=True)
    raw_data = models.JSONField('Données brutes', default=dict, blank=True)

    class Meta:
        verbose_name = 'Commande marketplace'

    def __str__(self):
        return f'{self.marketplace} — {self.external_order_id}'


class MarketplaceFee(models.Model):
    marketplace = models.ForeignKey(MarketplaceAccount, on_delete=models.CASCADE, related_name='fees')
    period_start = models.DateField()
    period_end = models.DateField()
    commission_total = models.DecimalField('Commissions', max_digits=12, decimal_places=2, default=0)
    shipping_fees = models.DecimalField('Frais port', max_digits=10, decimal_places=2, default=0)
    other_fees = models.DecimalField('Autres frais', max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField('Total frais', max_digits=12, decimal_places=2, default=0)
    invoice_number = models.CharField('N° facture marketplace', max_length=100, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Frais marketplace'

    def __str__(self):
        return f'{self.marketplace} — {self.period_start} → {self.period_end}'


# ─── CLICK & COLLECT ──────────────────────────────────────────────────────────

class StorePickupPoint(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='pickup_points')
    store = models.ForeignKey('commerce.Store', on_delete=models.CASCADE, related_name='pickup_points', null=True, blank=True)
    name = models.CharField('Nom', max_length=100)
    address = models.TextField('Adresse', blank=True)
    city = models.CharField('Ville', max_length=100, blank=True)
    phone = models.CharField('Téléphone', max_length=20, blank=True)
    opening_hours = models.TextField('Horaires', blank=True)
    is_active = models.BooleanField('Actif', default=True)
    max_reservation_days = models.PositiveIntegerField('Durée max réservation (j)', default=7)

    class Meta:
        verbose_name = 'Point retrait'

    def __str__(self):
        return self.name


class ClickAndCollectOrder(models.Model):
    STATUS_CHOICES = [
        ('new', 'Nouvelle'), ('preparing', 'En préparation'), ('ready', 'Prête au retrait'),
        ('picked_up', 'Retirée'), ('cancelled', 'Annulée'), ('expired', 'Expirée'),
    ]
    web_order = models.OneToOneField(WebOrder, on_delete=models.CASCADE, related_name='click_collect')
    pickup_point = models.ForeignKey(StorePickupPoint, on_delete=models.PROTECT, related_name='orders')
    status = models.CharField('Statut', max_length=15, choices=STATUS_CHOICES, default='new')
    ready_at = models.DateTimeField('Prêt le', null=True, blank=True)
    pickup_deadline = models.DateField('À retirer avant le', null=True, blank=True)
    picked_up_at = models.DateTimeField('Retiré le', null=True, blank=True)
    pickup_code = models.CharField('Code retrait', max_length=20, blank=True)
    staff_notes = models.TextField('Notes staff', blank=True)

    class Meta:
        verbose_name = 'Commande Click & Collect'

    def __str__(self):
        return f'C&C — {self.web_order.order_number} — {self.get_status_display()}'
