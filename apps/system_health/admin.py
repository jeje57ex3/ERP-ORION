from django.contrib import admin
from .models import (
    AlertThreshold, ErrorComment, HealthAuditLog, HealthPermission,
    IncidentTimeline, PostIncidentReport, RiskRegister, SensorReading,
    SystemError, SystemIncident,
)


@admin.register(SystemError)
class SystemErrorAdmin(admin.ModelAdmin):
    list_display  = ['uid', 'severity', 'module', 'error_type', 'status', 'occurrence_count', 'last_seen']
    list_filter   = ['severity', 'status', 'module', 'environment']
    search_fields = ['error_type', 'user_message', 'fingerprint', 'uid']
    raw_id_fields = ['affected_user', 'assigned_to', 'incident']
    readonly_fields = ['uid', 'fingerprint', 'first_seen', 'last_seen', 'created_at']


@admin.register(SystemIncident)
class SystemIncidentAdmin(admin.ModelAdmin):
    list_display = ['title', 'severity', 'status', 'started_at', 'resolved_at', 'assigned_to']
    list_filter  = ['severity', 'status']
    search_fields = ['title', 'description']
    filter_horizontal = ['affected_companies']


@admin.register(RiskRegister)
class RiskRegisterAdmin(admin.ModelAdmin):
    list_display = ['uid', 'title', 'category', 'probability', 'impact', 'status', 'owner']
    list_filter  = ['category', 'status', 'probability', 'impact']
    search_fields = ['uid', 'title', 'description']


@admin.register(SensorReading)
class SensorReadingAdmin(admin.ModelAdmin):
    list_display = ['sensor_type', 'value', 'status', 'collected_at']
    list_filter  = ['sensor_type', 'status']
    readonly_fields = ['collected_at']


@admin.register(AlertThreshold)
class AlertThresholdAdmin(admin.ModelAdmin):
    list_display = ['sensor_type', 'comparison', 'warning_threshold', 'critical_threshold', 'enabled']
    list_filter  = ['enabled', 'comparison']


@admin.register(HealthPermission)
class HealthPermissionAdmin(admin.ModelAdmin):
    list_display = ['user', 'can_view_health', 'can_view_errors', 'can_manage_incidents',
                    'can_administrate', 'can_view_sensitive']
    search_fields = ['user__username', 'user__email']


@admin.register(HealthAuditLog)
class HealthAuditLogAdmin(admin.ModelAdmin):
    list_display  = ['user', 'action', 'target_type', 'ip_address', 'created_at']
    list_filter   = ['action']
    readonly_fields = ['user', 'action', 'target_type', 'target_id', 'description',
                       'ip_address', 'created_at']
    search_fields = ['user__username', 'description']

    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False


admin.site.register(ErrorComment)
admin.site.register(IncidentTimeline)
admin.site.register(PostIncidentReport)
