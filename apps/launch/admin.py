from django.contrib import admin
from .models import WaitlistSubscriber, ContactMessage


@admin.register(WaitlistSubscriber)
class WaitlistSubscriberAdmin(admin.ModelAdmin):
    list_display = ['email', 'brand_key', 'feature_key', 'created_at']
    list_filter = ['brand_key', 'feature_key']
    search_fields = ['email']
    readonly_fields = ['created_at', 'ip_address', 'user_agent']


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'brand_key', 'subject', 'status', 'created_at']
    list_filter = ['brand_key', 'status']
    search_fields = ['name', 'email', 'subject']
    readonly_fields = ['created_at', 'ip_address']
