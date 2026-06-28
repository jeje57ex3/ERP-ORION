from django.contrib import admin
from django.utils.html import format_html
from .models import (
    DashboardProfile, DashboardWidget, UserDashboardWidget,
    DashboardShortcut, DashboardUserPreference, DashboardRequestBox,
    DashboardPersonalNote, DashboardGoal,
)


@admin.register(DashboardWidget)
class DashboardWidgetAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'module_code', 'widget_type', 'colored_icon', 'is_active', 'order']
    list_filter = ['widget_type', 'module_code', 'is_active', 'requires_permission']
    search_fields = ['name', 'code', 'description']
    list_editable = ['is_active', 'order']
    ordering = ['order', 'name']
    fieldsets = (
        (None, {'fields': ('name', 'code', 'description', 'module_code', 'widget_type')}),
        ('Affichage', {'fields': ('icon', 'color', 'template_name', 'default_width', 'default_height', 'order')}),
        ('Permissions', {'fields': ('requires_permission', 'permission_code', 'is_active')}),
    )

    def colored_icon(self, obj):
        return format_html(
            '<i class="{}" style="color:{};font-size:1.2rem"></i>',
            obj.icon, obj.color
        )
    colored_icon.short_description = 'Icône'


@admin.register(DashboardProfile)
class DashboardProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'company', 'name', 'layout_type', 'theme', 'is_default', 'widget_count']
    list_filter = ['company', 'layout_type', 'theme', 'is_default']
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'name']
    raw_id_fields = ['user']

    def widget_count(self, obj):
        return obj.user_widgets.count()
    widget_count.short_description = 'Widgets'

    def reset_dashboard(self, request, queryset):
        from .services import reset_user_dashboard
        for profile in queryset:
            reset_user_dashboard(profile.user, profile.company)
        self.message_user(request, f'{queryset.count()} dashboard(s) réinitialisé(s).')
    reset_dashboard.short_description = 'Réinitialiser le dashboard'
    actions = ['reset_dashboard']


@admin.register(UserDashboardWidget)
class UserDashboardWidgetAdmin(admin.ModelAdmin):
    list_display = ['dashboard_profile', 'widget', 'position_x', 'position_y', 'width', 'is_visible']
    list_filter = ['is_visible', 'widget__module_code', 'dashboard_profile__company']
    search_fields = ['dashboard_profile__user__username', 'widget__name']
    raw_id_fields = ['dashboard_profile']


@admin.register(DashboardShortcut)
class DashboardShortcutAdmin(admin.ModelAdmin):
    list_display = ['label', 'user', 'company', 'target_type', 'module_code', 'is_favorite', 'is_active', 'order']
    list_filter = ['company', 'target_type', 'module_code', 'is_favorite', 'is_active']
    search_fields = ['label', 'user__username', 'target_url', 'url_name']
    list_editable = ['order', 'is_active', 'is_favorite']
    raw_id_fields = ['user']


@admin.register(DashboardUserPreference)
class DashboardUserPreferenceAdmin(admin.ModelAdmin):
    list_display = ['user', 'company', 'default_period', 'compact_mode', 'auto_refresh', 'refresh_interval']
    list_filter = ['company', 'default_period', 'compact_mode', 'auto_refresh']
    search_fields = ['user__username']
    raw_id_fields = ['user']


@admin.register(DashboardRequestBox)
class DashboardRequestBoxAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'company', 'request_type', 'status', 'priority', 'due_date', 'created_at']
    list_filter = ['company', 'request_type', 'status', 'priority']
    search_fields = ['title', 'description', 'user__username']
    date_hierarchy = 'created_at'
    raw_id_fields = ['user']


@admin.register(DashboardPersonalNote)
class DashboardPersonalNoteAdmin(admin.ModelAdmin):
    list_display = ['user', 'company', 'title', 'color', 'is_pinned', 'updated_at']
    list_filter = ['company', 'is_pinned', 'color']
    search_fields = ['title', 'content', 'user__username']
    raw_id_fields = ['user']
    date_hierarchy = 'created_at'


@admin.register(DashboardGoal)
class DashboardGoalAdmin(admin.ModelAdmin):
    list_display = ['user', 'company', 'title', 'period', 'status', 'target_value', 'current_value', 'progress_pct']
    list_filter = ['company', 'period', 'status']
    search_fields = ['title', 'user__username']
    raw_id_fields = ['user']

    def progress_pct(self, obj):
        return f'{obj.progress_pct()} %'
    progress_pct.short_description = 'Avancement'
