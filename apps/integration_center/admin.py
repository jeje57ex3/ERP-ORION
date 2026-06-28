from django.contrib import admin
from .models import IntegrationConfig, IntegrationSyncLog


class SyncLogInline(admin.TabularInline):
    model = IntegrationSyncLog
    extra = 0
    readonly_fields = ['status', 'records_synced', 'records_failed', 'started_at', 'finished_at']
    can_delete = False
    max_num = 10


@admin.register(IntegrationConfig)
class IntegrationConfigAdmin(admin.ModelAdmin):
    list_display = ['name', 'integration_type', 'is_active', 'last_sync_at', 'company', 'created_at']
    list_filter = ['integration_type', 'is_active', 'company']
    search_fields = ['name']
    readonly_fields = ['created_at', 'updated_at', 'last_sync_at']
    inlines = [SyncLogInline]


@admin.register(IntegrationSyncLog)
class IntegrationSyncLogAdmin(admin.ModelAdmin):
    list_display = ['integration', 'status', 'records_synced', 'records_failed', 'started_at', 'finished_at', 'company']
    list_filter = ['status', 'company']
    readonly_fields = ['started_at', 'finished_at']
