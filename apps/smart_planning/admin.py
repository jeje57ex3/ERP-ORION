from django.contrib import admin
from .models import PlanningEvent, PlanningConflict


@admin.register(PlanningEvent)
class PlanningEventAdmin(admin.ModelAdmin):
    list_display = ['title', 'event_type', 'employee', 'customer', 'start_at', 'end_at', 'status', 'company']
    list_filter = ['event_type', 'status', 'company']
    search_fields = ['title', 'employee__first_name', 'employee__last_name', 'customer__name']
    date_hierarchy = 'start_at'
    readonly_fields = ['created_at', 'updated_at']


@admin.register(PlanningConflict)
class PlanningConflictAdmin(admin.ModelAdmin):
    list_display = ['event', 'conflict_type', 'severity', 'is_resolved', 'created_at']
    list_filter = ['conflict_type', 'severity', 'is_resolved', 'company']
    readonly_fields = ['created_at']
