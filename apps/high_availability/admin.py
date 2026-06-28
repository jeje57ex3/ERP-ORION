from django.contrib import admin
from apps.high_availability.models import (
    OrionHANode,
    OrionHASettings,
    OrionHAReplicationStatus,
    OrionHAFailoverEvent,
    OrionHAClusterLock,
)


@admin.register(OrionHANode)
class OrionHANodeAdmin(admin.ModelAdmin):
    list_display = ('node_id', 'name', 'role', 'priority', 'status', 'is_current_active', 'is_failover_target', 'last_heartbeat_at')
    list_filter = ('role', 'status', 'is_current_active', 'is_enabled')
    search_fields = ('node_id', 'name', 'region')
    readonly_fields = ('created_at', 'updated_at', 'last_heartbeat_at', 'last_health_payload')
    ordering = ('priority',)
    fieldsets = (
        ('Identité', {'fields': ('node_id', 'name', 'role', 'priority', 'region')}),
        ('Réseau', {'fields': ('base_url', 'public_ip', 'private_ip')}),
        ('État', {'fields': ('status', 'is_enabled', 'is_current_active', 'is_failover_target', 'allow_auto_failover')}),
        ('Réplication', {'fields': ('database_role', 'database_status', 'replication_lag_seconds', 'media_sync_status', 'media_last_sync_at')}),
        ('Heartbeat', {'fields': ('last_heartbeat_at', 'last_health_payload', 'app_version', 'git_commit')}),
        ('Méta', {'fields': ('notes', 'created_at', 'updated_at')}),
    )


@admin.register(OrionHASettings)
class OrionHASettingsAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'failover_enabled', 'automatic_failover_enabled', 'require_manual_confirmation', 'updated_at')
    readonly_fields = ('updated_at', 'updated_by')

    def has_add_permission(self, request):
        return not OrionHASettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(OrionHAReplicationStatus)
class OrionHAReplicationStatusAdmin(admin.ModelAdmin):
    list_display = ('node', 'database_status', 'io_thread_running', 'sql_thread_running', 'seconds_behind_primary', 'checked_at')
    readonly_fields = ('checked_at', 'payload')


@admin.register(OrionHAFailoverEvent)
class OrionHAFailoverEventAdmin(admin.ModelAdmin):
    list_display = ('id', 'event_type', 'status', 'from_node', 'to_node', 'started_by', 'started_at', 'finished_at')
    list_filter = ('event_type', 'status')
    readonly_fields = ('started_at', 'finished_at', 'steps', 'result_payload', 'error_message')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(OrionHAClusterLock)
class OrionHAClusterLockAdmin(admin.ModelAdmin):
    list_display = ('active_node_id', 'lock_token', 'updated_at')
    readonly_fields = ('updated_at',)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
