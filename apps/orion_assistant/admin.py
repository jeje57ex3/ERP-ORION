from django.contrib import admin
from .models import AssistantConversation, AssistantMessage


class MessageInline(admin.TabularInline):
    model = AssistantMessage
    extra = 0
    readonly_fields = ['role', 'content', 'tokens_used', 'created_at']
    can_delete = False


@admin.register(AssistantConversation)
class AssistantConversationAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'context_module', 'is_archived', 'company', 'updated_at']
    list_filter = ['is_archived', 'company', 'context_module']
    search_fields = ['title', 'user__username']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [MessageInline]
