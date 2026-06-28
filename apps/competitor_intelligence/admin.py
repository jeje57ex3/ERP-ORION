from django.contrib import admin
from .models import (
    Competitor, CompetitorSite, CompetitorProduct, CompetitorPriceHistory,
    CompetitorAdvantage, CompetitorTrafficEstimate, CompetitorComparison, CompetitorAlert,
)


@admin.register(Competitor)
class CompetitorAdmin(admin.ModelAdmin):
    list_display  = ('name', 'company', 'industry', 'country', 'is_active', 'created_at')
    list_filter   = ('is_active', 'country', 'industry')
    search_fields = ('name', 'company__name')


@admin.register(CompetitorSite)
class CompetitorSiteAdmin(admin.ModelAdmin):
    list_display = ('competitor', 'site_url', 'site_type', 'status', 'scan_frequency')
    list_filter  = ('status', 'site_type', 'robots_policy')


@admin.register(CompetitorProduct)
class CompetitorProductAdmin(admin.ModelAdmin):
    list_display  = ('name', 'competitor', 'category', 'price', 'availability', 'is_active')
    list_filter   = ('availability', 'is_active', 'currency')
    search_fields = ('name', 'competitor__name', 'category')


@admin.register(CompetitorPriceHistory)
class CompetitorPriceHistoryAdmin(admin.ModelAdmin):
    list_display = ('competitor_product', 'price', 'currency', 'availability', 'checked_at')
    list_filter  = ('currency', 'availability')
    date_hierarchy = 'checked_at'


@admin.register(CompetitorAdvantage)
class CompetitorAdvantageAdmin(admin.ModelAdmin):
    list_display = ('competitor', 'title', 'advantage_type', 'score', 'detected_manually')
    list_filter  = ('advantage_type', 'detected_manually')


@admin.register(CompetitorTrafficEstimate)
class CompetitorTrafficEstimateAdmin(admin.ModelAdmin):
    list_display = ('competitor', 'estimated_monthly_visitors', 'source_type', 'confidence_score', 'measured_at')
    list_filter  = ('source_type',)


@admin.register(CompetitorComparison)
class CompetitorComparisonAdmin(admin.ModelAdmin):
    list_display  = ('name', 'company', 'category', 'created_at')
    filter_horizontal = ('competitors',)


@admin.register(CompetitorAlert)
class CompetitorAlertAdmin(admin.ModelAdmin):
    list_display = ('title', 'competitor', 'alert_type', 'severity', 'is_read', 'created_at')
    list_filter  = ('alert_type', 'severity', 'is_read')
    date_hierarchy = 'created_at'
