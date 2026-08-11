from django.contrib import admin
from .models import BackupJob, BackupSchedule, BackupRestoreLog


@admin.register(BackupJob)
class BackupJobAdmin(admin.ModelAdmin):
    list_display  = ('name', 'company', 'backup_type', 'scope', 'status', 'file_size_display', 'created_at')
    list_filter   = ('status', 'backup_type', 'scope')
    search_fields = ('name', 'company__name')
    readonly_fields = ('created_at', 'started_at', 'finished_at', 'duration_seconds', 'checksum', 'file_size')
    date_hierarchy = 'created_at'


@admin.register(BackupSchedule)
class BackupScheduleAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'scope', 'frequency', 'time', 'is_active', 'last_run_at')
    list_filter  = ('frequency', 'scope', 'is_active')


@admin.register(BackupRestoreLog)
class BackupRestoreLogAdmin(admin.ModelAdmin):
    list_display = ('backup', 'company', 'status', 'restored_by', 'started_at')
    list_filter  = ('status',)
    readonly_fields = ('started_at', 'finished_at', 'created_at')
