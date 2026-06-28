from django.contrib import admin
from .models import (
    ProductCategory, LuneaProduct, ProductShade, ProductImage, ProductShadeMedia,
    ProductStock, ProductReview, BeautyRoutine, BeautyRoutineItem, MakeupLook,
    MakeupLookProduct, CustomerBeautyProfile, CustomerShadeProfile, BeautyQuizResult,
    ShadeFinderResult, CustomerSkinDiagnostic, CustomerWishlistItem,
    LoyaltyTier, LoyaltyAccount, LoyaltyTransaction, LoyaltyMission,
    GiftCardDesign, GiftCard, GiftCardRedemption, NewsletterSubscriber,
    BeautyBlogCategory, BeautyBlogPost, SampleProduct, OrderSample,
    CartGiftThreshold, BeautySubscription, BeautySubscriptionItem,
    ShadeStockAlert, WebOrder, WebOrderLine,
)


class ProductShadeInline(admin.TabularInline):
    model = ProductShade
    extra = 0
    fields = ('name', 'hex_color', 'undertone', 'stock', 'is_active', 'order')


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0
    fields = ('image', 'shade', 'alt_text', 'is_primary', 'order')


class BeautyRoutineItemInline(admin.TabularInline):
    model = BeautyRoutineItem
    extra = 0
    fields = ('step', 'product', 'quantity', 'note')


class MakeupLookProductInline(admin.TabularInline):
    model = MakeupLookProduct
    extra = 0
    fields = ('zone', 'product', 'shade_name', 'zone_x', 'zone_y')


class WebOrderLineInline(admin.TabularInline):
    model = WebOrderLine
    extra = 0
    readonly_fields = ('product', 'shade_name', 'quantity', 'unit_price', 'total_price')


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'parent', 'order', 'is_active')
    list_filter = ('company', 'is_active')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}


@admin.register(LuneaProduct)
class LuneaProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'is_best_seller', 'is_new', 'is_active', 'company')
    list_filter = ('company', 'category', 'is_best_seller', 'is_new', 'is_active', 'finish', 'coverage')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductShadeInline, ProductImageInline]
    fieldsets = (
        ('Informations', {'fields': ('company', 'category', 'name', 'slug', 'short_description', 'description')}),
        ('Beauté', {'fields': ('skin_types', 'finish', 'coverage', 'hold_hours', 'ingredients', 'how_to_use', 'benefits')}),
        ('Prix & Points', {'fields': ('price', 'compare_price', 'loyalty_points')}),
        ('Badges', {'fields': ('is_best_seller', 'is_new', 'is_vegan', 'is_limited_edition', 'has_shades', 'is_active')}),
        ('SEO', {'fields': ('meta_title', 'meta_description'), 'classes': ('collapse',)}),
    )


@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = ('product', 'customer', 'rating', 'is_verified_purchase', 'is_approved', 'created_at')
    list_filter = ('company', 'is_approved', 'rating', 'is_verified_purchase')
    search_fields = ('product__name', 'comment')
    actions = ['approve_reviews']

    def approve_reviews(self, request, queryset):
        queryset.update(is_approved=True)
    approve_reviews.short_description = 'Approuver les avis sélectionnés'


@admin.register(BeautyRoutine)
class BeautyRoutineAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'duration_minutes', 'is_quick', 'is_active')
    list_filter = ('company', 'is_quick', 'is_active')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [BeautyRoutineItemInline]


@admin.register(MakeupLook)
class MakeupLookAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'is_active', 'created_at')
    list_filter = ('company', 'is_active')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [MakeupLookProductInline]


@admin.register(BeautyQuizResult)
class BeautyQuizResultAdmin(admin.ModelAdmin):
    list_display = ('company', 'customer', 'skin_type', 'skin_tone', 'undertone', 'created_at')
    list_filter = ('company', 'skin_type', 'skin_tone')
    readonly_fields = ('answers', 'created_at')


@admin.register(ShadeFinderResult)
class ShadeFinderResultAdmin(admin.ModelAdmin):
    list_display = ('company', 'customer', 'skin_tone', 'undertone', 'finish', 'created_at')
    list_filter = ('company', 'skin_tone', 'undertone')


