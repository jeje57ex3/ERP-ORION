from django.utils import timezone

from .models import (
    PDCACycle, PDCAPlan, PDCADo, PDCACheck, PDCAAct,
    PDCAAction, PDCAKPI, PDCAStandard, PDCAEventLog, PDCATemplate,
)


# ─── Event logging ────────────────────────────────────────────────────────────

def log_event(cycle, event_type, title, description='', payload=None, user=None):
    PDCAEventLog.objects.create(
        cycle=cycle,
        event_type=event_type,
        title=title,
        description=description,
        payload=payload or {},
        created_by=user,
    )


# ─── Cycle lifecycle ──────────────────────────────────────────────────────────

def create_pdca_cycle(
    *,
    company,
    brand_key='',
    title,
    problem_statement,
    objective,
    category='quality',
    priority='medium',
    owner,
    created_by,
    start_date=None,
    target_date=None,
    root_cause='',
    success_criteria='',
    expected_result='',
    related_module='',
    parent_cycle=None,
    template=None,
):
    cycle = PDCACycle.objects.create(
        company=company,
        brand_key=brand_key,
        title=title,
        problem_statement=problem_statement,
        objective=objective,
        category=category,
        priority=priority,
        stage='plan',
        status='draft',
        owner=owner,
        created_by=created_by,
        start_date=start_date,
        target_date=target_date,
        root_cause=root_cause,
        success_criteria=success_criteria,
        expected_result=expected_result,
        related_module=related_module,
        parent_cycle=parent_cycle,
    )

    PDCAPlan.objects.create(cycle=cycle)

    if template:
        _apply_template(cycle, template)

    log_event(cycle, 'cycle_created', f'Cycle créé : {title}', user=created_by)
    return cycle


def _apply_template(cycle, template: PDCATemplate):
    plan = cycle.plan
    if template.default_problem_statement and not cycle.problem_statement:
        cycle.problem_statement = template.default_problem_statement
        cycle.save(update_fields=['problem_statement'])
    if template.default_objective and not cycle.objective:
        cycle.objective = template.default_objective
        cycle.save(update_fields=['objective'])
    if template.default_success_criteria and not cycle.success_criteria:
        cycle.success_criteria = template.default_success_criteria
        cycle.save(update_fields=['success_criteria'])
    plan.planned_actions_summary = ''
    plan.save()

    for i, action_data in enumerate(template.default_actions):
        PDCAAction.objects.create(
            cycle=cycle,
            title=action_data.get('title', ''),
            description=action_data.get('description', ''),
            order=i * 10,
        )

    for kpi_data in template.default_kpis:
        PDCAKPI.objects.create(
            cycle=cycle,
            name=kpi_data.get('name', ''),
            unit=kpi_data.get('unit', ''),
            description=kpi_data.get('description', ''),
        )


def activate_cycle(cycle, user=None):
    if cycle.status not in ('draft',):
        raise ValueError('Seul un cycle brouillon peut être activé.')
    cycle.status = 'active'
    if not cycle.start_date:
        cycle.start_date = timezone.now().date()
    cycle.save(update_fields=['status', 'start_date'])
    log_event(cycle, 'cycle_activated', 'Cycle activé', user=user)
    return cycle


def pause_cycle(cycle, reason='', user=None):
    if cycle.status != 'active':
        raise ValueError('Seul un cycle actif peut être mis en pause.')
    cycle.status = 'paused'
    cycle.save(update_fields=['status'])
    log_event(cycle, 'cycle_paused', 'Cycle mis en pause', description=reason, user=user)
    return cycle


def resume_cycle(cycle, user=None):
    if cycle.status != 'paused':
        raise ValueError('Seul un cycle en pause peut être relancé.')
    cycle.status = 'active'
    cycle.save(update_fields=['status'])
    log_event(cycle, 'cycle_resumed', 'Cycle relancé', user=user)
    return cycle


def cancel_cycle(cycle, reason='', user=None):
    cycle.status = 'cancelled'
    cycle.save(update_fields=['status'])
    log_event(cycle, 'cycle_cancelled', 'Cycle annulé', description=reason, user=user)
    return cycle


