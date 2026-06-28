from django.contrib import admin
from .models import WebhookEndpoint, WebhookDelivery


class DeliveryInline(admin.TabularInline):
    model = WebhookDelivery
    extra = 0
    readonly_fields = ['event_type', 'status', 'response_code', 'attempts', 'last_attempt_at', 'created_at']
    can_delete = False
    max_num = 10


@admin.register(WebhookEndpoint)
class WebhookEndpointAdmin(admin.ModelAdmin):
    list_display = ['name', 'url', 'is_active', 'company', 'created_at']
    list_filter = ['is_active', 'company']
    search_fields = ['name', 'url']
    readonly_fields = ['created_at', 'updated_at', 'secret_hash']
    inlines = [DeliveryInline]


@admin.register(WebhookDelivery)
class WebhookDeliveryAdmin(admin.ModelAdmin):
    list_display = ['event_type', 'endpoint', 'status', 'response_code', 'attempts', 'created_at', 'company']
    list_filter = ['status', 'event_type', 'company']
    readonly_fields = ['created_at', 'last_attempt_at']
