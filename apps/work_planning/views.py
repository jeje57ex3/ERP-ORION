from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404

from apps.private_saas.decorators import require_company_module
from .models import (
    EmployeeProfile, WorkMission, WorkTask, DedicatedTimeBlock,
    PlanningConflict, CustomerRequest, EmployeeAvailabilityConstraint,
)
from .forms import (
    EmployeeProfileForm, WorkMissionForm, WorkTaskForm,
    DedicatedTimeBlockForm, CustomerRequestForm, EmployeeAvailabilityConstraintForm,
)
from .selectors import (
    get_employee_profiles, get_all_employee_profiles, get_missions, get_active_missions,
    get_tasks_for_mission, get_week_dates, build_weekly_grid, get_dashboard_stats,
    get_customer_requests, get_open_customer_requests,
    get_employee_constraints, get_company_constraints,
)
from .services import (
    create_mission, delete_mission,
    create_task, delete_task,
    create_time_block, delete_time_block,
    resolve_conflict,
)
from .auto_scheduler import (
    auto_schedule_company, rebalance_planning, get_workload_summary,
    convert_request_to_task,
)


def _company(request):
    return request.current_company


# ─── Dashboard ────────────────────────────────────────────────────────────────

@login_required
@require_company_module('work_planning')
def dashboard(request):
    company = _company(request)
    stats = get_dashboard_stats(company)

    today = date.today()
    week_dates = get_week_dates(today)
    grid = build_weekly_grid(company, week_dates)

    recent_missions = get_active_missions(company)[:5]
    open_conflicts = PlanningConflict.objects.filter(company=company, resolved=False).select_related('employee__user')[:5]
    new_requests = CustomerRequest.objects.filter(company=company, status='new').order_by('-created_at')[:5]

    return render(request, 'work_planning/dashboard.html', {
        'page_title': 'Planning & Temps dédiés',
        'stats': stats,
        'week_dates': week_dates,
        'grid': grid,
        'today': today,
        'recent_missions': recent_missions,
        'open_conflicts': open_conflicts,
        'new_requests': new_requests,
    })


# ─── Missions ─────────────────────────────────────────────────────────────────

@login_required
@require_company_module('work_planning')
def mission_list(request):
    company = _company(request)
    status_filter = request.GET.get('status', '')
    missions = get_missions(company, status=status_filter if status_filter else None)

    status_counts = {}
    for s, _ in WorkMission.STATUS_CHOICES:
        status_counts[s] = WorkMission.objects.filter(company=company, status=s).count()

    return render(request, 'work_planning/mission_list.html', {
        'page_title': 'Missions',
        'missions': missions,
        'status_filter': status_filter,
        'status_counts': status_counts,
        'total': missions.count(),
    })


@login_required
@require_company_module('work_planning')
def mission_create(request):
    company = _company(request)
    if request.method == 'POST':
        form = WorkMissionForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            create_mission(
                company=company,
                user=request.user,
                name=data['name'],
                code=data.get('code', ''),
                description=data.get('description', ''),
                status=data['status'],
                priority=data['priority'],
                start_date=data['start_date'],
                end_date=data.get('end_date'),
                estimated_hours=data.get('estimated_hours'),
                color_code=data.get('color_code', '#0EA5E9'),
            )
            messages.success(request, f'Mission « {data["name"]} » créée.')
            return redirect('work_planning:mission_list')
    else:
        form = WorkMissionForm()

    return render(request, 'work_planning/mission_form.html', {
        'page_title': 'Nouvelle mission',
        'form': form,
        'action': 'create',
    })


@login_required
@require_company_module('work_planning')
def mission_edit(request, pk):
    company = _company(request)
    mission = get_object_or_404(WorkMission, pk=pk, company=company)

    if request.method == 'POST':
        form = WorkMissionForm(request.POST, instance=mission)
        if form.is_valid():
            form.save()
            messages.success(request, f'Mission « {mission.name} » mise à jour.')
            return redirect('work_planning:mission_detail', pk=mission.pk)
    else:
        form = WorkMissionForm(instance=mission)

    return render(request, 'work_planning/mission_form.html', {
        'page_title': f'Modifier — {mission.name}',
        'form': form,
        'mission': mission,
        'action': 'edit',
    })


@login_required
@require_company_module('work_planning')
def mission_detail(request, pk):
    company = _company(request)
    mission = get_object_or_404(WorkMission, pk=pk, company=company)
    tasks = get_tasks_for_mission(mission)

    return render(request, 'work_planning/mission_detail.html', {
        'page_title': mission.name,
        'mission': mission,
        'tasks': tasks,
        'tasks_done': tasks.filter(status='done').count(),
        'tasks_total': tasks.count(),
    })


