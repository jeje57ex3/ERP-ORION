from django.contrib import admin
from django.utils import timezone
from .models import SmartAlert


@admin.register(SmartAlert)
class SmartAlertAdmin(admin.ModelAdmin):
    list_display = ['title', 'priority', 'status', 'source_module', 'company', 'brand_key', 'assigned_to', 'created_at']
    list_filter = ['priority', 'status', 'source_module', 'company']
    search_fields = ['title', 'message', 'related_object_id']
    readonly_fields = ['created_at', 'updated_at', 'resolved_at']
    list_select_related = ['company', 'assigned_to', 'resolved_by']
    actions = ['mark_resolved', 'mark_ignored']

    @admin.action(description='Marquer comme résolues')
    def mark_resolved(self, request, queryset):
        queryset.update(status='resolved', resolved_at=timezone.now(), resolved_by=request.user)

    @admin.action(description='Ignorer')
    def mark_ignored(self, request, queryset):
        queryset.update(status='ignored')
