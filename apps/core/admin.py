from django.contrib import admin
from .models import Company, CompanySettings, AuditLog, Connector, Notification


class CompanySettingsInline(admin.StackedInline):
    model = CompanySettings
    extra = 0


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ['name', 'sector', 'city', 'email', 'is_active', 'created_at']
    list_filter = ['sector', 'is_active', 'country']
    search_fields = ['name', 'email', 'siret']
    prepopulated_fields = {'slug': ('name',)}
    inlines = [CompanySettingsInline]
    fieldsets = (
        ('Identité', {'fields': ('name', 'slug', 'sector', 'logo', 'is_active')}),
        ('Coordonnées', {'fields': ('email', 'phone', 'address', 'city', 'zip_code', 'country')}),
        ('Légal', {'fields': ('siret', 'siren', 'vat_number', 'rcs', 'legal_form', 'capital')}),
        ('Branding', {'fields': ('primary_color', 'secondary_color', 'accent_color')}),
        ('Paramètres', {'fields': ('currency', 'default_vat_rate', 'invoice_prefix', 'quote_prefix')}),
        ('Bancaire', {'fields': ('bank_name', 'iban', 'bic')}),
    )


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'user', 'company', 'action', 'module', 'model_name', 'object_repr', 'ip_address']
    list_filter = ['action', 'module', 'company', 'created_at']
    search_fields = ['user__username', 'object_repr', 'description', 'ip_address']
    readonly_fields = [
        'created_at', 'user', 'company', 'action', 'module',
        'model_name', 'object_id', 'object_repr',
        'old_values', 'new_values', 'description', 'ip_address', 'user_agent',
    ]
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(Connector)
class ConnectorAdmin(admin.ModelAdmin):
    list_display = ['company', 'connector_type', 'name', 'is_active', 'last_sync']
    list_filter = ['connector_type', 'is_active', 'company']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'title', 'level', 'is_read', 'created_at']
    list_filter = ['level', 'is_read']
