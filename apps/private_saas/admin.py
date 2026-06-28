from django.contrib import admin
from .models import CompanyModule, PrivateSaaSSettings, CompanyBackup


@admin.register(CompanyModule)
class CompanyModuleAdmin(admin.ModelAdmin):
    list_display = ('company', 'module_code', 'module_name', 'is_enabled', 'enabled_at')
    list_filter  = ('is_enabled', 'module_code')
    search_fields = ('company__name', 'module_code')


@admin.register(PrivateSaaSSettings)
class PrivateSaaSSettingsAdmin(admin.ModelAdmin):
    list_display = ('private_mode_enabled', 'public_signup_enabled', 'maintenance_mode', 'updated_at')


@admin.register(CompanyBackup)
class CompanyBackupAdmin(admin.ModelAdmin):
    list_display = ('company', 'backup_type', 'status', 'size_display', 'created_at')
    list_filter  = ('status', 'backup_type')
    search_fields = ('company__name',)
