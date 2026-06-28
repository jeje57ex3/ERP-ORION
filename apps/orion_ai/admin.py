from django.contrib import admin

from apps.orion_ai.models import (
    OrionAIAuditLog,
    OrionAIConversation,
    OrionAIMemory,
    OrionAIMessage,
    OrionAIProposedAction,
    OrionAISettings,
    OrionAIToolCall,
)


@admin.register(OrionAISettings)
class OrionAISettingsAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'is_global', 'company', 'ai_enabled', 'default_provider', 'default_model', 'updated_at']
    list_filter = ['is_global', 'ai_enabled', 'default_provider']


class OrionAIMessageInline(admin.TabularInline):
    model = OrionAIMessage
    extra = 0
    readonly_fields = ['role', 'content', 'provider', 'model', 'created_at']
    can_delete = False


@admin.register(OrionAIConversation)
class OrionAIConversationAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'company', 'status', 'context_module', 'created_at']
    list_filter = ['status', 'context_module']
    search_fields = ['title', 'user__username']
    inlines = [OrionAIMessageInline]


@admin.register(OrionAIMessage)
class OrionAIMessageAdmin(admin.ModelAdmin):
    list_display = ['role', 'conversation', 'provider', 'model', 'token_input', 'token_output', 'created_at']
    list_filter = ['role', 'provider']


@admin.register(OrionAIProposedAction)
class OrionAIProposedActionAdmin(admin.ModelAdmin):
    list_display = ['title', 'action_code', 'status', 'is_write_action', 'is_dangerous_action', 'confirmed_by', 'created_at']
    list_filter = ['status', 'is_write_action', 'is_dangerous_action']


@admin.register(OrionAIToolCall)
class OrionAIToolCallAdmin(admin.ModelAdmin):
    list_display = ['tool_name', 'status', 'is_write_action', 'is_dangerous_action', 'executed_by', 'created_at']
    list_filter = ['status', 'is_write_action']


@admin.register(OrionAIMemory)
class OrionAIMemoryAdmin(admin.ModelAdmin):
    list_display = ['scope', 'key', 'company', 'user', 'is_active', 'is_sensitive', 'created_at']
    list_filter = ['scope', 'is_active', 'is_sensitive']


@admin.register(OrionAIAuditLog)
class OrionAIAuditLogAdmin(admin.ModelAdmin):
    list_display = ['event_type', 'title', 'user', 'company', 'ip_address', 'created_at']
    list_filter = ['event_type']
    search_fields = ['title', 'user__username']
    readonly_fields = ['payload']
