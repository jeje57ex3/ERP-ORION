from django.contrib import admin
from .models import BackupJob, BackupRun


class RunInline(admin.TabularInline):
    model = BackupRun
    extra = 0
    readonly_fields = ['status', 'file_size_bytes', 'started_at', 'finished_at', 'error_message']
    can_delete = False
    max_num = 10


@admin.register(BackupJob)
class BackupJobAdmin(admin.ModelAdmin):
    list_display = ['name', 'job_type', 'schedule', 'storage_target', 'is_active',
                    'last_status', 'last_run_at', 'company']
    list_filter = ['job_type', 'schedule', 'is_active', 'company']
    search_fields = ['name']
    readonly_fields = ['created_at', 'updated_at', 'last_run_at', 'last_status']
    inlines = [RunInline]


@admin.register(BackupRun)
class BackupRunAdmin(admin.ModelAdmin):
    list_display = ['job', 'status', 'file_size_bytes', 'started_at', 'finished_at', 'company']
    list_filter = ['status', 'company']
    readonly_fields = ['started_at', 'finished_at']
