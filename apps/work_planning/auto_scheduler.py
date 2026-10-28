"""
apps/work_planning/auto_scheduler.py

Moteur de planification automatique Orion ERP.

Fonctionnement :
- Travaille en créneaux journaliers (date + heures), compatible avec DedicatedTimeBlock.
- Trie les tâches par score de priorité (urgence + deadline + priorité).
- Choisit le salarié le plus adapté selon compétences et charge de travail.
- Ne déplace pas les créneaux verrouillés (is_locked=True).
- Horizon de planification : 30 jours ouvrables.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import (
    DedicatedTimeBlock, EmployeeProfile, PlanningConflict,
    WorkTask, CustomerRequest,
)

HORIZON_DAYS = 30
MIN_BLOCK_HOURS = Decimal('0.5')

PRIORITY_WEIGHT = {
    'low': 10,
    'normal': 30,
    'high': 60,
    'urgent': 100,
}

URGENCY_WEIGHT = {
    'low': 10,
    'normal': 30,
    'high': 60,
    'urgent': 90,
    'critical': 120,
}


# ─── Scoring ──────────────────────────────────────────────────────────────────

def task_priority_score(task):
    score = PRIORITY_WEIGHT.get(task.priority, 30)

    if task.due_date:
        today = date.today()
        days_left = (task.due_date - today).days
        if days_left <= 0:
            score += 150
        elif days_left <= 1:
            score += 100
        elif days_left <= 3:
            score += 70
        elif days_left <= 7:
            score += 40
        elif days_left <= 14:
            score += 20

    req = task.customer_request
    if req:
        score += URGENCY_WEIGHT.get(req.urgency, 30)
        if req.requested_deadline:
            days_left = (req.requested_deadline - date.today()).days
            if days_left <= 0:
                score += 80
            elif days_left <= 1:
                score += 50

    return score


# ─── Capacité quotidienne ──────────────────────────────────────────────────────

def get_employee_used_hours_on_date(employee, target_date):
    result = DedicatedTimeBlock.objects.filter(
        company=employee.company,
        employee=employee,
        date=target_date,
    ).aggregate(total=Sum('hours'))
    return result['total'] or Decimal('0')


def get_employee_available_hours_on_date(employee, target_date):
    """Heures disponibles sur une date, en tenant compte des contraintes et heures sup."""
    from .services import get_employee_daily_capacity
    used = get_employee_used_hours_on_date(employee, target_date)
    max_capacity = get_employee_daily_capacity(employee, target_date)
    return max(Decimal('0'), max_capacity - used)


def is_working_day(d):
    return d.weekday() < 5  # lundi–vendredi


# ─── Matching salarié ─────────────────────────────────────────────────────────

def employee_matches_skill(employee, task):
    req = task.customer_request
    if not req or not req.required_skill:
        return True
    return employee.has_skill(req.required_skill.strip().lower())


def rank_employees_for_task(employees, task, candidate_date):
    from .services import is_date_blocked_for_employee, get_normal_daily_hours, get_employee_daily_capacity
    scored = []
    for emp in employees:
        # Exclure les salariés bloqués par contrainte ce jour
        if is_date_blocked_for_employee(emp, candidate_date):
            continue

        score = 0
        if employee_matches_skill(emp, task):
            score += 80
        else:
            score -= 80

        available = get_employee_available_hours_on_date(emp, candidate_date)
        capacity = emp.weekly_capacity_hours or Decimal('35')
        weekly_used = DedicatedTimeBlock.objects.filter(
            company=emp.company,
            employee=emp,
            date__week=candidate_date.isocalendar()[1],
            date__year=candidate_date.year,
        ).aggregate(total=Sum('hours'))['total'] or Decimal('0')

        load_pct = float(weekly_used / capacity) if capacity > 0 else 1.0
        score += max(0, 80 - int(load_pct * 100))

        if task.assigned_to and task.assigned_to_id == emp.user_id:
            score += 40

        # Bonus : salarié planifiable dans ses horaires normaux (priorité aux heures normales)
        normal_daily = get_normal_daily_hours(emp)
        daily_cap = get_employee_daily_capacity(emp, candidate_date)
        if daily_cap <= normal_daily:
            score += 30
        else:
            score -= 10  # créneau qui déborde sur heures sup

        scored.append((score, emp, available))

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored


def find_slot_for_task(company, task, active_employees, from_date=None):
    if from_date is None:
        from_date = date.today()

    needed_hours = task.get_effective_hours()
    if needed_hours < MIN_BLOCK_HOURS:
        needed_hours = MIN_BLOCK_HOURS

    for day_offset in range(HORIZON_DAYS):
        candidate_date = from_date + timedelta(days=day_offset)
        if not is_working_day(candidate_date):
            continue

        ranked = rank_employees_for_task(active_employees, task, candidate_date)
        for score, emp, available in ranked:
            if available >= needed_hours:
                return emp, candidate_date, needed_hours
            elif available >= MIN_BLOCK_HOURS:
                return emp, candidate_date, available

    return None, None, None


# ─── Planifier une tâche ──────────────────────────────────────────────────────

@transaction.atomic
def schedule_single_task(company, task, active_employees, from_date=None):
    if task.is_locked:
        return None

    emp, target_date, hours = find_slot_for_task(company, task, active_employees, from_date)
    if emp is None:
        return None

    block = DedicatedTimeBlock.objects.create(
        company=company,
        employee=emp,
        task=task,
        mission=task.mission,
        date=target_date,
        hours=hours,
        note=f'Auto-planifié — {task.name}',
        is_locked=False,
        created_by=None,
    )

    update_fields = ['auto_scheduled', 'scheduler_score', 'updated_at']
    task.auto_scheduled = True
    task.scheduler_score = Decimal(str(task_priority_score(task)))

    if not task.assigned_to:
        task.assigned_to = emp.user
        update_fields.append('assigned_to')

    task.save(update_fields=update_fields)

    if task.customer_request and task.customer_request.status in ('new', 'qualified'):
        task.customer_request.status = 'planned'
        task.customer_request.assigned_employee = emp
        task.customer_request.save(update_fields=['status', 'assigned_employee', 'updated_at'])

    _refresh_conflict(company, emp, target_date)
    return block


# ─── Convertir demande → tâche ────────────────────────────────────────────────

URGENCY_TO_PRIORITY = {
    'low': 'low',
    'normal': 'normal',
    'high': 'high',
    'urgent': 'urgent',
    'critical': 'urgent',
}


def convert_request_to_task(customer_request):
    if customer_request.created_task_id:
        return customer_request.created_task

    mission = customer_request.mission
    if mission is None:
        from .models import WorkMission
        mission, _ = WorkMission.objects.get_or_create(
            company=customer_request.company,
            name='Demandes clients',
            defaults={
                'status': 'active',
                'priority': 'normal',
                'color_code': '#F59E0B',
                'created_by': customer_request.created_by,
            },
        )

    task = WorkTask.objects.create(
        mission=mission,
        customer_request=customer_request,
        name=customer_request.title,
        description=customer_request.description,
        status='todo',
        priority=URGENCY_TO_PRIORITY.get(customer_request.urgency, 'normal'),
        estimated_minutes=customer_request.estimated_minutes,
        estimated_hours=Decimal(customer_request.estimated_minutes) / 60,
        assigned_to=(
            customer_request.assigned_employee.user
            if customer_request.assigned_employee else None
        ),
        due_date=customer_request.requested_deadline,
        created_by=customer_request.created_by if hasattr(WorkTask, 'created_by') else None,
    )

    customer_request.created_task = task
    customer_request.status = 'qualified'
    customer_request.save(update_fields=['created_task', 'status', 'updated_at'])
    return task


# ─── Planification automatique complète ──────────────────────────────────────

@transaction.atomic
def auto_schedule_company(company, from_date=None):
    """
    1. Convertit les demandes planifiables sans tâche en tâches.
    2. Planifie toutes les tâches non planifiées par ordre de priorité.
    Retourne un dict de stats.
    """
    if from_date is None:
        from_date = date.today()

    converted = 0
    plannable_requests = CustomerRequest.objects.filter(
        company=company,
        auto_planning_enabled=True,
        is_locked=False,
    ).exclude(status__in=['completed', 'cancelled'])

    for req in plannable_requests:
        if not req.created_task_id:
            convert_request_to_task(req)
            converted += 1

    active_employees = list(
        EmployeeProfile.objects.filter(company=company, is_active=True)
    )
    if not active_employees:
        return {'converted': converted, 'scheduled': 0, 'failed': 0}

    tasks = list(
        WorkTask.objects.filter(
            mission__company=company,
            auto_scheduled=False,
            is_locked=False,
        ).exclude(status__in=['done']).select_related(
            'mission', 'customer_request', 'assigned_to'
        )
    )

    tasks.sort(key=task_priority_score, reverse=True)

    scheduled = 0
    failed = 0
    for task in tasks:
        block = schedule_single_task(company, task, active_employees, from_date)
        if block:
            scheduled += 1
        else:
            failed += 1

    return {'converted': converted, 'scheduled': scheduled, 'failed': failed}


@transaction.atomic
def rebalance_planning(company, from_date=None):
    """
    Supprime tous les créneaux automatiques non verrouillés futurs,
    remet les tâches à 'todo' et relance la planification.
    """
    if from_date is None:
        from_date = date.today()

    deleted = DedicatedTimeBlock.objects.filter(
        company=company,
        is_locked=False,
        date__gte=from_date,
        task__isnull=False,
    ).delete()[0]

    WorkTask.objects.filter(
        mission__company=company,
        auto_scheduled=True,
        is_locked=False,
    ).exclude(status__in=['done']).update(
        auto_scheduled=False,
        scheduler_score=Decimal('0'),
    )

    result = auto_schedule_company(company, from_date)
    result['deleted_blocks'] = deleted
    return result


# ─── Charge de travail ────────────────────────────────────────────────────────

def get_workload_summary(company, from_date=None, to_date=None):
    if from_date is None:
        from_date = date.today()
    if to_date is None:
        to_date = from_date + timedelta(days=6)

    employees = EmployeeProfile.objects.filter(company=company, is_active=True).select_related('user')
    result = []
    for emp in employees:
        used = DedicatedTimeBlock.objects.filter(
            company=company, employee=emp,
            date__range=(from_date, to_date),
        ).aggregate(total=Sum('hours'))['total'] or Decimal('0')
        capacity = emp.weekly_capacity_hours or Decimal('35')
        load_pct = round(float(used / capacity) * 100) if capacity > 0 else 0
        result.append({
            'employee': emp,
            'total_hours': used,
            'capacity': capacity,
            'load_percent': min(load_pct, 999),
            'is_overloaded': used > capacity,
        })
    return result


def _refresh_conflict(company, employee, target_date):
    from .services import _check_and_create_conflict
    _check_and_create_conflict(company, employee, target_date)
