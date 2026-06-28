from django.contrib import admin
from .models import CustomerScore, CustomerTimelineEvent


@admin.register(CustomerScore)
class CustomerScoreAdmin(admin.ModelAdmin):
    list_display = ['customer', 'score_type', 'score', 'label', 'brand_key', 'company', 'updated_at']
    list_filter = ['score_type', 'company', 'brand_key']
    search_fields = ['customer__name', 'label']
    readonly_fields = ['updated_at', 'created_at']


@admin.register(CustomerTimelineEvent)
class CustomerTimelineEventAdmin(admin.ModelAdmin):
    list_display = ['customer', 'event_type', 'title', 'brand_key', 'company', 'created_at']
    list_filter = ['event_type', 'company', 'brand_key']
    search_fields = ['customer__name', 'title', 'description']
    readonly_fields = ['created_at']
