import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt

from .models import PDCACycle, PDCAAction, PDCAKPI
from .selectors import (
    get_cycles_for_company, get_cycle_detail, get_pending_actions_for_user,
    get_dashboard_stats, get_overdue_actions,
)
from .services import (
    create_pdca_cycle, advance_stage, update_plan, update_do,
    update_check, record_act_decision, create_action, complete_action,
    cancel_action, add_kpi, record_kpi_result, activate_cycle,
    cancel_cycle, create_followup_cycle,
)
from .kpis import compute_cycle_success_rate, compute_action_completion_rate
from .permissions import can_view_pdca, can_edit_pdca, can_advance_stage


def _json_body(request):
    try:
        return json.loads(request.body)
    except (json.JSONDecodeError, AttributeError):
        return {}


def _cycle_summary(cycle):
    return {
        'id': cycle.pk,
        'title': cycle.title,
        'stage': cycle.stage,
        'status': cycle.status,
        'category': cycle.category,
        'priority': cycle.priority,
        'progress_percent': cycle.progress_percent,
        'is_late': cycle.is_late,
        'target_date': cycle.target_date.isoformat() if cycle.target_date else None,
        'owner': str(cycle.owner) if cycle.owner else None,
        'created_at': cycle.created_at.isoformat(),
    }


def _cycle_detail(cycle):
    data = _cycle_summary(cycle)
    data.update({
        'problem_statement': cycle.problem_statement,
        'objective': cycle.objective,
        'root_cause': cycle.root_cause,
        'success_criteria': cycle.success_criteria,
        'expected_result': cycle.expected_result,
        'actual_result': cycle.actual_result,
        'brand_key': cycle.brand_key,
        'related_module': cycle.related_module,
        'action_completion_rate': compute_action_completion_rate(cycle),
        'kpi_success_rate': compute_cycle_success_rate(cycle),
        'actions': [
            {
                'id': a.pk, 'title': a.title, 'status': a.status,
                'assigned_to': str(a.assigned_to) if a.assigned_to else None,
                'due_date': a.due_date.isoformat() if a.due_date else None,
            }
            for a in cycle.actions.all()
        ],
        'kpis': [
            {
                'id': k.pk, 'name': k.name, 'unit': k.unit,
                'before_value': str(k.before_value) if k.before_value is not None else None,
                'target_value': str(k.target_value) if k.target_value is not None else None,
                'after_value': str(k.after_value) if k.after_value is not None else None,
                'target_reached': k.target_reached,
            }
            for k in cycle.kpis.all()
        ],
    })
    return data


@login_required
@require_GET
def api_cycles_list(request):
    company = request.current_company
    if not company:
        return JsonResponse({'error': 'Aucune entreprise active.'}, status=400)

    stage = request.GET.get('stage')
    status = request.GET.get('status')
    category = request.GET.get('category')
    priority = request.GET.get('priority')

    cycles = get_cycles_for_company(
        company,
        brand_key=request.GET.get('brand_key'),
        stage=stage, status=status,
        category=category, priority=priority,
    )
    return JsonResponse({'cycles': [_cycle_summary(c) for c in cycles]})


@login_required
def api_cycle_detail(request, pk):
    company = request.current_company
    cycle = get_cycle_detail(pk, company)
    if not cycle:
        return JsonResponse({'error': 'Cycle introuvable.'}, status=404)
    if not can_view_pdca(request.user, cycle):
        return JsonResponse({'error': 'Accès refusé.'}, status=403)
    return JsonResponse({'cycle': _cycle_detail(cycle)})


@login_required
@require_POST
def api_create_cycle(request):
    company = request.current_company
    if not company:
        return JsonResponse({'error': 'Aucune entreprise active.'}, status=400)
    data = _json_body(request)
    try:
        cycle = create_pdca_cycle(
            company=company,
            brand_key=data.get('brand_key', ''),
            title=data['title'],
            problem_statement=data.get('problem_statement', ''),
            objective=data.get('objective', ''),
            category=data.get('category', 'quality'),
            priority=data.get('priority', 'medium'),
            owner=request.user,
            created_by=request.user,
            start_date=data.get('start_date') or None,
            target_date=data.get('target_date') or None,
            root_cause=data.get('root_cause', ''),
            success_criteria=data.get('success_criteria', ''),
            expected_result=data.get('expected_result', ''),
            related_module=data.get('related_module', ''),
        )
    except KeyError as e:
        return JsonResponse({'error': f'Champ requis manquant : {e}'}, status=400)

    return JsonResponse({'cycle': _cycle_summary(cycle)}, status=201)


@login_required
@require_POST
def api_advance_stage(request, pk):
    company = request.current_company
    cycle = PDCACycle.objects.filter(pk=pk, company=company).first()
    if not cycle:
        return JsonResponse({'error': 'Cycle introuvable.'}, status=404)
    if not can_advance_stage(request.user, cycle):
        return JsonResponse({'error': 'Accès refusé.'}, status=403)
    try:
        advance_stage(cycle, user=request.user)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'stage': cycle.stage, 'status': cycle.status})


