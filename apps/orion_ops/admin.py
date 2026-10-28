"""
apps/orion_ops/admin.py — Administration Django pour le module Orion Ops.
"""
from django.contrib import admin
from django.utils.html import format_html

from .models import (
    ServiceComponent, ComponentDependency,
    SLOTarget, SLOBreach,
    Deployment,
    RestoreTest,
    DataQualityAnomaly,
    AlertRule,
    BusinessMetricReading,
    HealthScoreRecord,
    FailedTask,
    CapacityTrend,
    BCPScenario,
    FailureTest,
)


# ─── ServiceComponent ─────────────────────────────────────────────────────────

@admin.register(ServiceComponent)
class ServiceComponentAdmin(admin.ModelAdmin):
    list_display = ('name', 'component_type', 'criticality', 'colored_status', 'host', 'port', 'is_active', 'last_check')
    list_filter = ('component_type', 'criticality', 'status', 'is_active')
    search_fields = ('name', 'slug', 'host')
    readonly_fields = ('created_at', 'updated_at', 'last_check')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('criticality', 'name')

    def colored_status(self, obj):
        colors = {
            'ok': '#22C55E', 'degraded': '#F59E0B',
            'down': '#EF4444', 'unknown': '#94A3B8', 'maintenance': '#60A5FA',
        }
        color = colors.get(obj.status, '#94A3B8')
        return format_html('<span style="color:{};font-weight:600">● {}</span>', color, obj.get_status_display())
    colored_status.short_description = 'Statut'


@admin.register(ComponentDependency)
class ComponentDependencyAdmin(admin.ModelAdmin):
    list_display = ('source', 'target', 'dep_type', 'impact_desc')
    list_filter = ('dep_type',)
    autocomplete_fields = ('source', 'target')


# ─── SLO ─────────────────────────────────────────────────────────────────────

@admin.register(SLOTarget)
class SLOTargetAdmin(admin.ModelAdmin):
    list_display = ('name', 'sli_sensor', 'period', 'target_pct', 'current_value_display',
                    'error_budget_display', 'colored_status', 'enabled')
    list_filter = ('period', 'status', 'enabled')
    search_fields = ('name', 'slug', 'sli_sensor')
    readonly_fields = ('current_value', 'error_budget_pct', 'status', 'created_at', 'updated_at')
    filter_horizontal = ('components',)
    prepopulated_fields = {'slug': ('name',)}

    def current_value_display(self, obj):
        if obj.current_value is None:
            return '—'
        return f'{obj.current_value:.2f} %'
    current_value_display.short_description = 'Valeur actuelle'

    def error_budget_display(self, obj):
        if obj.error_budget_pct is None:
            return '—'
        color = '#22C55E' if obj.error_budget_pct > 50 else ('#F59E0B' if obj.error_budget_pct > 10 else '#EF4444')
        return format_html('<span style="color:{};font-weight:600">{:.0f} %</span>', color, obj.error_budget_pct)
    error_budget_display.short_description = 'Budget restant'

    def colored_status(self, obj):
        colors = {'ok': '#22C55E', 'at_risk': '#F59E0B', 'breached': '#EF4444',
                  'inactive': '#94A3B8', 'no_data': '#94A3B8'}
        c = colors.get(obj.status, '#94A3B8')
        return format_html('<span style="color:{};font-weight:600">{}</span>', c, obj.get_status_display())
    colored_status.short_description = 'Statut'


@admin.register(SLOBreach)
class SLOBreachAdmin(admin.ModelAdmin):
    list_display = ('slo', 'severity', 'actual_pct', 'target_pct', 'budget_consumed_pct', 'created_at')
    list_filter = ('severity',)
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'


# ─── Deployment ───────────────────────────────────────────────────────────────

@admin.register(Deployment)
class DeploymentAdmin(admin.ModelAdmin):
    list_display = ('version', 'environment', 'deployed_at', 'deployed_by', 'colored_result',
                    'migrations_count', 'tests_passed')
    list_filter = ('environment', 'result')
    readonly_fields = ('uid', 'created_at', 'updated_at')
    search_fields = ('version', 'git_commit', 'git_branch')
    date_hierarchy = 'deployed_at'

    def colored_result(self, obj):
        colors = {'success': '#22C55E', 'failed': '#EF4444', 'partial': '#F59E0B',
                  'rolled_back': '#F59E0B', 'pending': '#60A5FA'}
        c = colors.get(obj.result, '#94A3B8')
        return format_html('<span style="color:{};font-weight:600">{}</span>', c, obj.get_result_display())
    colored_result.short_description = 'Résultat'