@login_required
@require_company_module('work_planning')
def mission_delete(request, pk):
    company = _company(request)
    mission = get_object_or_404(WorkMission, pk=pk, company=company)

    if request.method == 'POST':
        name = mission.name
        delete_mission(mission)
        messages.success(request, f'Mission « {name} » supprimée.')
        return redirect('work_planning:mission_list')

    return render(request, 'work_planning/mission_confirm_delete.html', {
        'page_title': f'Supprimer — {mission.name}',
        'mission': mission,
    })


# ─── Tâches ───────────────────────────────────────────────────────────────────

@login_required
@require_company_module('work_planning')
def task_create(request, mission_pk):
    company = _company(request)
    mission = get_object_or_404(WorkMission, pk=mission_pk, company=company)

    if request.method == 'POST':
        form = WorkTaskForm(request.POST, company=company)
        if form.is_valid():
            data = form.cleaned_data
            create_task(
                mission=mission,
                name=data['name'],
                description=data.get('description', ''),
                status=data['status'],
                priority=data['priority'],
                estimated_hours=data.get('estimated_hours'),
                estimated_minutes=data.get('estimated_minutes') or 0,
                assigned_to=data.get('assigned_to'),
                due_date=data.get('due_date'),
                customer_request=data.get('customer_request'),
            )
            messages.success(request, f'Tâche « {data["name"]} » ajoutée.')
            return redirect('work_planning:mission_detail', pk=mission.pk)
    else:
        req_pk = request.GET.get('request')
        initial = {}
        if req_pk:
            try:
                req = CustomerRequest.objects.get(pk=req_pk, company=company)
                initial = {
                    'name': req.title,
                    'description': req.description,
                    'priority': {'low': 'low', 'normal': 'normal', 'high': 'high', 'urgent': 'urgent', 'critical': 'urgent'}.get(req.urgency, 'normal'),
                    'estimated_minutes': req.estimated_minutes,
                    'customer_request': req,
                }
            except CustomerRequest.DoesNotExist:
                pass
        form = WorkTaskForm(company=company, initial=initial)

    return render(request, 'work_planning/task_form.html', {
        'page_title': f'Nouvelle tâche — {mission.name}',
        'form': form,
        'mission': mission,
        'action': 'create',
    })


@login_required
@require_company_module('work_planning')
def task_edit(request, pk):
    company = _company(request)
    task = get_object_or_404(WorkTask, pk=pk, mission__company=company)
    mission = task.mission

    if request.method == 'POST':
        form = WorkTaskForm(request.POST, instance=task, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, f'Tâche « {task.name} » mise à jour.')
            return redirect('work_planning:mission_detail', pk=mission.pk)
    else:
        form = WorkTaskForm(instance=task, company=company)

    return render(request, 'work_planning/task_form.html', {
        'page_title': f'Modifier tâche — {task.name}',
        'form': form,
        'task': task,
        'mission': mission,
        'action': 'edit',
    })


@login_required
@require_company_module('work_planning')
def task_delete(request, pk):
    company = _company(request)
    task = get_object_or_404(WorkTask, pk=pk, mission__company=company)
    mission = task.mission

    if request.method == 'POST':
        name = task.name
        delete_task(task)
        messages.success(request, f'Tâche « {name} » supprimée.')
        return redirect('work_planning:mission_detail', pk=mission.pk)

    return render(request, 'work_planning/task_confirm_delete.html', {
        'page_title': f'Supprimer tâche — {task.name}',
        'task': task,
        'mission': mission,
    })


# ─── Employés ─────────────────────────────────────────────────────────────────

@login_required
@require_company_module('work_planning')
def employee_list(request):
    company = _company(request)
    employees = get_all_employee_profiles(company)
    return render(request, 'work_planning/employee_list.html', {
        'page_title': 'Équipe planning',
        'employees': employees,
        'total': employees.count(),
    })


@login_required
@require_company_module('work_planning')
def employee_create(request):
    company = _company(request)
    if request.method == 'POST':
        form = EmployeeProfileForm(request.POST, company=company)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.company = company
            profile.save()
            messages.success(request, f'Profil de {profile.display_name} créé.')
            return redirect('work_planning:employee_list')
    else:
        form = EmployeeProfileForm(company=company)

    return render(request, 'work_planning/employee_form.html', {
        'page_title': 'Ajouter un employé',
        'form': form,
        'action': 'create',
    })


