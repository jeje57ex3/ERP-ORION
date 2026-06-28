from django.urls import path
from . import views
from apps.ecommerce.api.siecle_api import (
    ProductListView, ProductDetailView, CollectionListView,
    CartValidateView, CreateCheckoutSessionView, StripeWebhookView,
    NewsletterSubscribeView,
    WatchCustomizationOptionsView, WatchValidateCustomizationView, WatchAddCustomToCartView,
)
from apps.ecommerce.api.customer_api import (
    RegisterView, LoginView, LogoutView, MeView,
    CustomerAccountView, CustomerOrdersView,
    CustomerRewardsView, UseRewardView,
    CustomerAffiliateView, CreateAffiliateCodeView,
    GiftCardCheckView, ApplyGiftCardView, ApplyRewardPointsView,
)
from apps.ecommerce.api.siecle_extended_api import (
    SearchView, CategoriesView,
    DropsView, DropRegisterView,
    PacksView, AddPackToCartView,
    LooksView, AddLookToCartView,
    GiftCardDesignsView, CreateGiftCardView,
    IdentityQuizView,
    BeautyQuizView, ShadeFinderView,
    CommunityPostsView,
    WatchConfigurationsView, WatchCertificateView,
)

app_name = 'api'

urlpatterns = [
    # ── SIECLE Store API ─────────────────────────────────────────────────────
    path('siecle/products/',                   ProductListView.as_view(),          name='siecle_products'),
    path('siecle/products/<slug:slug>/',       ProductDetailView.as_view(),        name='siecle_product_detail'),
    path('siecle/collections/',               CollectionListView.as_view(),       name='siecle_collections'),
    path('siecle/cart/validate/',             CartValidateView.as_view(),         name='siecle_cart_validate'),
    path('siecle/cart/apply-gift-card/',      ApplyGiftCardView.as_view(),        name='siecle_apply_gift_card'),
    path('siecle/cart/apply-reward/',         ApplyRewardPointsView.as_view(),    name='siecle_apply_reward'),
    path('siecle/create-checkout-session/',   CreateCheckoutSessionView.as_view(),name='siecle_checkout'),
    path('siecle/stripe/webhook/',            StripeWebhookView.as_view(),        name='siecle_stripe_webhook'),

    # ── SIECLE Auth ──────────────────────────────────────────────────────────
    path('siecle/auth/register/',             RegisterView.as_view(),             name='siecle_register'),
    path('siecle/auth/login/',                LoginView.as_view(),                name='siecle_login'),
    path('siecle/auth/logout/',               LogoutView.as_view(),               name='siecle_logout'),
    path('siecle/auth/me/',                   MeView.as_view(),                   name='siecle_me'),

    # ── SIECLE Customer ───────────────────────────────────────────────────────
    path('siecle/customer/account/',           CustomerAccountView.as_view(),      name='siecle_customer_account'),
    path('siecle/customer/orders/',            CustomerOrdersView.as_view(),       name='siecle_customer_orders'),
    path('siecle/customer/rewards/',           CustomerRewardsView.as_view(),      name='siecle_customer_rewards'),
    path('siecle/customer/rewards/use/',       UseRewardView.as_view(),            name='siecle_use_reward'),
    path('siecle/customer/affiliate/',         CustomerAffiliateView.as_view(),    name='siecle_customer_affiliate'),
    path('siecle/customer/affiliate/create-code/', CreateAffiliateCodeView.as_view(), name='siecle_create_affiliate_code'),

    # ── SIECLE Gift Cards ─────────────────────────────────────────────────────
    path('siecle/gift-card/<str:code>/',       GiftCardCheckView.as_view(),        name='siecle_gift_card_check'),

    # ── SIECLE Newsletter ─────────────────────────────────────────────────────
    path('siecle/newsletter/',                  NewsletterSubscribeView.as_view(),  name='siecle_newsletter'),

    # ── SIECLE Watch Configurator ─────────────────────────────────────────────
    path('siecle/products/<slug:slug>/customization-options/',
         WatchCustomizationOptionsView.as_view(),    name='siecle_watch_customization_options'),
    path('siecle/products/<slug:slug>/validate-customization/',
         WatchValidateCustomizationView.as_view(),   name='siecle_watch_validate_customization'),
    path('siecle/cart/add-custom-watch/',
         WatchAddCustomToCartView.as_view(),         name='siecle_add_custom_watch'),

    # ── SIECLE Extended ───────────────────────────────────────────────────────
    path('siecle/search/',                           SearchView.as_view(),              name='siecle_search'),
    path('siecle/categories/',                       CategoriesView.as_view(),          name='siecle_categories'),
    path('siecle/drops/',                            DropsView.as_view(),               name='siecle_drops'),
    path('siecle/drops/<int:pk>/register/',          DropRegisterView.as_view(),        name='siecle_drop_register'),
    path('siecle/packs/',                            PacksView.as_view(),               name='siecle_packs'),
    path('siecle/cart/add-pack/',                    AddPackToCartView.as_view(),       name='siecle_add_pack'),
    path('siecle/looks/',                            LooksView.as_view(),               name='siecle_looks'),
    path('siecle/cart/add-look/',                    AddLookToCartView.as_view(),       name='siecle_add_look'),
    path('siecle/giftcards/designs/',                GiftCardDesignsView.as_view(),     name='siecle_giftcard_designs'),
    path('siecle/giftcards/create/',                 CreateGiftCardView.as_view(),      name='siecle_giftcard_create'),
    path('siecle/identity-quiz/',                    IdentityQuizView.as_view(),        name='siecle_identity_quiz'),
    path('siecle/beauty/quiz/',                      BeautyQuizView.as_view(),          name='siecle_beauty_quiz'),
    path('siecle/beauty/shade-finder/',              ShadeFinderView.as_view(),         name='siecle_shade_finder'),
    path('siecle/community/posts/',                  CommunityPostsView.as_view(),      name='siecle_community_posts'),
    path('siecle/customer/watch-configurations/',    WatchConfigurationsView.as_view(), name='siecle_watch_configs'),
    path('siecle/watches/certificate/<str:watch_id>/', WatchCertificateView.as_view(), name='siecle_watch_certificate'),
]
