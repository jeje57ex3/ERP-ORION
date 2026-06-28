from django.contrib import admin
from .models import AutomationRule, AutomationRun


class AutomationRunInline(admin.TabularInline):
    model = AutomationRun
    extra = 0
    readonly_fields = ['status', 'started_at', 'finished_at', 'error_message']
    fields = ['status', 'started_at', 'finished_at', 'error_message']
    can_delete = False
    max_num = 10


@admin.register(AutomationRule)
class AutomationRuleAdmin(admin.ModelAdmin):
    list_display = ['name', 'trigger_type', 'is_active', 'run_count', 'last_run_at', 'company', 'created_by']
    list_filter = ['trigger_type', 'is_active', 'company']
    search_fields = ['name', 'description']
    readonly_fields = ['run_count', 'last_run_at', 'created_at', 'updated_at']
    inlines = [AutomationRunInline]


@admin.register(AutomationRun)
class AutomationRunAdmin(admin.ModelAdmin):
    list_display = ['rule', 'status', 'started_at', 'finished_at', 'company']
    list_filter = ['status', 'company', 'rule']
    readonly_fields = ['started_at', 'finished_at', 'trigger_payload', 'result_payload', 'error_message']
