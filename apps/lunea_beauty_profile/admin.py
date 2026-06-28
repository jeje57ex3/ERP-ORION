from django.contrib import admin
from .models import BeautyProfile, BeautyRecommendation


class RecommendationInline(admin.TabularInline):
    model = BeautyRecommendation
    extra = 0
    readonly_fields = ['product_name', 'recommendation_type', 'score', 'is_applied', 'created_at']
    can_delete = False
    max_num = 10


@admin.register(BeautyProfile)
class BeautyProfileAdmin(admin.ModelAdmin):
    list_display = ['customer', 'skin_type', 'hair_type', 'brand_key', 'company', 'updated_at']
    list_filter = ['skin_type', 'hair_type', 'company']
    search_fields = ['customer__name']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [RecommendationInline]


@admin.register(BeautyRecommendation)
class BeautyRecommendationAdmin(admin.ModelAdmin):
    list_display = ['product_name', 'recommendation_type', 'score', 'is_applied', 'company', 'created_at']
    list_filter = ['recommendation_type', 'is_applied', 'company']
    search_fields = ['product_name', 'brand']
    readonly_fields = ['created_at', 'applied_at']
