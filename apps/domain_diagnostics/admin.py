from django.contrib import admin

from apps.domain_diagnostics.models import (
    CloudflareZoneConfig,
    DomainDiagnosticRun,
    DomainDiagnosticTarget,
    DomainIssue,
    DomainRepairLog,
)


@admin.register(CloudflareZoneConfig)
class CloudflareZoneConfigAdmin(admin.ModelAdmin):
    list_display = ('zone_name', 'zone_id', 'company', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('zone_name', 'company__name')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(DomainDiagnosticTarget)
class DomainDiagnosticTargetAdmin(admin.ModelAdmin):
    list_display = ('domain', 'brand_key', 'company', 'last_status', 'last_scan_at', 'is_active')
    list_filter = ('is_active', 'last_status', 'target_type')
    search_fields = ('domain', 'brand_key', 'company__name')
    readonly_fields = ('last_scan_at', 'last_status', 'created_at', 'updated_at')


@admin.register(DomainDiagnosticRun)
class DomainDiagnosticRunAdmin(admin.ModelAdmin):
    list_display = ('target', 'company', 'status', 'summary', 'started_at', 'finished_at')
    list_filter = ('status',)
    search_fields = ('target__domain', 'company__name')
    readonly_fields = ('started_at', 'finished_at', 'raw_results')


@admin.register(DomainIssue)
class DomainIssueAdmin(admin.ModelAdmin):
    list_display = ('title', 'target', 'issue_type', 'severity', 'status', 'detected_at')
    list_filter = ('severity', 'status', 'issue_type')
    search_fields = ('title', 'target__domain', 'company__name')
    readonly_fields = ('detected_at',)


@admin.register(DomainRepairLog)
class DomainRepairLogAdmin(admin.ModelAdmin):
    list_display = ('repair_code', 'target', 'status', 'executed_by', 'executed_at')
    list_filter = ('status', 'repair_code')
    search_fields = ('target__domain', 'repair_code', 'company__name')
    readonly_fields = ('executed_at',)