@login_required
@require_company_module('work_planning')
def employee_edit(request, pk):
    company = _company(request)
    profile = get_object_or_404(EmployeeProfile, pk=pk, company=company)

    if request.method == 'POST':
        form = EmployeeProfileForm(request.POST, instance=profile, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, f'Profil de {profile.display_name} mis à jour.')
            return redirect('work_planning:employee_list')
    else:
        form = EmployeeProfileForm(instance=profile, company=company)

    return render(request, 'work_planning/employee_form.html', {
        'page_title': f'Modifier — {profile.display_name}',
        'form': form,
        'profile': profile,
        'action': 'edit',
    })


# ─── Contraintes salarié ─────────────────────────────────────────────────────

@login_required
@require_company_module('work_planning')
def employee_constraints(request, pk):
    company = _company(request)
    profile = get_object_or_404(EmployeeProfile, pk=pk, company=company)
    constraints = profile.availability_constraints.filter(
        company=company,
    ).order_by('priority', 'weekday', 'start_time')
    return render(request, 'work_planning/employee_constraints.html', {
        'page_title': f'Contraintes — {profile.display_name}',
        'profile': profile,
        'constraints': constraints,
    })


@login_required
@require_company_module('work_planning')
def employee_constraint_create(request, pk):
    company = _company(request)
    profile = get_object_or_404(EmployeeProfile, pk=pk, company=company)

    if request.method == 'POST':
        form = EmployeeAvailabilityConstraintForm(request.POST, company=company)
        if form.is_valid():
            constraint = form.save(commit=False)
            constraint.company = company
            constraint.employee = profile
            constraint.created_by = request.user
            constraint.save()
            messages.success(request, f'Contrainte « {constraint.title} » ajoutée.')
            return redirect('work_planning:employee_constraints', pk=profile.pk)
    else:
        form = EmployeeAvailabilityConstraintForm(company=company)
        form.fields['employee'].initial = profile
        form.fields['employee'].widget = form.fields['employee'].hidden_widget()

    return render(request, 'work_planning/employee_constraint_form.html', {
        'page_title': f'Nouvelle contrainte — {profile.display_name}',
        'form': form,
        'profile': profile,
        'action': 'create',
    })


@login_required
@require_company_module('work_planning')
def employee_constraint_edit(request, constraint_pk):
    company = _company(request)
    constraint = get_object_or_404(EmployeeAvailabilityConstraint, pk=constraint_pk, company=company)
    profile = constraint.employee

    if request.method == 'POST':
        form = EmployeeAvailabilityConstraintForm(request.POST, instance=constraint, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, f'Contrainte « {constraint.title} » mise à jour.')
            return redirect('work_planning:employee_constraints', pk=profile.pk)
    else:
        form = EmployeeAvailabilityConstraintForm(instance=constraint, company=company)

    return render(request, 'work_planning/employee_constraint_form.html', {
        'page_title': f'Modifier contrainte — {constraint.title}',
        'form': form,
        'profile': profile,
        'constraint': constraint,
        'action': 'edit',
    })


@login_required
@require_company_module('work_planning')
def employee_constraint_delete(request, constraint_pk):
    company = _company(request)
    constraint = get_object_or_404(EmployeeAvailabilityConstraint, pk=constraint_pk, company=company)
    profile = constraint.employee

    if request.method == 'POST':
        title = constraint.title
        constraint.delete()
        messages.success(request, f'Contrainte « {title} » supprimée.')
        return redirect('work_planning:employee_constraints', pk=profile.pk)

    return render(request, 'work_planning/employee_constraint_confirm_delete.html', {
        'page_title': f'Supprimer contrainte — {constraint.title}',
        'constraint': constraint,
        'profile': profile,
    })


@login_required
@require_company_module('work_planning')
def all_employee_constraints(request):
    company = _company(request)
    constraints = get_company_constraints(company)
    employees = get_all_employee_profiles(company)
    employee_filter = request.GET.get('employee', '')
    if employee_filter:
        constraints = constraints.filter(employee_id=employee_filter)

    return render(request, 'work_planning/all_employee_constraints.html', {
        'page_title': 'Contraintes salariés',
        'constraints': constraints,
        'employees': employees,
        'employee_filter': employee_filter,
    })


# ─── Planning hebdomadaire ────────────────────────────────────────────────────

