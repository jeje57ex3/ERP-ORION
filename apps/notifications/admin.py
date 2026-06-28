"""
apps/notifications/admin.py
"""
from django.contrib import admin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'user', 'company', 'notification_type', 'priority',
        'is_read', 'email_sent', 'created_at',
    )
    list_filter = (
        'is_read', 'notification_type', 'priority', 'created_at',
        'email_sent', 'source_module',
    )
    search_fields = ('title', 'message', 'user__username', 'user__email')
    readonly_fields = ('created_at', 'read_at', 'email_sent_at')
    list_select_related = ('user', 'company')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)

    fieldsets = (
        ('Contenu', {
            'fields': ('user', 'company', 'title', 'message', 'notification_type', 'priority'),
        }),
        ('Apparence', {
            'fields': ('icon', 'icon_color'),
        }),
        ('Lien', {
            'fields': ('link_url', 'link_label'),
            'classes': ('collapse',),
        }),
        ('Source', {
            'fields': ('source_module', 'source_model', 'source_id'),
            'classes': ('collapse',),
        }),
        ('Statut', {
            'fields': ('is_read', 'read_at', 'email_sent', 'email_sent_at', 'created_at'),
        }),
    )

    actions = ['mark_as_read', 'mark_as_unread']

    @admin.action(description='Marquer comme lues')
    def mark_as_read(self, request, queryset):
        from django.utils import timezone
        updated = queryset.filter(is_read=False).update(is_read=True, read_at=timezone.now())
        self.message_user(request, f'{updated} notification(s) marquée(s) comme lue(s).')

    @admin.action(description='Marquer comme non lues')
    def mark_as_unread(self, request, queryset):
        updated = queryset.filter(is_read=True).update(is_read=False, read_at=None)
        self.message_user(request, f'{updated} notification(s) marquée(s) comme non lue(s).')
