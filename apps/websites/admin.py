"""
apps/websites/admin.py — Administration Django pour le module Sites Web
"""
from django.contrib import admin
from .models import (
    WebsiteTheme, Website, WebsitePage, WebsiteSection,
    WebsiteMenu, WebsiteMenuItem, BlogCategory, BlogPost,
    ContactMessage, QuoteRequest,
    WebsiteService, WebsiteTestimonial, WebsiteProject, WebsiteFAQ,
    StoreCategory, StoreProduct, StoreProductImage, StoreCart, StoreOrder, StoreOrderItem,
    WebsiteDomain, WebsiteMedia, WebsiteForm, WebsiteFormField,
    WebsiteFormSubmission, WebsiteAnalyticsEvent,
    BTPPortfolioProject, BTPWebsiteReview, BTPClientAccessRequest, BTPEmergencyRequest,
    WebsitePageTranslation, WebsiteSectionTranslation, BlogPostTranslation,
    ProductTranslation, WebsiteMenuItemTranslation,
    LoyaltyAccount, LoyaltyTransaction,
    AffiliateProgram, AffiliateCode, AffiliateReferral,
    GiftCard, GiftCardRedemption, SiecleCustomerToken,
)


@admin.register(WebsiteTheme)
class WebsiteThemeAdmin(admin.ModelAdmin):
    list_display = ['name', 'company', 'mode', 'primary_color', 'font_primary', 'is_default']
    list_filter = ['mode', 'is_default', 'company']
    search_fields = ['name']


class WebsiteDomainInline(admin.TabularInline):
    model = WebsiteDomain
    extra = 0
    fields = ['domain', 'domain_type', 'status', 'is_primary', 'dns_verified']
    readonly_fields = ['dns_verified', 'dns_verified_at', 'last_checked_at']


class WebsitePageInline(admin.TabularInline):
    model = WebsitePage
    extra = 0
    fields = ['title', 'page_type', 'status', 'is_homepage', 'show_in_menu', 'order']


@admin.register(Website)
class WebsiteAdmin(admin.ModelAdmin):
    list_display = ['name', 'company', 'site_type', 'status', 'is_published', 'is_active', 'created_at']
    list_filter = ['site_type', 'status', 'is_published', 'is_active', 'company']
    search_fields = ['name', 'domain', 'company__name']
    readonly_fields = ['created_at', 'updated_at', 'published_at', 'unpublished_at']
    inlines = [WebsiteDomainInline, WebsitePageInline]
    fieldsets = [
        ('Général', {'fields': ['company', 'name', 'slug', 'site_type', 'status', 'is_published', 'maintenance_mode']}),
        ('Contenu', {'fields': ['logo', 'favicon', 'theme', 'home_page', 'language', 'currency']}),
        ('Contact', {'fields': ['contact_email', 'contact_phone', 'address']}),
        ('SEO', {'fields': ['meta_title', 'meta_description', 'google_analytics_id', 'meta_pixel_id']}),
        ('Réseaux sociaux', {'fields': ['facebook_url', 'instagram_url', 'twitter_url', 'linkedin_url', 'youtube_url', 'tiktok_url']}),
        ('Légal', {'fields': ['legal_company_name', 'legal_siret', 'legal_vat', 'legal_director', 'hosting_provider']}),
        ('Dates', {'fields': ['created_at', 'updated_at', 'published_at', 'unpublished_at'], 'classes': ['collapse']}),
    ]


@admin.register(WebsiteDomain)
class WebsiteDomainAdmin(admin.ModelAdmin):
    list_display = ['domain', 'website', 'domain_type', 'status', 'is_primary', 'dns_verified', 'ssl_enabled']
    list_filter = ['domain_type', 'status', 'dns_verified', 'ssl_enabled']
    search_fields = ['domain', 'website__name']
    readonly_fields = ['dns_verified_at', 'last_checked_at', 'verification_token']


@admin.register(WebsitePage)
class WebsitePageAdmin(admin.ModelAdmin):
    list_display = ['title', 'website', 'page_type', 'status', 'is_homepage', 'show_in_menu', 'order']
    list_filter = ['page_type', 'status', 'website', 'is_homepage']
    search_fields = ['title', 'website__name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(WebsiteSection)
class WebsiteSectionAdmin(admin.ModelAdmin):
    list_display = ['section_type', 'page', 'title', 'order', 'is_visible']
    list_filter = ['section_type', 'is_visible']
    search_fields = ['title', 'page__title']


@admin.register(WebsiteMenu)
class WebsiteMenuAdmin(admin.ModelAdmin):
    list_display = ['name', 'website', 'position', 'is_active']
    list_filter = ['position', 'is_active']


@admin.register(BlogCategory)
class BlogCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'website', 'slug']
    search_fields = ['name', 'website__name']


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ['title', 'website', 'author', 'status', 'published_at']
    list_filter = ['status', 'website', 'category']
    search_fields = ['title', 'website__name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'website', 'status', 'created_at']
    list_filter = ['status', 'website']
    search_fields = ['name', 'email', 'subject']
    readonly_fields = ['created_at']


@admin.register(QuoteRequest)
class QuoteRequestAdmin(admin.ModelAdmin):
    list_display = ['name', 'company_name', 'website', 'status', 'created_at']
    list_filter = ['status', 'website']
    search_fields = ['name', 'email', 'company_name']


@admin.register(StoreProduct)
class StoreProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'website', 'category', 'price', 'stock_quantity', 'status']
    list_filter = ['status', 'website', 'category']
    search_fields = ['name', 'sku']


