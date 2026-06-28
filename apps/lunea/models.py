"""
LUNEA — Modèles e-commerce maquillage premium.

Tous les modèles sont liés à company pour compatibilité SaaS multi-entreprises Orion ERP.
"""
from django.db import models
from django.utils.text import slugify
from django.contrib.auth.models import User


# ── Référence Company (ForeignKey) ───────────────────────────────────────────

def _company():
    from apps.core.models import Company
    return Company


# ── Catégories & Produits ─────────────────────────────────────────────────────

class ProductCategory(models.Model):
    company = models.ForeignKey('core.Company', on_delete=models.CASCADE, related_name='lunea_categories')
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='lunea/categories/', blank=True, null=True)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children')
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order', 'name']
        unique_together = [('company', 'slug')]
        verbose_name = 'Catégorie LUNEA'
        verbose_name_plural = 'Catégories LUNEA'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class LuneaProduct(models.Model):
    SKIN_TYPE_CHOICES = [
        ('all', 'Tous types'),
        ('dry', 'Sèche'),
        ('oily', 'Grasse'),
        ('combination', 'Mixte'),
        ('sensitive', 'Sensible'),
        ('normal', 'Normale'),
    ]
    FINISH_CHOICES = [
        ('matte', 'Mat'),
        ('luminous', 'Lumineux'),
        ('satin', 'Satiné'),
        ('dewy', 'Hydraté'),
        ('natural', 'Naturel'),
    ]
    COVERAGE_CHOICES = [
        ('light', 'Légère'),
        ('medium', 'Moyenne'),
        ('full', 'Couvrant'),
        ('buildable', 'Modulable'),
    ]

    company = models.ForeignKey('core.Company', on_delete=models.CASCADE, related_name='lunea_products')
    category = models.ForeignKey(ProductCategory, on_delete=models.SET_NULL, null=True, related_name='products')
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    short_description = models.TextField(blank=True)
    description = models.TextField(blank=True)
    ingredients = models.TextField(blank=True)
    how_to_use = models.TextField(blank=True)
    benefits = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    compare_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    skin_types = models.CharField(max_length=200, blank=True)
    finish = models.CharField(max_length=20, choices=FINISH_CHOICES, blank=True)
    coverage = models.CharField(max_length=20, choices=COVERAGE_CHOICES, blank=True)
    hold_hours = models.PositiveIntegerField(null=True, blank=True)
    loyalty_points = models.PositiveIntegerField(default=0)
    is_best_seller = models.BooleanField(default=False)
    is_new = models.BooleanField(default=True)
    is_vegan = models.BooleanField(default=False)
    is_limited_edition = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    has_shades = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Produit LUNEA'
        verbose_name_plural = 'Produits LUNEA'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def rating_avg(self):
        agg = self.reviews.filter(is_approved=True).aggregate(avg=models.Avg('rating'))
        return round(agg['avg'] or 0, 1)

    @property
    def review_count(self):
        return self.reviews.filter(is_approved=True).count()


class ProductShade(models.Model):
    UNDERTONE_CHOICES = [
        ('cool', 'Froid'),
        ('neutral', 'Neutre'),
        ('warm', 'Chaud'),
        ('olive', 'Olive'),
    ]
    SKIN_TONE_CHOICES = [
        ('very_fair', 'Très claire'),
        ('fair', 'Claire'),
        ('medium', 'Medium'),
        ('tan', 'Mate'),
        ('dark', 'Foncée'),
        ('deep', 'Très foncée'),
    ]

    product = models.ForeignKey(LuneaProduct, on_delete=models.CASCADE, related_name='shades')
    name = models.CharField(max_length=100)
    hex_color = models.CharField(max_length=7, blank=True)
    undertone = models.CharField(max_length=10, choices=UNDERTONE_CHOICES, blank=True)
    recommended_skin_tones = models.CharField(max_length=200, blank=True)
    stock = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']
        verbose_name = 'Teinte'
        verbose_name_plural = 'Teintes'

    def __str__(self):
        return f'{self.product.name} — {self.name}'

    @property
    def is_in_stock(self):
        return self.stock > 0


