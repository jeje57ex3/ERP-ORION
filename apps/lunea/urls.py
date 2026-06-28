from django.urls import path
from . import views

app_name = 'lunea'

urlpatterns = [
    # Produits
    path('products/', views.ProductListView.as_view(), name='product_list'),
    path('products/<slug:slug>/', views.ProductDetailView.as_view(), name='product_detail'),
    path('categories/', views.CategoryListView.as_view(), name='category_list'),
    path('best-sellers/', views.BestSellersView.as_view(), name='best_sellers'),
    path('new-products/', views.NewProductsView.as_view(), name='new_products'),

    # Recherche
    path('search/', views.SearchView.as_view(), name='search'),

    # Outils beauté
    path('product-diagnostic/', views.ProductDiagnosticView.as_view(), name='product_diagnostic'),
    path('shade-finder/', views.ShadeFinderView.as_view(), name='shade_finder'),
    path('beauty-quiz/', views.BeautyQuizView.as_view(), name='beauty_quiz'),
    path('shades/compare/', views.ShadeCompareView.as_view(), name='shade_compare'),

    # Routines & Looks
    path('routines/', views.RoutineListView.as_view(), name='routine_list'),
    path('routines/<slug:slug>/', views.RoutineDetailView.as_view(), name='routine_detail'),
    path('looks/', views.LookListView.as_view(), name='look_list'),

    # Panier
    path('cart/', views.CartView.as_view(), name='cart'),
    path('cart/add/', views.CartView.as_view(), name='cart_add'),
    path('cart/add-routine/', views.CartAddRoutineView.as_view(), name='cart_add_routine'),
    path('cart/add-look/', views.CartAddLookView.as_view(), name='cart_add_look'),

    # Checkout
    path('checkout/session/', views.CheckoutSessionView.as_view(), name='checkout_session'),

    # Newsletter
    path('newsletter/', views.NewsletterView.as_view(), name='newsletter'),

    # Avis
    path('reviews/', views.ReviewListView.as_view(), name='review_list'),

    # Alertes stock
    path('stock-alerts/', views.StockAlertView.as_view(), name='stock_alert'),

    # Échantillons & Cadeaux
    path('samples/', views.SampleListView.as_view(), name='sample_list'),
    path('gift-thresholds/', views.GiftThresholdView.as_view(), name='gift_thresholds'),

    # Compte client
    path('customer/account/', views.CustomerAccountView.as_view(), name='customer_account'),
    path('customer/orders/', views.CustomerOrdersView.as_view(), name='customer_orders'),
    path('customer/rewards/', views.CustomerRewardsView.as_view(), name='customer_rewards'),
    path('customer/wishlist/', views.CustomerWishlistView.as_view(), name='customer_wishlist'),
    path('customer/wishlist/add/', views.CustomerWishlistView.as_view(), name='customer_wishlist_add'),
    path('customer/my-shades/', views.CustomerMyShadesView.as_view(), name='customer_my_shades'),
    path('customer/subscriptions/', views.CustomerSubscriptionsView.as_view(), name='customer_subscriptions'),
]