@login_required
@require_company_module('work_planning')
def weekly_planning(request):
    company = _company(request)
    today = date.today()

    ref_str = request.GET.get('semaine')
    try:
        ref_date = date.fromisoformat(ref_str) if ref_str else today
    except ValueError:
        ref_date = today

    week_dates = get_week_dates(ref_date)
    grid = build_weekly_grid(company, week_dates)
    active_missions = get_active_missions(company)

    prev_week = week_dates[0] - timedelta(days=7)
    next_week = week_dates[0] + timedelta(days=7)

    return render(request, 'work_planning/weekly_planning.html', {
        'page_title': 'Planning de la semaine',
        'week_dates': week_dates,
        'grid': grid,
        'today': today,
        'active_missions': active_missions,
        'prev_week': prev_week,
        'next_week': next_week,
        'ref_date': ref_date,
    })


# ─── Blocs de temps ───────────────────────────────────────────────────────────

@login_required
@require_company_module('work_planning')
def time_block_create(request):
    company = _company(request)

    initial = {}
    date_str = request.GET.get('date')
    employee_pk = request.GET.get('employee')
    if date_str:
        initial['date'] = date_str
    if employee_pk:
        try:
            initial['employee'] = EmployeeProfile.objects.get(pk=employee_pk, company=company)
        except EmployeeProfile.DoesNotExist:
            pass

    if request.method == 'POST':
        form = DedicatedTimeBlockForm(request.POST, company=company)
        if form.is_valid():
            data = form.cleaned_data
            block = create_time_block(
                company=company,
                employee=data['employee'],
                date_val=data['date'],
                hours=data['hours'],
                mission=data.get('mission'),
                task=data.get('task'),
                note=data.get('note', ''),
                created_by=request.user,
                is_locked=data.get('is_locked', False),
            )
            messages.success(request, f'{block.hours}h enregistrée(s) pour {block.employee.display_name}.')
            next_url = request.POST.get('next', '')
            return redirect(next_url or 'work_planning:weekly_planning')
    else:
        form = DedicatedTimeBlockForm(company=company, initial=initial)

    return render(request, 'work_planning/time_block_form.html', {
        'page_title': 'Saisir des heures',
        'form': form,
        'action': 'create',
        'next': request.GET.get('next', ''),
    })


@login_required
@require_company_module('work_planning')
def time_block_edit(request, pk):
    company = _company(request)
    block = get_object_or_404(DedicatedTimeBlock, pk=pk, company=company)

    if request.method == 'POST':
        form = DedicatedTimeBlockForm(request.POST, instance=block, company=company)
        if form.is_valid():
            form.save()
            from .services import _check_and_create_conflict
            _check_and_create_conflict(company, block.employee, block.date)
            messages.success(request, 'Bloc de temps mis à jour.')
            return redirect('work_planning:weekly_planning')
    else:
        form = DedicatedTimeBlockForm(instance=block, company=company)

    return render(request, 'work_planning/time_block_form.html', {
        'page_title': 'Modifier les heures',
        'form': form,
        'block': block,
        'action': 'edit',
    })


@login_required
@require_company_module('work_planning')
def time_block_delete(request, pk):
    company = _company(request)
    block = get_object_or_404(DedicatedTimeBlock, pk=pk, company=company)

    if request.method == 'POST':
        delete_time_block(block)
        messages.success(request, 'Bloc de temps supprimé.')
        return redirect('work_planning:weekly_planning')

    return render(request, 'work_planning/time_block_confirm_delete.html', {
        'page_title': 'Supprimer le bloc de temps',
        'block': block,
    })


# ─── Demandes clients ─────────────────────────────────────────────────────────

@login_required
@require_company_module('work_planning')
def customer_request_list(request):
    company = _company(request)
    status_filter = request.GET.get('status', '')
    urgency_filter = request.GET.get('urgency', '')

    requests = get_customer_requests(company, status=status_filter or None)
    if urgency_filter:
        requests = requests.filter(urgency=urgency_filter)

    status_counts = {}
    for s, _ in CustomerRequest.STATUS_CHOICES:
        status_counts[s] = CustomerRequest.objects.filter(company=company, status=s).count()

    return render(request, 'work_planning/customer_request_list.html', {
        'page_title': 'Demandes clients',
        'requests': requests,
        'status_filter': status_filter,
        'urgency_filter': urgency_filter,
        'status_counts': status_counts,
        'total': requests.count(),
        'urgency_choices': CustomerRequest.URGENCY_CHOICES,
    })