class ProductImage(models.Model):
    product = models.ForeignKey(LuneaProduct, on_delete=models.CASCADE, related_name='images')
    shade = models.ForeignKey(ProductShade, on_delete=models.SET_NULL, null=True, blank=True, related_name='images')
    image = models.ImageField(upload_to='lunea/products/')
    alt_text = models.CharField(max_length=200, blank=True)
    is_primary = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']


class ProductShadeMedia(models.Model):
    product = models.ForeignKey(LuneaProduct, on_delete=models.CASCADE, related_name='shade_media')
    shade_name = models.CharField(max_length=100)
    skin_tone = models.CharField(max_length=20, choices=ProductShade.SKIN_TONE_CHOICES)
    image = models.ImageField(upload_to='lunea/shade_media/', null=True, blank=True)
    video = models.FileField(upload_to='lunea/shade_videos/', null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Média teinte / carnation'
        verbose_name_plural = 'Médias teinte / carnation'


class ProductStock(models.Model):
    product = models.OneToOneField(LuneaProduct, on_delete=models.CASCADE, related_name='stock_info')
    quantity = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=5)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_low(self):
        return self.quantity <= self.low_stock_threshold


# ── Avis clients ──────────────────────────────────────────────────────────────

class ProductReview(models.Model):
    AGE_CHOICES = [
        ('18-24', '18-24 ans'), ('25-34', '25-34 ans'), ('35-44', '35-44 ans'),
        ('45-54', '45-54 ans'), ('55+', '55 ans et plus'),
    ]

    company = models.ForeignKey('core.Company', on_delete=models.CASCADE, related_name='lunea_reviews')
    product = models.ForeignKey(LuneaProduct, on_delete=models.CASCADE, related_name='reviews')
    customer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    rating = models.PositiveSmallIntegerField(default=5)
    title = models.CharField(max_length=200, blank=True)
    comment = models.TextField()
    shade_name = models.CharField(max_length=100, blank=True)
    skin_type = models.CharField(max_length=20, blank=True)
    skin_tone = models.CharField(max_length=20, choices=ProductShade.SKIN_TONE_CHOICES, blank=True)
    undertone = models.CharField(max_length=10, choices=ProductShade.UNDERTONE_CHOICES, blank=True)
    age_range = models.CharField(max_length=10, choices=AGE_CHOICES, blank=True)
    image = models.ImageField(upload_to='lunea/reviews/', null=True, blank=True)
    is_verified_purchase = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Avis produit'
        verbose_name_plural = 'Avis produits'

    def __str__(self):
        return f'{self.product.name} — {self.rating}★'


# ── Routines beauté ───────────────────────────────────────────────────────────

class BeautyRoutine(models.Model):
    company = models.ForeignKey('core.Company', on_delete=models.CASCADE, related_name='beauty_routines')
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='lunea/routines/', null=True, blank=True)
    skin_type = models.CharField(max_length=20, blank=True)
    skin_tone = models.CharField(max_length=20, blank=True)
    occasion = models.CharField(max_length=100, blank=True)
    duration_minutes = models.PositiveIntegerField(default=15)
    is_quick = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']
        unique_together = [('company', 'slug')]
        verbose_name = 'Routine beauté'
        verbose_name_plural = 'Routines beauté'

    def __str__(self):
        return self.name

    @property
    def total_price(self):
        return sum(item.product.price * item.quantity for item in self.items.select_related('product'))

    @property
    def total_points(self):
        return sum(item.product.loyalty_points * item.quantity for item in self.items.select_related('product'))


