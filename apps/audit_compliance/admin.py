from django.contrib import admin
from apps.core.models import AuditLog


class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'user', 'action', 'module', 'model_name', 'object_repr', 'company', 'ip_address']
    list_filter = ['action', 'module', 'company']
    search_fields = ['user__username', 'description', 'object_repr', 'model_name', 'ip_address']
    readonly_fields = ['user', 'company', 'action', 'module', 'model_name', 'object_id', 'object_repr',
                       'old_values', 'new_values', 'description', 'ip_address', 'user_agent', 'created_at']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# Register only if not already registered by another app (core)
if not admin.site.is_registered(AuditLog):
    admin.site.register(AuditLog, AuditLogAdmin)