@login_required
@require_company_module('work_planning')
def customer_request_create(request):
    company = _company(request)

    if request.method == 'POST':
        form = CustomerRequestForm(request.POST, company=company)
        if form.is_valid():
            req = form.save(commit=False)
            req.company = company
            req.created_by = request.user
            req.save()
            messages.success(request, f'Demande « {req.title} » créée.')
            return redirect('work_planning:customer_request_detail', pk=req.pk)
    else:
        form = CustomerRequestForm(company=company)

    return render(request, 'work_planning/customer_request_form.html', {
        'page_title': 'Nouvelle demande client',
        'form': form,
        'action': 'create',
    })


@login_required
@require_company_module('work_planning')
def customer_request_edit(request, pk):
    company = _company(request)
    req = get_object_or_404(CustomerRequest, pk=pk, company=company)

    if request.method == 'POST':
        form = CustomerRequestForm(request.POST, instance=req, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, f'Demande « {req.title} » mise à jour.')
            return redirect('work_planning:customer_request_detail', pk=req.pk)
    else:
        form = CustomerRequestForm(instance=req, company=company)

    return render(request, 'work_planning/customer_request_form.html', {
        'page_title': f'Modifier — {req.title}',
        'form': form,
        'request_obj': req,
        'action': 'edit',
    })


@login_required
@require_company_module('work_planning')
def customer_request_detail(request, pk):
    company = _company(request)
    req = get_object_or_404(
        CustomerRequest.objects.select_related(
            'customer', 'website', 'assigned_employee__user', 'mission', 'created_task',
        ),
        pk=pk, company=company,
    )
    tasks = req.tasks.select_related('assigned_to', 'mission').all()

    return render(request, 'work_planning/customer_request_detail.html', {
        'page_title': req.title,
        'req': req,
        'tasks': tasks,
    })


@login_required
@require_company_module('work_planning')
def customer_request_convert(request, pk):
    company = _company(request)
    req = get_object_or_404(CustomerRequest, pk=pk, company=company)

    if request.method == 'POST':
        task = convert_request_to_task(req)
        messages.success(request, f'Demande convertie en tâche « {task.name} ».')
        return redirect('work_planning:mission_detail', pk=task.mission.pk)

    return render(request, 'work_planning/customer_request_convert_confirm.html', {
        'page_title': f'Convertir — {req.title}',
        'req': req,
    })


@login_required
@require_company_module('work_planning')
def customer_request_delete(request, pk):
    company = _company(request)
    req = get_object_or_404(CustomerRequest, pk=pk, company=company)

    if request.method == 'POST':
        title = req.title
        req.delete()
        messages.success(request, f'Demande « {title} » supprimée.')
        return redirect('work_planning:customer_request_list')

    return render(request, 'work_planning/customer_request_confirm_delete.html', {
        'page_title': f'Supprimer — {req.title}',
        'req': req,
    })


# ─── Planification automatique ────────────────────────────────────────────────

@login_required
@require_company_module('work_planning')
def auto_schedule(request):
    company = _company(request)

    if request.method == 'POST':
        action = request.POST.get('action', 'schedule')

        if action == 'rebalance':
            result = rebalance_planning(company)
            messages.success(
                request,
                f'Planning réajusté : {result["deleted_blocks"]} créneaux supprimés, '
                f'{result["scheduled"]} recréés.'
            )
        else:
            result = auto_schedule_company(company)
            messages.success(
                request,
                f'Planification terminée : {result["converted"]} demande(s) convertie(s), '
                f'{result["scheduled"]} créneau(x) créé(s)'
                + (f', {result["failed"]} non planifiable(s).' if result['failed'] else '.')
            )
        return redirect('work_planning:auto_schedule')

    today = date.today()
    week_end = today + timedelta(days=6)

    open_requests = get_open_customer_requests(company)[:20]
    pending_tasks = WorkTask.objects.filter(
        mission__company=company,
        auto_scheduled=False,
        is_locked=False,
    ).exclude(status='done').select_related('mission', 'customer_request')[:20]

    workload = get_workload_summary(company, from_date=today, to_date=week_end)
    open_conflicts = PlanningConflict.objects.filter(company=company, resolved=False).select_related('employee__user')

    return render(request, 'work_planning/auto_schedule.html', {
        'page_title': 'Planification automatique',
        'open_requests': open_requests,
        'pending_tasks': pending_tasks,
        'workload': workload,
        'open_conflicts': open_conflicts,
        'today': today,
    })