class BeautyRoutineItem(models.Model):
    routine = models.ForeignKey(BeautyRoutine, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(LuneaProduct, on_delete=models.CASCADE)
    step = models.PositiveIntegerField(default=1)
    quantity = models.PositiveIntegerField(default=1)
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['step']


# ── Looks maquillage ──────────────────────────────────────────────────────────

class MakeupLook(models.Model):
    company = models.ForeignKey('core.Company', on_delete=models.CASCADE, related_name='makeup_looks')
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='lunea/looks/')
    face_map_image = models.ImageField(upload_to='lunea/face_maps/', null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Look maquillage'
        verbose_name_plural = 'Looks maquillage'

    def __str__(self):
        return self.name


class MakeupLookProduct(models.Model):
    ZONE_CHOICES = [
        ('teint', 'Teint'), ('joues', 'Joues'), ('yeux', 'Yeux'),
        ('sourcils', 'Sourcils'), ('levres', 'Lèvres'), ('highlighter', 'Highlighter'),
    ]

    look = models.ForeignKey(MakeupLook, on_delete=models.CASCADE, related_name='products')
    product = models.ForeignKey(LuneaProduct, on_delete=models.CASCADE)
    zone = models.CharField(max_length=20, choices=ZONE_CHOICES)
    shade_name = models.CharField(max_length=100, blank=True)
    zone_x = models.FloatField(default=50, help_text='Position X en % sur le face map')
    zone_y = models.FloatField(default=50, help_text='Position Y en % sur le face map')

    class Meta:
        ordering = ['zone']


# ── Outils beauté (Quiz, Finder, Diagnostic) ─────────────────────────────────

class CustomerBeautyProfile(models.Model):
    company = models.ForeignKey('core.Company', on_delete=models.CASCADE, related_name='beauty_profiles')
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='beauty_profiles')
    skin_type = models.CharField(max_length=20, blank=True)
    skin_tone = models.CharField(max_length=20, choices=ProductShade.SKIN_TONE_CHOICES, blank=True)
    undertone = models.CharField(max_length=10, choices=ProductShade.UNDERTONE_CHOICES, blank=True)
    preferred_finish = models.CharField(max_length=20, blank=True)
    preferred_coverage = models.CharField(max_length=20, blank=True)
    concerns = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('company', 'customer')]
        verbose_name = 'Profil beauté client'
        verbose_name_plural = 'Profils beauté clients'


class CustomerShadeProfile(models.Model):
    company = models.ForeignKey('core.Company', on_delete=models.CASCADE, related_name='shade_profiles')
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='shade_profiles')
    foundation_shade = models.CharField(max_length=100, blank=True)
    concealer_shade = models.CharField(max_length=100, blank=True)
    powder_shade = models.CharField(max_length=100, blank=True)
    lip_shade = models.CharField(max_length=100, blank=True)
    finder_used_count = models.PositiveIntegerField(default=0)
    last_finder_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('company', 'customer')]
        verbose_name = 'Profil teintes client'
        verbose_name_plural = 'Profils teintes clients'


class BeautyQuizResult(models.Model):
    company = models.ForeignKey('core.Company', on_delete=models.CASCADE, related_name='quiz_results')
    customer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    session_key = models.CharField(max_length=40, blank=True)
    answers = models.JSONField(default=dict)
    recommended_products = models.ManyToManyField(LuneaProduct, blank=True)
    skin_type = models.CharField(max_length=20, blank=True)
    skin_tone = models.CharField(max_length=20, blank=True)
    undertone = models.CharField(max_length=10, blank=True)
    routine_id = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Résultat quiz beauté'
        verbose_name_plural = 'Résultats quiz beauté'


