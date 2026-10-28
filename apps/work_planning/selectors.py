from datetime import date, timedelta
from decimal import Decimal
from django.db.models import Sum, Count, Q

from .models import (
    EmployeeProfile, WorkMission, WorkTask,
    DedicatedTimeBlock, PlanningConflict, CustomerRequest,
    EmployeeAvailabilityConstraint,
)


def get_employee_profiles(company):
    return EmployeeProfile.objects.filter(company=company, is_active=True).select_related('user')


def get_all_employee_profiles(company):
    return EmployeeProfile.objects.filter(company=company).select_related('user')


def get_missions(company, status=None):
    qs = WorkMission.objects.filter(company=company)
    if status:
        qs = qs.filter(status=status)
    return qs.select_related('created_by')


def get_active_missions(company):
    return get_missions(company, status='active')


def get_tasks_for_mission(mission):
    return WorkTask.objects.filter(mission=mission).select_related(
        'assigned_to', 'customer_request'
    ).order_by('order', 'created_at')


def get_week_dates(ref_date: date):
    monday = ref_date - timedelta(days=ref_date.weekday())
    return [monday + timedelta(days=i) for i in range(7)]


def get_time_blocks_for_week(company, week_start: date):
    week_end = week_start + timedelta(days=6)
    return (
        DedicatedTimeBlock.objects
        .filter(company=company, date__range=(week_start, week_end))
        .select_related('employee__user', 'mission', 'task')
        .order_by('date', 'employee')
    )


def get_dashboard_stats(company):
    active_missions = WorkMission.objects.filter(company=company, status='active').count()
    total_employees = EmployeeProfile.objects.filter(company=company, is_active=True).count()

    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    hours_this_week = (
        DedicatedTimeBlock.objects
        .filter(company=company, date__range=(week_start, week_end))
        .aggregate(total=Sum('hours'))['total'] or Decimal('0')
    )

    pending_tasks = WorkTask.objects.filter(
        mission__company=company,
        status__in=['todo', 'in_progress'],
    ).count()

    open_conflicts = PlanningConflict.objects.filter(
        company=company, resolved=False
    ).count()

    new_requests = CustomerRequest.objects.filter(
        company=company, status='new'
    ).count()

    return {
        'active_missions': active_missions,
        'total_employees': total_employees,
        'hours_this_week': hours_this_week,
        'pending_tasks': pending_tasks,
        'open_conflicts': open_conflicts,
        'new_requests': new_requests,
    }


def build_weekly_grid(company, week_dates):
    blocks = get_time_blocks_for_week(company, week_dates[0])
    employees = get_employee_profiles(company)

    grid = {}
    for emp in employees:
        grid[emp.pk] = {
            'employee': emp,
            'days': {d: [] for d in week_dates},
            'total': Decimal('0'),
        }

    for block in blocks:
        emp_pk = block.employee_id
        if emp_pk in grid and block.date in grid[emp_pk]['days']:
            grid[emp_pk]['days'][block.date].append(block)
            grid[emp_pk]['total'] += block.hours

    return list(grid.values())


# ─── Demandes clients ──────────────────────────────────────────────────────────

def get_customer_requests(company, status=None):
    qs = CustomerRequest.objects.filter(company=company).select_related(
        'customer', 'website', 'assigned_employee__user', 'mission', 'created_task',
    )
    if status:
        qs = qs.filter(status=status)
    return qs.order_by('-created_at')


def get_open_customer_requests(company):
    return CustomerRequest.objects.filter(
        company=company,
    ).exclude(status__in=['completed', 'cancelled']).select_related(
        'customer', 'assigned_employee__user',
    ).order_by('requested_deadline', '-created_at')


def get_employee_constraints(employee):
    return EmployeeAvailabilityConstraint.objects.filter(
        company=employee.company,
        employee=employee,
        is_active=True,
    ).order_by('weekday', 'start_time')


def get_company_constraints(company):
    if not company:
        return EmployeeAvailabilityConstraint.objects.none()
    return (
        EmployeeAvailabilityConstraint.objects
        .filter(company=company, is_active=True)
        .select_related('employee__user')
        .order_by('employee__user__last_name', 'weekday', 'start_time')
    )


def get_plannable_requests(company):
    return CustomerRequest.objects.filter(
        company=company,
        auto_planning_enabled=True,
        is_locked=False,
        created_task__isnull=True,
    ).exclude(status__in=['completed', 'cancelled']).order_by(
        'requested_deadline', '-created_at'
    )
