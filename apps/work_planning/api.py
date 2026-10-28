import json
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .models import EmployeeProfile, WorkMission, WorkTask, DedicatedTimeBlock, CustomerRequest, EmployeeAvailabilityConstraint
from .selectors import get_week_dates, build_weekly_grid, get_tasks_for_mission, get_open_customer_requests
from .services import create_time_block, delete_time_block
from .auto_scheduler import auto_schedule_company, rebalance_planning, get_workload_summary


def _company(request):
    return request.current_company


@login_required
@require_http_methods(['GET'])
def api_weekly_data(request):
    company = _company(request)
    ref_str = request.GET.get('date', str(date.today()))
    try:
        ref_date = date.fromisoformat(ref_str)
    except ValueError:
        ref_date = date.today()

    week_dates = get_week_dates(ref_date)
    grid = build_weekly_grid(company, week_dates)

    rows = []
    for row in grid:
        emp = row['employee']
        days_data = {}
        for d, blocks in row['days'].items():
            days_data[str(d)] = [
                {
                    'id': b.pk,
                    'hours': float(b.hours),
                    'mission': b.mission.name if b.mission else None,
                    'mission_id': b.mission_id,
                    'task': b.task.name if b.task else None,
                    'task_id': b.task_id,
                    'note': b.note,
                    'is_locked': b.is_locked,
                }
                for b in blocks
            ]
        rows.append({
            'employee_id': emp.pk,
            'name': emp.display_name,
            'color': emp.color_code,
            'max_hours': float(emp.default_hours_per_day),
            'skills': emp.skills or [],
            'total': float(row['total']),
            'days': days_data,
        })

    return JsonResponse({
        'week_start': str(week_dates[0]),
        'week_end': str(week_dates[6]),
        'dates': [str(d) for d in week_dates],
        'rows': rows,
    })


@login_required
@require_http_methods(['GET'])
def api_missions(request):
    company = _company(request)
    missions = WorkMission.objects.filter(company=company, status='active').values(
        'id', 'name', 'code', 'color_code'
    )
    return JsonResponse({'missions': list(missions)})


@login_required
@require_http_methods(['GET'])
def api_tasks(request):
    company = _company(request)
    mission_id = request.GET.get('mission')
    if not mission_id:
        return JsonResponse({'tasks': []})
    try:
        mission = WorkMission.objects.get(pk=mission_id, company=company)
    except WorkMission.DoesNotExist:
        return JsonResponse({'error': 'Mission introuvable'}, status=404)
    tasks = get_tasks_for_mission(mission).values('id', 'name', 'status', 'estimated_hours', 'estimated_minutes')
    return JsonResponse({'tasks': list(tasks)})


@login_required
@require_http_methods(['POST'])
def api_create_block(request):
    company = _company(request)
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'error': 'JSON invalide'}, status=400)

    employee_id = data.get('employee_id')
    mission_id = data.get('mission_id')
    task_id = data.get('task_id')
    date_str = data.get('date')
    hours = data.get('hours')
    note = data.get('note', '')
    is_locked = data.get('is_locked', False)

    if not all([employee_id, date_str, hours]):
        return JsonResponse({'error': 'Champs requis : employee_id, date, hours'}, status=400)

    try:
        employee = EmployeeProfile.objects.get(pk=employee_id, company=company)
        date_val = date.fromisoformat(date_str)
        hours_dec = Decimal(str(hours))
    except (EmployeeProfile.DoesNotExist, ValueError) as e:
        return JsonResponse({'error': str(e)}, status=400)

    mission = None
    task = None
    if mission_id:
        try:
            mission = WorkMission.objects.get(pk=mission_id, company=company)
        except WorkMission.DoesNotExist:
            pass
    if task_id and mission:
        try:
            task = WorkTask.objects.get(pk=task_id, mission=mission)
        except WorkTask.DoesNotExist:
            pass

    block = create_time_block(
        company=company,
        employee=employee,
        date_val=date_val,
        hours=hours_dec,
        mission=mission,
        task=task,
        note=note,
        created_by=request.user,
        is_locked=is_locked,
    )

    return JsonResponse({'id': block.pk, 'hours': float(block.hours), 'date': str(block.date)}, status=201)


@login_required
@require_http_methods(['DELETE'])
def api_delete_block(request, pk):
    company = _company(request)
    try:
        block = DedicatedTimeBlock.objects.get(pk=pk, company=company)
    except DedicatedTimeBlock.DoesNotExist:
        return JsonResponse({'error': 'Bloc introuvable'}, status=404)
    if block.is_locked:
        return JsonResponse({'error': 'Ce créneau est verrouillé'}, status=403)
    delete_time_block(block)
    return JsonResponse({'deleted': True})


@login_required
@require_http_methods(['GET'])
def api_customer_requests(request):
    company = _company(request)
    requests = get_open_customer_requests(company)[:50]
    data = []
    for r in requests:
        data.append({
            'id': r.pk,
            'title': r.title,
            'customer': r.customer.name if r.customer else '',
            'urgency': r.urgency,
            'urgency_display': r.get_urgency_display(),
            'status': r.status,
            'status_display': r.get_status_display(),
            'estimated_minutes': r.estimated_minutes,
            'requested_deadline': str(r.requested_deadline) if r.requested_deadline else None,
            'required_skill': r.required_skill,
            'assigned_employee': r.assigned_employee.display_name if r.assigned_employee else '',
            'has_task': bool(r.created_task_id),
        })
    return JsonResponse({'customer_requests': data})


@login_required
@require_http_methods(['GET'])
def api_employee_constraints(request):
    company = _company(request)
    employee_id = request.GET.get('employee_id')
    qs = EmployeeAvailabilityConstraint.objects.filter(
        company=company, is_active=True,
    ).select_related('employee__user')
    if employee_id:
        qs = qs.filter(employee_id=employee_id)
    qs = qs[:100]
    return JsonResponse({
        'constraints': [
            {
                'id': c.pk,
                'employee_id': c.employee_id,
                'employee': c.employee.display_name,
                'title': c.title,
                'type': c.constraint_type,
                'priority': c.priority,
                'recurrence': c.recurrence,
                'weekday': c.weekday,
                'start_time': str(c.start_time) if c.start_time else None,
                'end_time': str(c.end_time) if c.end_time else None,
                'starts_at': c.starts_at.isoformat() if c.starts_at else None,
                'ends_at': c.ends_at.isoformat() if c.ends_at else None,
                'can_be_overridden_by_manager': c.can_be_overridden_by_manager,
            }
            for c in qs
        ]
    })


@login_required
@require_http_methods(['POST'])
def api_auto_schedule(request):
    company = _company(request)
    try:
        body = json.loads(request.body) if request.body else {}
    except Exception:
        body = {}

    action = body.get('action', 'schedule')

    if action == 'rebalance':
        result = rebalance_planning(company)
    else:
        result = auto_schedule_company(company)

    return JsonResponse({'status': 'ok', 'result': result})