@admin.register(CustomerBeautyProfile)
class CustomerBeautyProfileAdmin(admin.ModelAdmin):
    list_display = ('customer', 'company', 'skin_type', 'skin_tone', 'undertone', 'updated_at')
    list_filter = ('company', 'skin_type', 'skin_tone')


@admin.register(CustomerWishlistItem)
class CustomerWishlistItemAdmin(admin.ModelAdmin):
    list_display = ('customer', 'product', 'shade_name', 'created_at')
    list_filter = ('company',)


@admin.register(LoyaltyTier)
class LoyaltyTierAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'min_points', 'order')
    list_filter = ('company',)


@admin.register(LoyaltyAccount)
class LoyaltyAccountAdmin(admin.ModelAdmin):
    list_display = ('customer', 'company', 'tier', 'points_balance', 'points_lifetime', 'updated_at')
    list_filter = ('company', 'tier')
    search_fields = ('customer__email', 'customer__first_name')


@admin.register(LoyaltyTransaction)
class LoyaltyTransactionAdmin(admin.ModelAdmin):
    list_display = ('account', 'type', 'points', 'description', 'created_at')
    list_filter = ('type',)
    readonly_fields = ('created_at',)


@admin.register(GiftCard)
class GiftCardAdmin(admin.ModelAdmin):
    list_display = ('code', 'company', 'amount', 'balance', 'recipient_email', 'is_active', 'created_at')
    list_filter = ('company', 'is_active')
    search_fields = ('code', 'recipient_email', 'sender_email')
    readonly_fields = ('created_at',)


@admin.register(GiftCardDesign)
class GiftCardDesignAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'is_active')
    list_filter = ('company', 'is_active')


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ('email', 'first_name', 'company', 'is_active', 'created_at')
    list_filter = ('company', 'is_active')
    search_fields = ('email', 'first_name')


@admin.register(BeautyBlogPost)
class BeautyBlogPostAdmin(admin.ModelAdmin):
    list_display = ('title', 'company', 'category', 'is_published', 'published_at')
    list_filter = ('company', 'is_published', 'category')
    prepopulated_fields = {'slug': ('title',)}
    search_fields = ('title',)


@admin.register(BeautyBlogCategory)
class BeautyBlogCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'order')
    list_filter = ('company',)
    prepopulated_fields = {'slug': ('name',)}


@admin.register(SampleProduct)
class SampleProductAdmin(admin.ModelAdmin):
    list_display = ('product', 'shade_name', 'company', 'stock', 'is_active')
    list_filter = ('company', 'is_active')


@admin.register(CartGiftThreshold)
class CartGiftThresholdAdmin(admin.ModelAdmin):
    list_display = ('amount', 'description', 'company', 'is_free_shipping', 'is_active', 'order')
    list_filter = ('company', 'is_active')


@admin.register(BeautySubscription)
class BeautySubscriptionAdmin(admin.ModelAdmin):
    list_display = ('customer', 'company', 'status', 'frequency', 'next_renewal_at', 'created_at')
    list_filter = ('company', 'status', 'frequency')
    search_fields = ('customer__email',)


@admin.register(ShadeStockAlert)
class ShadeStockAlertAdmin(admin.ModelAdmin):
    list_display = ('email', 'product', 'shade_name', 'company', 'is_notified', 'created_at')
    list_filter = ('company', 'is_notified')
    search_fields = ('email', 'product__name')


@admin.register(WebOrder)
class WebOrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'customer_email', 'status', 'total', 'company', 'created_at')
    list_filter = ('company', 'status', 'is_gift')
    search_fields = ('order_number', 'customer_email', 'customer_name')
    readonly_fields = ('order_number', 'stripe_session_id', 'stripe_payment_intent', 'created_at', 'updated_at')
    inlines = [WebOrderLineInline]


@admin.register(CustomerSkinDiagnostic)
class CustomerSkinDiagnosticAdmin(admin.ModelAdmin):
    list_display = ('customer', 'company', 'skin_type', 'skin_tone', 'season', 'created_at')
    list_filter = ('company', 'skin_type', 'skin_tone')


admin.site.register(ProductShadeMedia)
admin.site.register(ProductStock)
admin.site.register(CustomerShadeProfile)
admin.site.register(LoyaltyMission)
admin.site.register(OrderSample)
admin.site.register(BeautySubscriptionItem)
admin.site.register(GiftCardRedemption)
