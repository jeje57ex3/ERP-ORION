from django.contrib import admin

from apps.system_updates.models import (
    SystemRollbackRun,
    SystemUpdateCheck,
    SystemUpdateRun,
    SystemUpdateSettings,
    SystemUpdateStepLog,
)


@admin.register(SystemUpdateSettings)
class SystemUpdateSettingsAdmin(admin.ModelAdmin):
    list_display = [
        'update_enabled', 'manual_only', 'git_branch',
        'require_backup_before_update', 'allow_rollback', 'updated_at',
    ]

    def has_add_permission(self, request):
        return not SystemUpdateSettings.objects.exists()


@admin.register(SystemUpdateCheck)
class SystemUpdateCheckAdmin(admin.ModelAdmin):
    list_display = [
        'status', 'current_commit', 'remote_commit', 'commits_behind', 'checked_at',
    ]
    readonly_fields = ['checked_at']

    def has_add_permission(self, request):
        return False


class SystemUpdateStepLogInline(admin.TabularInline):
    model = SystemUpdateStepLog
    extra = 0
    readonly_fields = [
        'step_code', 'step_name', 'level', 'message',
        'command', 'output', 'error_output',
        'started_at', 'finished_at', 'duration_seconds',
    ]

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(SystemUpdateRun)
class SystemUpdateRunAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'status', 'from_commit', 'to_commit',
        'started_by', 'started_at', 'finished_at',
    ]
    readonly_fields = ['started_at', 'finished_at']
    inlines = [SystemUpdateStepLogInline]

    def has_add_permission(self, request):
        return False


@admin.register(SystemRollbackRun)
class SystemRollbackRunAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'update_run', 'status', 'rollback_to_commit',
        'started_by', 'started_at', 'finished_at',
    ]
    readonly_fields = ['started_at', 'finished_at']

    def has_add_permission(self, request):
        return False
