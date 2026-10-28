from datetime import date, timedelta
from decimal import Decimal
from django.db.models import Sum

from .models import (
    EmployeeProfile, WorkMission, WorkTask, DedicatedTimeBlock, PlanningConflict,
    EmployeeAvailabilityConstraint,
)


def create_mission(company, user, name, code='', description='', status='active',
                   priority='normal', start_date=None, end_date=None,
                   estimated_hours=None, color_code='#0EA5E9'):
    if start_date is None:
        from django.utils import timezone
        start_date = timezone.now().date()
    return WorkMission.objects.create(
        company=company,
        created_by=user,
        name=name,
        code=code,
        description=description,
        status=status,
        priority=priority,
        start_date=start_date,
        end_date=end_date,
        estimated_hours=estimated_hours,
        color_code=color_code,
    )


def update_mission(mission, **kwargs):
    for field, value in kwargs.items():
        setattr(mission, field, value)
    mission.save()
    return mission


def delete_mission(mission):
    mission.delete()


def create_task(mission, name, description='', status='todo', priority='normal',
                estimated_hours=None, estimated_minutes=0, assigned_to=None,
                due_date=None, customer_request=None):
    order = WorkTask.objects.filter(mission=mission).count()
    return WorkTask.objects.create(
        mission=mission,
        customer_request=customer_request,
        name=name,
        description=description,
        status=status,
        priority=priority,
        estimated_hours=estimated_hours,
        estimated_minutes=estimated_minutes or 0,
        assigned_to=assigned_to,
        due_date=due_date,
        order=order,
    )


def update_task(task, **kwargs):
    for field, value in kwargs.items():
        setattr(task, field, value)
    task.save()
    return task


def delete_task(task):
    task.delete()


def create_employee_profile(company, user, role='employee', color_code='#6366F1',
                             default_hours_per_day=Decimal('8.0'),
                             weekly_capacity_hours=Decimal('35.0'),
                             skills=None, notes=''):
    profile, _ = EmployeeProfile.objects.get_or_create(
        company=company,
        user=user,
        defaults={
            'role': role,
            'color_code': color_code,
            'default_hours_per_day': default_hours_per_day,
            'weekly_capacity_hours': weekly_capacity_hours,
            'skills': skills or [],
            'notes': notes,
        },
    )
    return profile


def update_employee_profile(profile, **kwargs):
    for field, value in kwargs.items():
        setattr(profile, field, value)
    profile.save()
    return profile


def create_time_block(company, employee, date_val, hours, mission=None, task=None,
                      note='', created_by=None, is_locked=False):
    block = DedicatedTimeBlock.objects.create(
        company=company,
        employee=employee,
        date=date_val,
        hours=hours,
        mission=mission,
        task=task,
        note=note,
        is_locked=is_locked,
        created_by=created_by,
    )
    _check_and_create_conflict(company, employee, date_val)
    return block


def update_time_block(block, **kwargs):
    for field, value in kwargs.items():
        setattr(block, field, value)
    block.save()
    _check_and_create_conflict(block.company, block.employee, block.date)
    return block


def delete_time_block(block):
    company = block.company
    employee = block.employee
    date_val = block.date
    block.delete()
    _check_and_create_conflict(company, employee, date_val)


def _check_and_create_conflict(company, employee, date_val):
    total = (
        DedicatedTimeBlock.objects
        .filter(company=company, employee=employee, date=date_val)
        .aggregate(total=Sum('hours'))['total'] or Decimal('0')
    )
    max_hours = employee.default_hours_per_day

    if total > max_hours:
        PlanningConflict.objects.update_or_create(
            company=company,
            employee=employee,
            date=date_val,
            defaults={
                'total_hours_planned': total,
                'max_hours': max_hours,
                'resolved': False,
            },
        )
    else:
        PlanningConflict.objects.filter(
            company=company, employee=employee, date=date_val
        ).update(resolved=True)


def resolve_conflict(conflict):
    conflict.resolved = True
    conflict.save(update_fields=['resolved'])


# ─── Contraintes disponibilité salarié ───────────────────────────────────────

def get_normal_daily_hours(employee):
    """Heures productives dans une journée normale (en tenant compte de la pause déj)."""
    start = employee.normal_work_start
    end = employee.normal_work_end
    total_minutes = (end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)
    if employee.lunch_break_start and employee.lunch_break_end:
        lunch_min = (
            (employee.lunch_break_end.hour * 60 + employee.lunch_break_end.minute) -
            (employee.lunch_break_start.hour * 60 + employee.lunch_break_start.minute)
        )
        total_minutes -= max(0, lunch_min)
    return Decimal(str(max(0, total_minutes))) / 60


def _constraint_applies_on_date(constraint, target_date):
    """Retourne True si cette contrainte est active sur target_date."""
    if not constraint.is_active:
        return False
    if constraint.recurrence == 'daily':
        return True
    if constraint.recurrence == 'weekly':
        return constraint.weekday is not None and target_date.weekday() == constraint.weekday
    if constraint.recurrence == 'monthly':
        if constraint.starts_at:
            return target_date.day == constraint.starts_at.day
        return True
    if constraint.recurrence == 'none':
        if constraint.starts_at and constraint.ends_at:
            start_d = constraint.starts_at.date() if hasattr(constraint.starts_at, 'date') else constraint.starts_at
            end_d = constraint.ends_at.date() if hasattr(constraint.ends_at, 'date') else constraint.ends_at
            return start_d <= target_date <= end_d
    return False


def get_blocked_hours_on_date(employee, target_date):
    """Heures bloquées par des contraintes BLOQUANTES sur cette date."""
    constraints = EmployeeAvailabilityConstraint.objects.filter(
        company=employee.company,
        employee=employee,
        is_active=True,
        priority='blocking',
    )
    total = Decimal('0')
    for c in constraints:
        if not _constraint_applies_on_date(c, target_date):
            continue
        if c.start_time and c.end_time:
            mins = (c.end_time.hour * 60 + c.end_time.minute) - (c.start_time.hour * 60 + c.start_time.minute)
            total += Decimal(str(max(0, mins))) / 60
        elif c.starts_at and c.ends_at:
            mins = (c.ends_at - c.starts_at).total_seconds() / 60
            total += Decimal(str(max(0, mins))) / 60
    return total


def get_employee_daily_capacity(employee, target_date):
    """
    Heures planifiables sur cette date compte tenu :
    - des horaires normaux (si refus heures sup)
    - des contraintes bloquantes
    """
    normal_hours = get_normal_daily_hours(employee)
    if employee.accepts_overtime:
        base = employee.default_hours_per_day
    else:
        base = normal_hours
    blocked = get_blocked_hours_on_date(employee, target_date)
    return max(Decimal('0'), base - blocked)


def is_date_blocked_for_employee(employee, target_date):
    """True si le salarié ne peut pas travailler du tout ce jour (contraintes)."""
    return get_employee_daily_capacity(employee, target_date) <= Decimal('0')


def get_employee_week_overtime_hours(employee, week_start):
    """Heures travaillées au-delà des heures normales journalières sur la semaine."""
    week_end = week_start + timedelta(days=6)
    normal_daily = get_normal_daily_hours(employee)
    blocks = DedicatedTimeBlock.objects.filter(
        company=employee.company,
        employee=employee,
        date__range=(week_start, week_end),
    )
    by_date = {}
    for block in blocks:
        by_date.setdefault(block.date, Decimal('0'))
        by_date[block.date] += block.hours
    overtime = Decimal('0')
    for _, total in by_date.items():
        if total > normal_daily:
            overtime += total - normal_daily
    return overtime
