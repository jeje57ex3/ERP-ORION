from django.contrib import admin
from .models import (
    ERPModule, ERPView, ERPAction, Role, RolePermission,
    UserCompanyAccess, UserPermissionOverride, DepartmentAccess, AccessLog,
)


@admin.register(ERPModule)
class ERPModuleAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'is_active', 'order']
    list_editable = ['is_active', 'order']
    ordering = ['order']


@admin.register(ERPView)
class ERPViewAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'module', 'is_active']
    list_filter = ['module']


@admin.register(ERPAction)
class ERPActionAdmin(admin.ModelAdmin):
    list_display = ['name', 'code']


class RolePermissionInline(admin.TabularInline):
    model = RolePermission
    extra = 0


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'company', 'is_system_role', 'is_active', 'user_count']
    list_filter = ['is_system_role', 'is_active', 'company']
    inlines = [RolePermissionInline]


@admin.register(UserCompanyAccess)
class UserCompanyAccessAdmin(admin.ModelAdmin):
    list_display = ['user', 'company', 'role', 'is_active', 'can_switch_company']
    list_filter = ['company', 'role', 'is_active']
    search_fields = ['user__username', 'user__email']


@admin.register(UserPermissionOverride)
class UserPermissionOverrideAdmin(admin.ModelAdmin):
    list_display = ['user', 'company', 'module', 'action', 'allowed', 'created_by']
    list_filter = ['allowed', 'company', 'module']


@admin.register(AccessLog)
class AccessLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'company', 'module', 'view_code', 'action', 'allowed', 'created_at']
    list_filter = ['allowed', 'module']
    readonly_fields = ['created_at']
    ordering = ['-created_at']