@admin.register(StoreOrder)
class StoreOrderAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'customer_name', 'website', 'status', 'payment_status', 'grand_total', 'created_at']
    list_filter = ['status', 'payment_status', 'website']
    search_fields = ['order_number', 'customer_name', 'customer_email']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(WebsiteMedia)
class WebsiteMediaAdmin(admin.ModelAdmin):
    list_display = ['title', 'company', 'website', 'media_type', 'file_size_display', 'uploaded_by', 'created_at']
    list_filter = ['media_type', 'company', 'website']
    search_fields = ['title', 'alt_text']


class WebsiteFormFieldInline(admin.TabularInline):
    model = WebsiteFormField
    extra = 1
    fields = ['label', 'field_type', 'is_required', 'order']


@admin.register(WebsiteForm)
class WebsiteFormAdmin(admin.ModelAdmin):
    list_display = ['name', 'website', 'form_type', 'is_active', 'create_crm_prospect']
    list_filter = ['form_type', 'is_active', 'website']
    inlines = [WebsiteFormFieldInline]


@admin.register(WebsiteFormSubmission)
class WebsiteFormSubmissionAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'website', 'form', 'status', 'created_at']
    list_filter = ['status', 'website', 'form']
    search_fields = ['name', 'email']
    readonly_fields = ['created_at', 'data', 'ip_address', 'user_agent']


@admin.register(WebsiteAnalyticsEvent)
class WebsiteAnalyticsEventAdmin(admin.ModelAdmin):
    list_display = ['event_type', 'website', 'path', 'created_at']
    list_filter = ['event_type', 'website']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'


# ─── BTP ──────────────────────────────────────────────────────────────────────

@admin.register(BTPPortfolioProject)
class BTPPortfolioProjectAdmin(admin.ModelAdmin):
    list_display  = ['title', 'website', 'work_type', 'city', 'is_featured', 'is_published', 'order']
    list_filter   = ['work_type', 'is_featured', 'is_published', 'website']
    search_fields = ['title', 'city', 'description']
    list_editable = ['is_featured', 'is_published', 'order']
    prepopulated_fields = {'slug': ('title',)}
    fieldsets = (
        (None, {'fields': ('website', 'title', 'slug', 'work_type', 'city', 'description')}),
        ('Images', {'fields': ('before_image', 'after_image')}),
        ('Avis client', {'fields': ('customer_name', 'customer_review', 'completion_date')}),
        ('Publication', {'fields': ('is_featured', 'is_published', 'order')}),
    )


@admin.register(BTPWebsiteReview)
class BTPWebsiteReviewAdmin(admin.ModelAdmin):
    list_display  = ['customer_name', 'website', 'rating', 'work_type', 'customer_city', 'is_published', 'order']
    list_filter   = ['rating', 'is_published', 'work_type', 'website']
    search_fields = ['customer_name', 'comment', 'customer_city']
    list_editable = ['is_published', 'order']


@admin.register(BTPClientAccessRequest)
class BTPClientAccessRequestAdmin(admin.ModelAdmin):
    list_display  = ['first_name', 'last_name', 'email', 'website', 'status', 'reference', 'created_at']
    list_filter   = ['status', 'website']
    search_fields = ['first_name', 'last_name', 'email', 'reference']
    list_editable = ['status']
    readonly_fields = ['ip_address', 'created_at']
    date_hierarchy = 'created_at'


@admin.register(BTPEmergencyRequest)
class BTPEmergencyRequestAdmin(admin.ModelAdmin):
    list_display  = ['first_name', 'last_name', 'phone', 'emergency_type', 'website', 'status', 'wants_callback', 'created_at']
    list_filter   = ['emergency_type', 'status', 'wants_callback', 'website']
    search_fields = ['first_name', 'last_name', 'phone', 'address', 'description']
    list_editable = ['status']
    readonly_fields = ['ip_address', 'created_at', 'guided_quote']
    date_hierarchy = 'created_at'


# ─── Traductions sites web ────────────────────────────────────────────────────

@admin.register(WebsitePageTranslation)
class WebsitePageTranslationAdmin(admin.ModelAdmin):
    list_display  = ['page', 'language', 'title', 'updated_at']
    list_filter   = ['language', 'page__website']
    search_fields = ['title', 'page__title']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(WebsiteSectionTranslation)
class WebsiteSectionTranslationAdmin(admin.ModelAdmin):
    list_display  = ['section', 'language', 'title', 'updated_at']
    list_filter   = ['language']
    search_fields = ['title', 'subtitle']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(BlogPostTranslation)
class BlogPostTranslationAdmin(admin.ModelAdmin):
    list_display  = ['post', 'language', 'title', 'updated_at']
    list_filter   = ['language', 'post__website']
    search_fields = ['title', 'post__title']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(ProductTranslation)
