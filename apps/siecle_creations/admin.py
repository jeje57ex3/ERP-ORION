from django.contrib import admin
from .models import Creation, CreationOrder


class OrderInline(admin.TabularInline):
    model = CreationOrder
    extra = 0
    readonly_fields = ['customer', 'quantity', 'total_price', 'status', 'created_at']
    can_delete = False


@admin.register(Creation)
class CreationAdmin(admin.ModelAdmin):
    list_display = ['reference', 'title', 'category', 'status', 'price_ttc',
                    'stock_qty', 'is_limited_edition', 'company', 'published_at']
    list_filter = ['category', 'status', 'is_limited_edition', 'company']
    search_fields = ['reference', 'title', 'description']
    readonly_fields = ['created_at', 'updated_at', 'published_at']
    inlines = [OrderInline]


@admin.register(CreationOrder)
class CreationOrderAdmin(admin.ModelAdmin):
    list_display = ['pk', 'creation', 'customer', 'quantity', 'total_price', 'status', 'company', 'created_at']
    list_filter = ['status', 'company']
    search_fields = ['creation__title', 'creation__reference', 'customer__name']
    readonly_fields = ['created_at', 'updated_at']