# ─── Stage transitions ────────────────────────────────────────────────────────

STAGE_ORDER = ['plan', 'do', 'check', 'act', 'closed']

STAGE_OBJECT_CREATORS = {
    'do': lambda cycle: PDCADo.objects.get_or_create(cycle=cycle),
    'check': lambda cycle: PDCACheck.objects.get_or_create(cycle=cycle),
    'act': lambda cycle: PDCAAct.objects.get_or_create(cycle=cycle),
}


def advance_stage(cycle, user=None):
    if cycle.status not in ('active',):
        raise ValueError('Le cycle doit être actif pour avancer.')
    current_idx = STAGE_ORDER.index(cycle.stage)
    if current_idx >= len(STAGE_ORDER) - 1:
        raise ValueError('Le cycle est déjà à l\'étape finale.')

    next_stage = STAGE_ORDER[current_idx + 1]
    old_stage = cycle.stage
    cycle.stage = next_stage

    if next_stage == 'closed':
        cycle.status = 'completed'
        cycle.completed_at = timezone.now()
        cycle.save(update_fields=['stage', 'status', 'completed_at'])
    else:
        cycle.save(update_fields=['stage'])
        creator = STAGE_OBJECT_CREATORS.get(next_stage)
        if creator:
            creator(cycle)

    log_event(
        cycle, 'stage_advanced',
        f'Étape : {old_stage} → {next_stage}',
        payload={'from': old_stage, 'to': next_stage},
        user=user,
    )
    return cycle


# ─── Plan phase ───────────────────────────────────────────────────────────────

def update_plan(cycle, data: dict, user=None):
    plan, _ = PDCAPlan.objects.get_or_create(cycle=cycle)
    allowed = [
        'current_situation', 'analysis', 'root_causes', 'risks', 'assumptions',
        'planned_actions_summary',
        'baseline_metric_name', 'baseline_metric_value',
        'target_metric_name', 'target_metric_value',
    ]
    for field in allowed:
        if field in data:
            setattr(plan, field, data[field])
    plan.save()
    log_event(cycle, 'plan_updated', 'Phase PLAN mise à jour', user=user)
    return plan


def validate_plan(cycle, user):
    plan, _ = PDCAPlan.objects.get_or_create(cycle=cycle)
    plan.validated_by = user
    plan.validated_at = timezone.now()
    plan.save(update_fields=['validated_by', 'validated_at'])
    log_event(cycle, 'plan_validated', 'Plan validé', user=user)
    return plan


# ─── Do phase ─────────────────────────────────────────────────────────────────

def update_do(cycle, data: dict, user=None):
    do_obj, _ = PDCADo.objects.get_or_create(cycle=cycle)
    if not do_obj.started_at:
        do_obj.started_at = timezone.now()
    allowed = ['execution_summary', 'difficulties', 'deviations_from_plan']
    for field in allowed:
        if field in data:
            setattr(do_obj, field, data[field])
    do_obj.save()
    log_event(cycle, 'do_updated', 'Phase FAIRE mise à jour', user=user)
    return do_obj


def complete_do(cycle, user=None):
    do_obj, _ = PDCADo.objects.get_or_create(cycle=cycle)
    do_obj.finished_at = timezone.now()
    do_obj.save(update_fields=['finished_at', 'updated_at'])
    log_event(cycle, 'do_completed', 'Phase FAIRE terminée', user=user)
    return do_obj


# ─── Check phase ──────────────────────────────────────────────────────────────

def update_check(cycle, data: dict, user=None):
    check_obj, _ = PDCACheck.objects.get_or_create(cycle=cycle)  # related_name='pdca_check'
    allowed = [
        'measured_result', 'data_sources', 'result_status',
        'measured_metric_name', 'measured_metric_value',
        'gap_analysis', 'lessons_learned',
    ]
    for field in allowed:
        if field in data:
            setattr(check_obj, field, data[field])
    check_obj.save()
    log_event(cycle, 'check_updated', 'Phase VÉRIFIER mise à jour', user=user)
    return check_obj