class ProductTranslationAdmin(admin.ModelAdmin):
    list_display  = ['product', 'language', 'name', 'updated_at']
    list_filter   = ['language', 'product__website']
    search_fields = ['name', 'product__name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(WebsiteMenuItemTranslation)
class WebsiteMenuItemTranslationAdmin(admin.ModelAdmin):
    list_display  = ['menu_item', 'language', 'label', 'updated_at']
    list_filter   = ['language']
    search_fields = ['label', 'menu_item__label']
    readonly_fields = ['created_at', 'updated_at']


# ── Fidélité ──────────────────────────────────────────────────────────────────

class LoyaltyTransactionInline(admin.TabularInline):
    model       = LoyaltyTransaction
    extra       = 0
    readonly_fields = ['points', 'transaction_type', 'reason', 'order', 'created_at']
    can_delete  = False


@admin.register(LoyaltyAccount)
class LoyaltyAccountAdmin(admin.ModelAdmin):
    list_display    = ['customer_email', 'company', 'tier', 'points_balance', 'lifetime_points', 'updated_at']
    list_filter     = ['tier', 'company']
    search_fields   = ['customer_email']
    readonly_fields = ['created_at', 'updated_at', 'lifetime_points']
    inlines         = [LoyaltyTransactionInline]
    actions         = ['add_bonus_points']

    def add_bonus_points(self, request, queryset):
        for acc in queryset:
            acc.add_points(50, reason='Bonus admin')
        self.message_user(request, f'{queryset.count()} compte(s) crédité(s) de 50 points.')
    add_bonus_points.short_description = 'Ajouter 50 points bonus'


@admin.register(LoyaltyTransaction)
class LoyaltyTransactionAdmin(admin.ModelAdmin):
    list_display  = ['loyalty_account', 'points', 'transaction_type', 'reason', 'created_at']
    list_filter   = ['transaction_type', 'company']
    search_fields = ['loyalty_account__customer_email', 'reason']
    readonly_fields = ['created_at']


# ── Affiliation ───────────────────────────────────────────────────────────────

@admin.register(AffiliateProgram)
class AffiliateProgramAdmin(admin.ModelAdmin):
    list_display = ['name', 'company', 'is_active', 'reward_type', 'referrer_reward_value', 'referred_reward_value']
    list_filter  = ['is_active', 'reward_type']


@admin.register(AffiliateCode)
class AffiliateCodeAdmin(admin.ModelAdmin):
    list_display  = ['code', 'customer_email', 'company', 'clicks', 'signups', 'orders', 'total_commission', 'is_active']
    list_filter   = ['is_active', 'company']
    search_fields = ['code', 'customer_email']
    readonly_fields = ['created_at', 'clicks', 'signups', 'orders', 'total_commission']


@admin.register(AffiliateReferral)
class AffiliateReferralAdmin(admin.ModelAdmin):
    list_display  = ['referrer_email', 'referred_email', 'status', 'points_reward', 'commission_amount', 'created_at']
    list_filter   = ['status', 'company']
    search_fields = ['referrer_email', 'referred_email']
    readonly_fields = ['created_at']
    actions       = ['validate_referrals']

    def validate_referrals(self, request, queryset):
        updated = queryset.filter(status='pending').update(status='validated')
        self.message_user(request, f'{updated} parrainage(s) validé(s).')
    validate_referrals.short_description = 'Valider les parrainages sélectionnés'


# ── Cartes cadeaux ────────────────────────────────────────────────────────────

class GiftCardRedemptionInline(admin.TabularInline):
    model       = GiftCardRedemption
    extra       = 0
    readonly_fields = ['customer_email', 'order', 'amount_used', 'created_at']
    can_delete  = False


@admin.register(GiftCard)
class GiftCardAdmin(admin.ModelAdmin):
    list_display    = ['code', 'company', 'initial_amount', 'remaining_amount', 'status', 'assigned_to_email', 'expires_at', 'created_at']
    list_filter     = ['status', 'company', 'currency']
    search_fields   = ['code', 'assigned_to_email', 'purchased_by_email']
    readonly_fields = ['created_at', 'remaining_amount']
    inlines         = [GiftCardRedemptionInline]
    actions         = ['deactivate_cards']

    def deactivate_cards(self, request, queryset):
        updated = queryset.update(status='cancelled')
        self.message_user(request, f'{updated} carte(s) annulée(s).')
    deactivate_cards.short_description = 'Annuler les cartes sélectionnées'


@admin.register(GiftCardRedemption)
class GiftCardRedemptionAdmin(admin.ModelAdmin):
    list_display  = ['gift_card', 'customer_email', 'amount_used', 'order', 'created_at']
    list_filter   = ['company']
    search_fields = ['gift_card__code', 'customer_email']
    readonly_fields = ['created_at']


@admin.register(SiecleCustomerToken)
class SiecleCustomerTokenAdmin(admin.ModelAdmin):
    list_display  = ['user', 'created_at']
    search_fields = ['user__email']
    readonly_fields = ['key', 'created_at']