# ─── RestoreTest ──────────────────────────────────────────────────────────────

@admin.register(RestoreTest)
class RestoreTestAdmin(admin.ModelAdmin):
    list_display = ('tested_at', 'backup_job', 'colored_result', 'rto_minutes',
                    'rpo_minutes', 'tables_checked', 'rows_verified', 'is_automated')
    list_filter = ('result', 'is_automated')
    readonly_fields = ('tested_at',)
    date_hierarchy = 'tested_at'

    def colored_result(self, obj):
        colors = {'success': '#22C55E', 'partial': '#F59E0B', 'failed': '#EF4444'}
        c = colors.get(obj.result, '#94A3B8')
        return format_html('<span style="color:{};font-weight:600">{}</span>', c, obj.get_result_display())
    colored_result.short_description = 'Résultat'


# ─── DataQualityAnomaly ───────────────────────────────────────────────────────

@admin.register(DataQualityAnomaly)
class DataQualityAnomalyAdmin(admin.ModelAdmin):
    list_display = ('colored_severity', 'get_anomaly_type_display', 'module', 'count',
                    'status', 'owner', 'detected_at', 'resolved_at')
    list_filter = ('severity', 'status', 'module')
    readonly_fields = ('detected_at',)
    search_fields = ('anomaly_type', 'cause')
    date_hierarchy = 'detected_at'

    def colored_severity(self, obj):
        colors = {'critical': '#EF4444', 'high': '#F59E0B', 'medium': '#60A5FA', 'low': '#94A3B8'}
        c = colors.get(obj.severity, '#94A3B8')
        return format_html('<span style="color:{};font-weight:700">{}</span>', c, obj.get_severity_display())
    colored_severity.short_description = 'Gravité'

    def get_anomaly_type_display(self, obj):
        return obj.get_anomaly_type_display()
    get_anomaly_type_display.short_description = 'Type'


# ─── AlertRule ────────────────────────────────────────────────────────────────

@admin.register(AlertRule)
class AlertRuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'source', 'metric_key', 'operator', 'threshold',
                    'severity', 'enabled', 'last_triggered', 'trigger_count')
    list_filter = ('source', 'severity', 'enabled')
    readonly_fields = ('last_triggered', 'last_status', 'trigger_count', 'created_at', 'updated_at')
    search_fields = ('name', 'metric_key')


# ─── BusinessMetricReading ────────────────────────────────────────────────────

@admin.register(BusinessMetricReading)
class BusinessMetricReadingAdmin(admin.ModelAdmin):
    list_display = ('metric_type', 'value', 'colored_status', 'company', 'collected_at')
    list_filter = ('metric_type', 'status')
    readonly_fields = ('collected_at',)
    date_hierarchy = 'collected_at'

    def colored_status(self, obj):
        colors = {'ok': '#22C55E', 'warning': '#F59E0B', 'critical': '#EF4444', 'unknown': '#94A3B8'}
        c = colors.get(obj.status, '#94A3B8')
        return format_html('<span style="color:{}">{}</span>', c, obj.get_status_display())
    colored_status.short_description = 'Statut'


# ─── HealthScoreRecord ────────────────────────────────────────────────────────

@admin.register(HealthScoreRecord)
class HealthScoreRecordAdmin(admin.ModelAdmin):
    list_display = ('domain_display', 'score_display', 'colored_status', 'is_stale', 'computed_at', 'expires_at')
    list_filter = ('domain', 'status', 'is_stale')
    readonly_fields = ('computed_at',)
    date_hierarchy = 'computed_at'

    def domain_display(self, obj):
        return obj.get_domain_display()
    domain_display.short_description = 'Domaine'

    def score_display(self, obj):
        return f'{obj.score}/100' if obj.score is not None else '—'
    score_display.short_description = 'Score'

    def colored_status(self, obj):
        colors = {'ok': '#22C55E', 'warning': '#F59E0B', 'critical': '#EF4444',
                  'unavailable': '#94A3B8', 'stale': '#94A3B8'}
        c = colors.get(obj.status, '#94A3B8')
        return format_html('<span style="color:{}">{}</span>', c, obj.get_status_display())
    colored_status.short_description = 'Statut'


