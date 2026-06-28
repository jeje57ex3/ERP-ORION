from django.contrib import admin
from .models import SystemHealthCheck, SystemObservabilityAlert, SystemAlertRule


@admin.register(SystemHealthCheck)
class SystemHealthCheckAdmin(admin.ModelAdmin):
    list_display = ['check_type', 'status', 'response_time_ms', 'message', 'company', 'checked_at']
    list_filter = ['check_type', 'status', 'company']
    readonly_fields = ['checked_at']


@admin.register(SystemObservabilityAlert)
class SystemObservabilityAlertAdmin(admin.ModelAdmin):
    list_display = ['title', 'alert_type', 'severity', 'is_acknowledged', 'company', 'created_at']
    list_filter = ['severity', 'is_acknowledged', 'company']
    search_fields = ['title', 'message']
    readonly_fields = ['created_at', 'acknowledged_at']


@admin.register(SystemAlertRule)
class SystemAlertRuleAdmin(admin.ModelAdmin):
    list_display = ['name', 'check_type', 'trigger_status', 'is_active', 'company', 'created_at']
    list_filter = ['check_type', 'is_active', 'company']