class ShadeFinderResult(models.Model):
    company = models.ForeignKey('core.Company', on_delete=models.CASCADE, related_name='shade_finder_results')
    customer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    session_key = models.CharField(max_length=40, blank=True)
    skin_tone = models.CharField(max_length=20)
    undertone = models.CharField(max_length=10)
    skin_type = models.CharField(max_length=20, blank=True)
    finish = models.CharField(max_length=20, blank=True)
    coverage = models.CharField(max_length=20, blank=True)
    recommended_foundation = models.ForeignKey(LuneaProduct, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    recommended_concealer = models.ForeignKey(LuneaProduct, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    recommended_powder = models.ForeignKey(LuneaProduct, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    recommended_lip = models.ForeignKey(LuneaProduct, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    foundation_shade = models.CharField(max_length=100, blank=True)
    concealer_shade = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Résultat finder de teinte'
        verbose_name_plural = 'Résultats finder de teinte'


class CustomerSkinDiagnostic(models.Model):
    company = models.ForeignKey('core.Company', on_delete=models.CASCADE, related_name='skin_diagnostics')
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='skin_diagnostics')
    skin_type = models.CharField(max_length=20)
    skin_tone = models.CharField(max_length=20)
    concerns = models.TextField(blank=True)
    season = models.CharField(max_length=20, blank=True)
    preferred_finish = models.CharField(max_length=20, blank=True)
    recommended_routine = models.ForeignKey(BeautyRoutine, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Diagnostic peau'
        verbose_name_plural = 'Diagnostics peau'


# ── Wishlist ──────────────────────────────────────────────────────────────────

class CustomerWishlistItem(models.Model):
    company = models.ForeignKey('core.Company', on_delete=models.CASCADE, related_name='wishlist_items')
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='lunea_wishlist')
    product = models.ForeignKey(LuneaProduct, on_delete=models.CASCADE)
    shade_name = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('company', 'customer', 'product')]
        ordering = ['-created_at']
        verbose_name = 'Favori client'
        verbose_name_plural = 'Favoris clients'


# ── Fidélité ──────────────────────────────────────────────────────────────────

class LoyaltyTier(models.Model):
    company = models.ForeignKey('core.Company', on_delete=models.CASCADE, related_name='loyalty_tiers')
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120)
    min_points = models.PositiveIntegerField(default=0)
    color = models.CharField(max_length=7, default='#c9a45c')
    perks = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'min_points']
        verbose_name = 'Niveau fidélité'
        verbose_name_plural = 'Niveaux fidélité'

    def __str__(self):
        return self.name


class LoyaltyAccount(models.Model):
    company = models.ForeignKey('core.Company', on_delete=models.CASCADE, related_name='lunea_loyalty_accounts')
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='lunea_loyalty')
    tier = models.ForeignKey(LoyaltyTier, on_delete=models.SET_NULL, null=True, blank=True)
    points_balance = models.PositiveIntegerField(default=0)
    points_lifetime = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('company', 'customer')]
        verbose_name = 'Compte fidélité'
        verbose_name_plural = 'Comptes fidélité'

    def __str__(self):
        return f'{self.customer.get_full_name()} — {self.points_balance} pts'


class LoyaltyTransaction(models.Model):
    TYPE_CHOICES = [
        ('earn', 'Gain'), ('redeem', 'Utilisation'), ('expire', 'Expiration'),
        ('bonus', 'Bonus'), ('adjust', 'Ajustement'),
    ]

    account = models.ForeignKey(LoyaltyAccount, on_delete=models.CASCADE, related_name='transactions')
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    points = models.IntegerField()
    description = models.CharField(max_length=200)
    order_id = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Transaction fidélité'
        verbose_name_plural = 'Transactions fidélité'


class LoyaltyMission(models.Model):
    company = models.ForeignKey('core.Company', on_delete=models.CASCADE, related_name='lunea_loyalty_missions')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    points_reward = models.PositiveIntegerField(default=50)
    action_type = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Mission fidélité'
        verbose_name_plural = 'Missions fidélité'


# ── Cartes cadeaux ────────────────────────────────────────────────────────────

class GiftCardDesign(models.Model):
    company = models.ForeignKey('core.Company', on_delete=models.CASCADE, related_name='gift_card_designs')
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120)
    image = models.ImageField(upload_to='lunea/giftcards/')
    primary_color = models.CharField(max_length=7, default='#faf6ef')
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Design carte cadeau'
        verbose_name_plural = 'Designs cartes cadeaux'

    def __str__(self):
        return self.name