# ─── FailedTask ───────────────────────────────────────────────────────────────

@admin.register(FailedTask)
class FailedTaskAdmin(admin.ModelAdmin):
    list_display = ('task_name', 'queue', 'colored_status', 'error_type', 'retries',
                    'can_replay', 'failed_at', 'replayed_at')
    list_filter = ('status', 'queue', 'can_replay')
    readonly_fields = ('task_id', 'failed_at', 'replayed_at')
    search_fields = ('task_name', 'error_type', 'task_id')
    date_hierarchy = 'failed_at'

    def colored_status(self, obj):
        colors = {'failed': '#EF4444', 'retrying': '#F59E0B', 'replayed': '#22C55E', 'closed': '#94A3B8'}
        c = colors.get(obj.status, '#94A3B8')
        return format_html('<span style="color:{};font-weight:600">{}</span>', c, obj.get_status_display())
    colored_status.short_description = 'Statut'


# ─── CapacityTrend ────────────────────────────────────────────────────────────

@admin.register(CapacityTrend)
class CapacityTrendAdmin(admin.ModelAdmin):
    list_display = ('resource_type', 'current_value', 'growth_7d_pct', 'growth_30d_pct',
                    'days_until_limit_display', 'saturation_date', 'computed_at')
    list_filter = ('resource_type',)
    readonly_fields = ('computed_at',)
    date_hierarchy = 'computed_at'

    def days_until_limit_display(self, obj):
        if obj.days_until_limit is None:
            return '∞'
        if obj.days_until_limit <= 7:
            return format_html('<span style="color:#EF4444;font-weight:700">{} jours</span>', obj.days_until_limit)
        if obj.days_until_limit <= 30:
            return format_html('<span style="color:#F59E0B;font-weight:600">{} jours</span>', obj.days_until_limit)
        return f'{obj.days_until_limit} jours'
    days_until_limit_display.short_description = 'Jours avant limite'


# ─── BCPScenario ──────────────────────────────────────────────────────────────

@admin.register(BCPScenario)
class BCPScenarioAdmin(admin.ModelAdmin):
    list_display = ('name', 'scenario_type', 'priority_badge', 'rto_hours', 'rpo_hours',
                    'last_result', 'last_exercised', 'needs_retest_flag', 'is_active')
    list_filter = ('scenario_type', 'priority', 'last_result', 'is_active')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    filter_horizontal = ('affected_components',)

    def priority_badge(self, obj):
        colors = {'critical': '#EF4444', 'high': '#F59E0B', 'medium': '#60A5FA', 'low': '#94A3B8'}
        c = colors.get(obj.priority, '#94A3B8')
        return format_html('<span style="color:{};font-weight:700">{}</span>', c, obj.get_priority_display())
    priority_badge.short_description = 'Priorité'

    def needs_retest_flag(self, obj):
        if obj.needs_retest:
            return format_html('<span style="color:#EF4444;font-weight:700">⚠ À retester</span>')
        return format_html('<span style="color:#22C55E">✓</span>')
    needs_retest_flag.short_description = 'Retest'


# ─── FailureTest ──────────────────────────────────────────────────────────────

@admin.register(FailureTest)
class FailureTestAdmin(admin.ModelAdmin):
    list_display = ('name', 'test_type', 'target_component', 'colored_result',
                    'recovery_time_secs', 'automated_recovery', 'remediation_required',
                    'executed_by', 'executed_at')
    list_filter = ('test_type', 'result', 'remediation_required', 'remediation_done')
    search_fields = ('name', 'description', 'impact_observed')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'

    def colored_result(self, obj):
        colors = {'success': '#22C55E', 'partial': '#F59E0B', 'failed': '#EF4444',
                  'aborted': '#94A3B8', 'pending': '#60A5FA'}
        c = colors.get(obj.result, '#94A3B8')
        return format_html('<span style="color:{};font-weight:600">{}</span>', c, obj.get_result_display())
    colored_result.short_description = 'Résultat'