def finalize_check(cycle, user):
    check_obj, _ = PDCACheck.objects.get_or_create(cycle=cycle)  # related_name='pdca_check'
    check_obj.checked_by = user
    check_obj.checked_at = timezone.now()
    check_obj.save(update_fields=['checked_by', 'checked_at', 'updated_at'])
    log_event(cycle, 'check_finalized', 'Vérification finalisée', user=user)
    return check_obj


# ─── Act phase ────────────────────────────────────────────────────────────────

def record_act_decision(cycle, decision, reason='', standardization_notes='', next_steps='', user=None):
    act_obj, _ = PDCAAct.objects.get_or_create(cycle=cycle)
    act_obj.decision = decision
    act_obj.decision_reason = reason
    act_obj.standardization_notes = standardization_notes
    act_obj.next_steps = next_steps
    act_obj.decided_by = user
    act_obj.decided_at = timezone.now()
    act_obj.save()
    log_event(
        cycle, 'act_decision',
        f'Décision ACT : {decision}',
        description=reason,
        payload={'decision': decision},
        user=user,
    )

    if decision == 'standardize':
        _create_standard_from_cycle(cycle, standardization_notes, user)

    return act_obj


def _create_standard_from_cycle(cycle, notes, user):
    PDCAStandard.objects.create(
        company=cycle.company,
        brand_key=cycle.brand_key,
        cycle=cycle,
        title=f'Standard issu de : {cycle.title}',
        description=notes or cycle.objective,
        module=cycle.related_module,
        created_by=user,
    )
    log_event(cycle, 'standard_created', 'Standard créé depuis ce cycle', user=user)


# ─── Actions CRUD ─────────────────────────────────────────────────────────────

def create_action(cycle, title, description='', assigned_to=None, due_date=None, order=100, user=None):
    action = PDCAAction.objects.create(
        cycle=cycle,
        title=title,
        description=description,
        assigned_to=assigned_to,
        due_date=due_date,
        order=order,
        created_by=user,
    )
    log_event(cycle, 'action_created', f'Action créée : {title}', user=user)
    return action


def complete_action(action, evidence='', user=None):
    action.status = 'done'
    action.evidence = evidence
    action.completed_at = timezone.now()
    action.save(update_fields=['status', 'evidence', 'completed_at', 'updated_at'])
    log_event(action.cycle, 'action_completed', f'Action terminée : {action.title}', user=user)
    return action


def cancel_action(action, user=None):
    action.status = 'cancelled'
    action.save(update_fields=['status', 'updated_at'])
    log_event(action.cycle, 'action_cancelled', f'Action annulée : {action.title}', user=user)
    return action


# ─── KPI recording ────────────────────────────────────────────────────────────

def add_kpi(cycle, name, unit='', description='', before_value=None, target_value=None):
    return PDCAKPI.objects.create(
        cycle=cycle,
        name=name,
        unit=unit,
        description=description,
        before_value=before_value,
        target_value=target_value,
    )


def record_kpi_result(kpi, after_value, user=None):
    kpi.after_value = after_value
    kpi.measured_at = timezone.now()
    kpi.save(update_fields=['after_value', 'measured_at'])
    log_event(
        kpi.cycle, 'kpi_measured',
        f'KPI mesuré : {kpi.name} = {after_value} {kpi.unit}',
        payload={'kpi_id': kpi.pk, 'value': str(after_value)},
        user=user,
    )
    return kpi


# ─── New cycle from Act ───────────────────────────────────────────────────────

def create_followup_cycle(original_cycle, user):
    new_cycle = create_pdca_cycle(
        company=original_cycle.company,
        brand_key=original_cycle.brand_key,
        title=f'Suite de : {original_cycle.title}',
        problem_statement=original_cycle.actual_result or original_cycle.problem_statement,
        objective=original_cycle.objective,
        category=original_cycle.category,
        priority=original_cycle.priority,
        owner=original_cycle.owner or user,
        created_by=user,
        related_module=original_cycle.related_module,
        parent_cycle=original_cycle,
    )
    log_event(original_cycle, 'followup_cycle_created', f'Nouveau cycle créé : {new_cycle.pk}', user=user)
    return new_cycle
