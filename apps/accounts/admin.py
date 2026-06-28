from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import UserProfile, UserModulePermission, UserActivity


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    extra = 0
    filter_horizontal = ['companies']
    fieldsets = (
        ('Profil', {'fields': ('role', 'phone', 'mobile', 'job_title', 'department', 'avatar', 'bio')}),
        ('Entreprises', {'fields': ('companies', 'current_company')}),
        ('Préférences', {'fields': ('language', 'timezone', 'items_per_page', 'email_notifications')}),
    )


class UserModulePermissionInline(admin.TabularInline):
    model = UserModulePermission
    extra = 0


def get_employee_link(obj):
    """Colonne salarié lié dans l'admin utilisateur."""
    try:
        emp = obj.employee_profile
        return f'{emp.full_name} (#{emp.pk})'
    except Exception:
        if obj.is_superuser or obj.is_staff:
            return '— admin —'
        return '⚠ Aucun salarié'
get_employee_link.short_description = 'Salarié lié'


class CustomUserAdmin(BaseUserAdmin):
    inlines = [UserProfileInline]
    list_display = ['username', 'email', 'first_name', 'last_name', 'is_active', 'is_staff', get_employee_link, 'date_joined']


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


@admin.register(UserActivity)
class UserActivityAdmin(admin.ModelAdmin):
    list_display = ['user', 'company', 'action', 'ip_address', 'created_at']
    list_filter = ['company', 'created_at']
    search_fields = ['user__username', 'action']
    readonly_fields = ['created_at']
