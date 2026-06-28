from django.contrib import admin

from .models import (
    PDCACycle, PDCAPlan, PDCADo, PDCACheck, PDCAAct,
    PDCAAction, PDCAKPI, PDCAStandard, PDCATemplate, PDCAEventLog,
)


class PDCAPlanInline(admin.StackedInline):
    model = PDCAPlan
    extra = 0


class PDCADoInline(admin.StackedInline):
    model = PDCADo
    extra = 0


class PDCACheckInline(admin.StackedInline):
    model = PDCACheck
    extra = 0


class PDCAActInline(admin.StackedInline):
    model = PDCAAct
    extra = 0


class PDCAActionInline(admin.TabularInline):
    model = PDCAAction
    extra = 0
    fields = ('title', 'status', 'assigned_to', 'due_date', 'order')


class PDCAKPIInline(admin.TabularInline):
    model = PDCAKPI
    extra = 0
    fields = ('name', 'unit', 'before_value', 'target_value', 'after_value')


@admin.register(PDCACycle)
class PDCACycleAdmin(admin.ModelAdmin):
    list_display = ('title', 'company', 'category', 'priority', 'stage', 'status', 'owner', 'target_date', 'created_at')
    list_filter = ('stage', 'status', 'category', 'priority', 'company')
    search_fields = ('title', 'problem_statement', 'objective')
    readonly_fields = ('created_at', 'updated_at', 'completed_at')
    raw_id_fields = ('owner', 'created_by', 'parent_cycle')
    inlines = [PDCAPlanInline, PDCADoInline, PDCACheckInline, PDCAActInline, PDCAActionInline, PDCAKPIInline]


@admin.register(PDCAStandard)
class PDCAStandardAdmin(admin.ModelAdmin):
    list_display = ('title', 'company', 'module', 'is_active', 'created_at')
    list_filter = ('is_active', 'company', 'module')
    search_fields = ('title', 'description')


@admin.register(PDCATemplate)
class PDCATemplateAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'priority', 'is_system_template', 'is_active')
    list_filter = ('category', 'is_system_template', 'is_active')
    search_fields = ('title', 'description')


@admin.register(PDCAEventLog)
class PDCAEventLogAdmin(admin.ModelAdmin):
    list_display = ('cycle', 'event_type', 'title', 'created_by', 'created_at')
    list_filter = ('event_type',)
    readonly_fields = ('created_at',)
    raw_id_fields = ('cycle', 'created_by')