@login_required
@require_POST
def api_activate_cycle(request, pk):
    company = request.current_company
    cycle = PDCACycle.objects.filter(pk=pk, company=company).first()
    if not cycle:
        return JsonResponse({'error': 'Cycle introuvable.'}, status=404)
    if not can_edit_pdca(request.user, cycle):
        return JsonResponse({'error': 'Accès refusé.'}, status=403)
    try:
        activate_cycle(cycle, user=request.user)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'status': cycle.status})


@login_required
@require_POST
def api_update_phase(request, pk, phase):
    company = request.current_company
    cycle = PDCACycle.objects.filter(pk=pk, company=company).first()
    if not cycle:
        return JsonResponse({'error': 'Cycle introuvable.'}, status=404)
    if not can_edit_pdca(request.user, cycle):
        return JsonResponse({'error': 'Accès refusé.'}, status=403)

    data = _json_body(request)
    PHASE_UPDATERS = {
        'plan': update_plan,
        'do': update_do,
        'check': update_check,
    }
    updater = PHASE_UPDATERS.get(phase)
    if not updater:
        return JsonResponse({'error': 'Phase inconnue.'}, status=400)

    updater(cycle, data, user=request.user)
    return JsonResponse({'ok': True})


@login_required
@require_POST
def api_record_act(request, pk):
    company = request.current_company
    cycle = PDCACycle.objects.filter(pk=pk, company=company).first()
    if not cycle:
        return JsonResponse({'error': 'Cycle introuvable.'}, status=404)
    if not can_edit_pdca(request.user, cycle):
        return JsonResponse({'error': 'Accès refusé.'}, status=403)

    data = _json_body(request)
    decision = data.get('decision')
    if not decision:
        return JsonResponse({'error': 'Décision requise.'}, status=400)

    record_act_decision(
        cycle=cycle,
        decision=decision,
        reason=data.get('reason', ''),
        standardization_notes=data.get('standardization_notes', ''),
        next_steps=data.get('next_steps', ''),
        user=request.user,
    )

    if data.get('create_new_cycle') and decision == 'restart_cycle':
        new_cycle = create_followup_cycle(cycle, request.user)
        return JsonResponse({'ok': True, 'new_cycle_id': new_cycle.pk})

    return JsonResponse({'ok': True})


@login_required
@require_POST
def api_create_action(request, pk):
    company = request.current_company
    cycle = PDCACycle.objects.filter(pk=pk, company=company).first()
    if not cycle:
        return JsonResponse({'error': 'Cycle introuvable.'}, status=404)
    if not can_edit_pdca(request.user, cycle):
        return JsonResponse({'error': 'Accès refusé.'}, status=403)

    data = _json_body(request)
    title = data.get('title', '').strip()
    if not title:
        return JsonResponse({'error': 'Le titre est requis.'}, status=400)

    action = create_action(
        cycle=cycle,
        title=title,
        description=data.get('description', ''),
        due_date=data.get('due_date') or None,
        order=data.get('order', 100),
        user=request.user,
    )
    return JsonResponse({'action': {'id': action.pk, 'title': action.title, 'status': action.status}}, status=201)


@login_required
@require_POST
def api_complete_action(request, action_pk):
    company = request.current_company
    action = PDCAAction.objects.filter(pk=action_pk, cycle__company=company).first()
    if not action:
        return JsonResponse({'error': 'Action introuvable.'}, status=404)

    data = _json_body(request)
    complete_action(action, evidence=data.get('evidence', ''), user=request.user)
    return JsonResponse({'ok': True, 'status': action.status})


@login_required
@require_POST
def api_record_kpi_result(request, kpi_pk):
    company = request.current_company
    kpi = PDCAKPI.objects.filter(pk=kpi_pk, cycle__company=company).first()
    if not kpi:
        return JsonResponse({'error': 'KPI introuvable.'}, status=404)

    data = _json_body(request)
    try:
        after_value = data['after_value']
    except KeyError:
        return JsonResponse({'error': 'after_value requis.'}, status=400)

    record_kpi_result(kpi, after_value, user=request.user)
    return JsonResponse({'ok': True, 'target_reached': kpi.target_reached})


@login_required
@require_GET
def api_dashboard_stats(request):
    company = request.current_company
    if not company:
        return JsonResponse({'error': 'Aucune entreprise active.'}, status=400)
    stats = get_dashboard_stats(company)
    return JsonResponse({'stats': stats})


@login_required
@require_GET
def api_my_actions(request):
    company = request.current_company
    actions = get_pending_actions_for_user(request.user, company)
    return JsonResponse({'actions': [
        {
            'id': a.pk,
            'title': a.title,
            'status': a.status,
            'cycle_id': a.cycle_id,
            'cycle_title': a.cycle.title,
            'due_date': a.due_date.isoformat() if a.due_date else None,
        }
        for a in actions
    ]})