class GiftCard(models.Model):
    company = models.ForeignKey('core.Company', on_delete=models.CASCADE, related_name='lunea_gift_cards')
    design = models.ForeignKey(GiftCardDesign, on_delete=models.SET_NULL, null=True, blank=True)
    code = models.CharField(max_length=20, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    balance = models.DecimalField(max_digits=10, decimal_places=2)
    sender_name = models.CharField(max_length=100, blank=True)
    sender_email = models.EmailField(blank=True)
    recipient_name = models.CharField(max_length=100, blank=True)
    recipient_email = models.EmailField(blank=True)
    message = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Carte cadeau'
        verbose_name_plural = 'Cartes cadeaux'

    def __str__(self):
        return f'Carte cadeau {self.code} — {self.balance}€'


class GiftCardRedemption(models.Model):
    gift_card = models.ForeignKey(GiftCard, on_delete=models.CASCADE, related_name='redemptions')
    amount_used = models.DecimalField(max_digits=10, decimal_places=2)
    order_id = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


# ── Newsletter ────────────────────────────────────────────────────────────────

class NewsletterSubscriber(models.Model):
    company = models.ForeignKey('core.Company', on_delete=models.CASCADE, related_name='newsletter_subscribers')
    email = models.EmailField()
    first_name = models.CharField(max_length=100, blank=True)
    skin_type = models.CharField(max_length=20, blank=True)
    skin_tone = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('company', 'email')]
        ordering = ['-created_at']
        verbose_name = 'Abonnée newsletter'
        verbose_name_plural = 'Abonnées newsletter'

    def __str__(self):
        return self.email


# ── Blog beauté ───────────────────────────────────────────────────────────────

class BeautyBlogCategory(models.Model):
    company = models.ForeignKey('core.Company', on_delete=models.CASCADE, related_name='blog_categories')
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']
        verbose_name = 'Catégorie blog'
        verbose_name_plural = 'Catégories blog'

    def __str__(self):
        return self.name


class BeautyBlogPost(models.Model):
    company = models.ForeignKey('core.Company', on_delete=models.CASCADE, related_name='blog_posts')
    category = models.ForeignKey(BeautyBlogCategory, on_delete=models.SET_NULL, null=True, blank=True)
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220)
    excerpt = models.TextField(blank=True)
    content = models.TextField()
    image = models.ImageField(upload_to='lunea/blog/', null=True, blank=True)
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    related_products = models.ManyToManyField(LuneaProduct, blank=True)
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-published_at', '-created_at']
        unique_together = [('company', 'slug')]
        verbose_name = 'Article blog beauté'
        verbose_name_plural = 'Articles blog beauté'

    def __str__(self):
        return self.title


# ── Échantillons ──────────────────────────────────────────────────────────────

class SampleProduct(models.Model):
    company = models.ForeignKey('core.Company', on_delete=models.CASCADE, related_name='sample_products')
    product = models.ForeignKey(LuneaProduct, on_delete=models.CASCADE)
    shade_name = models.CharField(max_length=100, blank=True)
    description = models.CharField(max_length=200, blank=True)
    stock = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=50)

    class Meta:
        verbose_name = 'Échantillon'
        verbose_name_plural = 'Échantillons'

    def __str__(self):
        name = f'{self.product.name}'
        if self.shade_name:
            name += f' — {self.shade_name}'
        return name


class OrderSample(models.Model):
    company = models.ForeignKey('core.Company', on_delete=models.CASCADE, related_name='order_samples')
    order_id = models.PositiveIntegerField()
    sample = models.ForeignKey(SampleProduct, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)


# ── Cadeaux par palier panier ─────────────────────────────────────────────────

class CartGiftThreshold(models.Model):
    company = models.ForeignKey('core.Company', on_delete=models.CASCADE, related_name='gift_thresholds')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=200)
    gift_product = models.ForeignKey(LuneaProduct, on_delete=models.SET_NULL, null=True, blank=True)
    is_free_shipping = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'amount']
        verbose_name = 'Palier cadeau panier'
        verbose_name_plural = 'Paliers cadeaux panier'

    def __str__(self):
        return f'Dès {self.amount}€ : {self.description}'


# ── Abonnements beauté ────────────────────────────────────────────────────────

