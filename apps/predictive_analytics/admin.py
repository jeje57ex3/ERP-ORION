from django.contrib import admin
from .models import AnalyticsForecast, AnalyticsInsight


@admin.register(AnalyticsForecast)
class AnalyticsForecastAdmin(admin.ModelAdmin):
    list_display = ['forecast_type', 'period', 'value', 'confidence', 'brand_key', 'company', 'computed_at']
    list_filter = ['forecast_type', 'company', 'brand_key']
    readonly_fields = ['computed_at']


@admin.register(AnalyticsInsight)
class AnalyticsInsightAdmin(admin.ModelAdmin):
    list_display = ['title', 'insight_type', 'score', 'is_read', 'is_dismissed', 'brand_key', 'company', 'created_at']
    list_filter = ['insight_type', 'is_dismissed', 'company', 'brand_key']
    search_fields = ['title', 'message']
    readonly_fields = ['created_at']
