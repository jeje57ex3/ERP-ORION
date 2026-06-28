from django.contrib import admin
from .models import WorkflowTemplate, WorkflowInstance, WorkflowAction


class WorkflowActionInline(admin.TabularInline):
    model = WorkflowAction
    extra = 0
    readonly_fields = ['user', 'action', 'step_index', 'comment', 'created_at']
    can_delete = False


@admin.register(WorkflowTemplate)
class WorkflowTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'object_type', 'is_active', 'company']
    list_filter = ['object_type', 'is_active', 'company']
    search_fields = ['name', 'code']


@admin.register(WorkflowInstance)
class WorkflowInstanceAdmin(admin.ModelAdmin):
    list_display = ['object_type', 'object_id', 'status', 'current_step_index', 'company', 'created_by', 'created_at']
    list_filter = ['status', 'object_type', 'company']
    readonly_fields = ['created_at', 'completed_at']
    inlines = [WorkflowActionInline]