class BeautySubscription(models.Model):
    STATUS_CHOICES = [
        ('active', 'Actif'), ('paused', 'Pausé'), ('cancelled', 'Annulé'),
    ]
    FREQUENCY_CHOICES = [
        ('monthly', 'Mensuel'), ('bimonthly', 'Tous les 2 mois'), ('quarterly', 'Trimestriel'),
    ]

    company = models.ForeignKey('core.Company', on_delete=models.CASCADE, related_name='beauty_subscriptions')
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='beauty_subscriptions')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='active')
    frequency = models.CharField(max_length=15, choices=FREQUENCY_CHOICES, default='bimonthly')
    discount_percent = models.PositiveIntegerField(default=10)
    next_renewal_at = models.DateField(null=True, blank=True)
    stripe_subscription_id = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Abonnement beauté'
        verbose_name_plural = 'Abonnements beauté'

    def __str__(self):
        return f'{self.customer.get_full_name()} — {self.get_frequency_display()}'


class BeautySubscriptionItem(models.Model):
    subscription = models.ForeignKey(BeautySubscription, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(LuneaProduct, on_delete=models.CASCADE)
    shade_name = models.CharField(max_length=100, blank=True)
    quantity = models.PositiveIntegerField(default=1)


# ── Alertes stock teinte ──────────────────────────────────────────────────────

class ShadeStockAlert(models.Model):
    company = models.ForeignKey('core.Company', on_delete=models.CASCADE, related_name='shade_stock_alerts')
    customer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    email = models.EmailField()
    product = models.ForeignKey(LuneaProduct, on_delete=models.CASCADE)
    shade = models.ForeignKey(ProductShade, on_delete=models.CASCADE, null=True, blank=True)
    shade_name = models.CharField(max_length=100, blank=True)
    is_notified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    notified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Alerte stock teinte'
        verbose_name_plural = 'Alertes stock teinte'

    def __str__(self):
        return f'{self.email} — {self.product.name} ({self.shade_name})'


# ── Commandes web ─────────────────────────────────────────────────────────────

class WebOrder(models.Model):
    STATUS_CHOICES = [
        ('pending', 'En attente'), ('paid', 'Payée'), ('processing', 'En cours'),
        ('shipped', 'Expédiée'), ('delivered', 'Livrée'), ('cancelled', 'Annulée'),
        ('refunded', 'Remboursée'),
    ]

    company = models.ForeignKey('core.Company', on_delete=models.CASCADE, related_name='lunea_web_orders')
    customer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    order_number = models.CharField(max_length=20, unique=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    customer_email = models.EmailField()
    customer_name = models.CharField(max_length=200)
    shipping_address = models.JSONField(default=dict)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    points_earned = models.PositiveIntegerField(default=0)
    points_used = models.PositiveIntegerField(default=0)
    gift_card_code = models.CharField(max_length=20, blank=True)
    gift_card_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    promo_code = models.CharField(max_length=50, blank=True)
    is_gift = models.BooleanField(default=False)
    gift_message = models.TextField(blank=True)
    samples = models.ManyToManyField(SampleProduct, blank=True)
    stripe_session_id = models.CharField(max_length=200, blank=True)
    stripe_payment_intent = models.CharField(max_length=200, blank=True)
    newsletter_consent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Commande web'
        verbose_name_plural = 'Commandes web'

    def __str__(self):
        return f'Commande {self.order_number} — {self.customer_email}'

    def save(self, *args, **kwargs):
        if not self.order_number:
            import random
            import string
            self.order_number = 'LN' + ''.join(random.choices(string.digits, k=8))
        super().save(*args, **kwargs)


class WebOrderLine(models.Model):
    order = models.ForeignKey(WebOrder, on_delete=models.CASCADE, related_name='lines')
    product = models.ForeignKey(LuneaProduct, on_delete=models.CASCADE)
    shade_name = models.CharField(max_length=100, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    is_subscription = models.BooleanField(default=False)
    discount_percent = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Ligne de commande'
        verbose_name_plural = 'Lignes de commande'
