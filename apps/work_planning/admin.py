from django.contrib import admin
from .models import (
    EmployeeProfile, WorkMission, WorkTask,
    DedicatedTimeBlock, PlanningConflict, CustomerRequest,
    EmployeeAvailabilityConstraint,
)


@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'company', 'role',
        'default_hours_per_day', 'weekly_capacity_hours',
        'accepts_overtime', 'max_overtime_hours_per_week',
        'normal_work_start', 'normal_work_end',
        'is_active',
    ]
    list_filter = ['company', 'role', 'is_active', 'accepts_overtime']
    search_fields = ['user__username', 'user__first_name', 'user__last_name']


@admin.register(WorkMission)
class WorkMissionAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'company', 'status', 'priority', 'start_date', 'end_date']
    list_filter = ['company', 'status', 'priority']
    search_fields = ['name', 'code']


@admin.register(WorkTask)
class WorkTaskAdmin(admin.ModelAdmin):
    list_display = ['name', 'mission', 'status', 'priority', 'assigned_to', 'due_date', 'auto_scheduled', 'is_locked']
    list_filter = ['status', 'priority', 'auto_scheduled', 'is_locked']
    search_fields = ['name', 'mission__name']


@admin.register(CustomerRequest)
class CustomerRequestAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'company', 'customer', 'urgency', 'status',
        'estimated_minutes', 'assigned_employee', 'requested_deadline', 'created_at',
    ]
    list_filter = ['company', 'status', 'urgency', 'source', 'auto_planning_enabled', 'is_locked']
    search_fields = ['title', 'description', 'customer__name', 'required_skill']
    date_hierarchy = 'created_at'
    readonly_fields = ['created_at', 'updated_at']


@admin.register(DedicatedTimeBlock)
class DedicatedTimeBlockAdmin(admin.ModelAdmin):
    list_display = ['employee', 'date', 'hours', 'mission', 'task', 'is_locked', 'created_by']
    list_filter = ['company', 'date', 'is_locked']
    search_fields = ['employee__user__username', 'mission__name']
    date_hierarchy = 'date'


@admin.register(PlanningConflict)
class PlanningConflictAdmin(admin.ModelAdmin):
    list_display = ['employee', 'date', 'total_hours_planned', 'max_hours', 'resolved']
    list_filter = ['company', 'resolved']
    search_fields = ['employee__user__username']


@admin.register(EmployeeAvailabilityConstraint)
class EmployeeAvailabilityConstraintAdmin(admin.ModelAdmin):
    list_display = [
        'employee', 'company', 'title',
        'constraint_type', 'priority', 'recurrence',
        'weekday', 'start_time', 'end_time', 'is_active',
    ]
    list_filter = ['company', 'constraint_type', 'priority', 'recurrence', 'is_active']
    search_fields = ['employee__user__first_name', 'employee__user__last_name', 'title', 'description']
