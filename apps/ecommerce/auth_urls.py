from django.urls import path
from .auth_views import (
    CustomerLoginView,
    CustomerPasswordResetRequestView,
    CustomerPasswordResetConfirmView,
    CustomerBrandProfileView,
)

app_name = 'ecommerce_auth'

urlpatterns = [
    path('login/', CustomerLoginView.as_view(), name='login'),
    path('logout/', CustomerLoginView.as_view(), name='logout'),
    path('password-reset/request/', CustomerPasswordResetRequestView.as_view(), name='password_reset_request'),
    path('password-reset/confirm/', CustomerPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('brand-profile/', CustomerBrandProfileView.as_view(), name='brand_profile'),
]
