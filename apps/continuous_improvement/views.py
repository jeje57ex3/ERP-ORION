from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.http import Http404

from .models import PDCACycle, PDCAPlan, PDCADo, PDCACheck, PDCAAct, PDCAAction, PDCAKPI, PDCATemplate
from .forms import (
    PDCACycleCreateForm, PDCACycleEditForm,
    PDCAPlanForm, PDCADoForm, PDCACheckForm, PDCAActForm,
    PDCAActionForm, PDCAKPIForm,
)
from .services import (
    create_pdca_cycle, activate_cycle, advance_stage,
    update_plan, validate_plan, update_do, complete_do,
    update_check, finalize_check, record_act_decision,
    create_action, complete_action, cancel_action,
    add_kpi, record_kpi_result, cancel_cycle, create_followup_cycle,
)
from .selectors import (
    get_cycles_for_company, get_cycle_detail, get_late_cycles,
    get_pending_actions_for_user, get_dashboard_stats,
    get_standards_for_company, get_overdue_actions, get_active_templates,
)
from .kpis import auto_populate_kpis, compute_cycle_success_rate, compute_action_completion_rate
from .permissions import can_view_pdca, can_edit_pdca, can_advance_stage as perm_advance


@login_required
def dashboard(request):
    company = request.current_company
    if not company:
        return redirect('core:dashboard')

    stats = get_dashboard_stats(company)
    active_cycles = get_cycles_for_company(company, status='active').order_by('target_date')[:10]
    late_cycles = get_late_cycles(company)[:5]
    my_actions = get_pending_actions_for_user(request.user, company)[:8]
    overdue_actions = get_overdue_actions(company)[:5]

    return render(request, 'continuous_improvement/dashboard.html', {
        'page_title': 'Amélioration continue — PDCA',
        'stats': stats,
        'active_cycles': active_cycles,
        'late_cycles': late_cycles,
        'my_actions': my_actions,
        'overdue_actions': overdue_actions,
        'today': timezone.now().date(),
    })


@login_required
def cycle_list(request):
    company = request.current_company
    if not company:
        return redirect('core:dashboard')

    stage_filter = request.GET.get('stage', '')
    status_filter = request.GET.get('status', '')
    category_filter = request.GET.get('category', '')

    cycles = get_cycles_for_company(
        company,
        stage=stage_filter or None,
        status=status_filter or None,
        category=category_filter or None,
    )

    return render(request, 'continuous_improvement/cycle_list.html', {
        'page_title': 'Cycles PDCA',
        'cycles': cycles,
        'stage_filter': stage_filter,
        'status_filter': status_filter,
        'category_filter': category_filter,
        'stage_choices': PDCACycle.STAGE_CHOICES,
        'status_choices': PDCACycle.STATUS_CHOICES,
        'category_choices': PDCACycle.CATEGORY_CHOICES,
    })


@login_required
def cycle_create(request):
    company = request.current_company
    if not company:
        return redirect('core:dashboard')

    template_id = request.GET.get('template')
    template_obj = None
    initial = {}

    if template_id:
        template_obj = PDCATemplate.objects.filter(pk=template_id, is_active=True).first()
        if template_obj:
            initial = {
                'category': template_obj.category,
                'priority': template_obj.priority,
                'problem_statement': template_obj.default_problem_statement,
                'objective': template_obj.default_objective,
                'success_criteria': template_obj.default_success_criteria,
            }

    if request.method == 'POST':
        form = PDCACycleCreateForm(request.POST)
        if form.is_valid():
            cycle = create_pdca_cycle(
                company=company,
                brand_key=form.cleaned_data.get('brand_key', ''),
                title=form.cleaned_data['title'],
                problem_statement=form.cleaned_data['problem_statement'],
                objective=form.cleaned_data['objective'],
                category=form.cleaned_data['category'],
                priority=form.cleaned_data['priority'],
                owner=form.cleaned_data.get('owner') or request.user,
                created_by=request.user,
                start_date=form.cleaned_data.get('start_date'),
                target_date=form.cleaned_data.get('target_date'),
                root_cause=form.cleaned_data.get('root_cause', ''),
                success_criteria=form.cleaned_data.get('success_criteria', ''),
                expected_result=form.cleaned_data.get('expected_result', ''),
                related_module=form.cleaned_data.get('related_module', ''),
                template=template_obj,
            )
            auto_populate_kpis(cycle)
            messages.success(request, f'Cycle PDCA « {cycle.title} » créé avec succès.')
            return redirect('continuous_improvement:cycle_detail', pk=cycle.pk)
    else:
        form = PDCACycleCreateForm(initial=initial)

    templates = get_active_templates()

    return render(request, 'continuous_improvement/cycle_form.html', {
        'page_title': 'Nouveau cycle PDCA',
        'form': form,
        'templates': templates,
        'selected_template': template_obj,
    })


@login_required
def cycle_detail(request, pk):
    company = request.current_company
    cycle = get_cycle_detail(pk, company)
    if not cycle:
        raise Http404

    if not can_view_pdca(request.user, cycle):
        messages.error(request, 'Accès refusé à ce cycle.')
        return redirect('continuous_improvement:dashboard')

    can_edit = can_edit_pdca(request.user, cycle)
    can_advance = perm_advance(request.user, cycle)

    plan_form = PDCAPlanForm(instance=getattr(cycle, 'plan', None)) if can_edit else None
    do_form = PDCADoForm(instance=getattr(cycle, 'do', None)) if can_edit else None
    check_form = PDCACheckForm(instance=getattr(cycle, 'pdca_check', None)) if can_edit else None
    act_form = PDCAActForm(instance=getattr(cycle, 'act', None)) if can_edit else None
    action_form = PDCAActionForm() if can_edit else None
    kpi_form = PDCAKPIForm() if can_edit else None

    return render(request, 'continuous_improvement/cycle_detail.html', {
        'page_title': cycle.title,
        'cycle': cycle,
        'can_edit': can_edit,
        'can_advance': can_advance,
        'plan_form': plan_form,
        'do_form': do_form,
        'check_form': check_form,
        'act_form': act_form,
        'action_form': action_form,
        'kpi_form': kpi_form,
        'action_completion_rate': compute_action_completion_rate(cycle),
        'kpi_success_rate': compute_cycle_success_rate(cycle),
    })


@login_required
def cycle_edit(request, pk):
    company = request.current_company
    cycle = get_object_or_404(PDCACycle, pk=pk, company=company)
    if not can_edit_pdca(request.user, cycle):
        messages.error(request, 'Vous ne pouvez pas modifier ce cycle.')
        return redirect('continuous_improvement:cycle_detail', pk=pk)

    if request.method == 'POST':
        form = PDCACycleEditForm(request.POST, instance=cycle)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cycle mis à jour.')
            return redirect('continuous_improvement:cycle_detail', pk=pk)
    else:
        form = PDCACycleEditForm(instance=cycle)

    return render(request, 'continuous_improvement/cycle_form.html', {
        'page_title': f'Modifier — {cycle.title}',
        'form': form,
        'cycle': cycle,
        'is_edit': True,
    })


# ─── Phase form submissions ────────────────────────────────────────────────────

@login_required
def save_plan(request, pk):
    company = request.current_company
    cycle = get_object_or_404(PDCACycle, pk=pk, company=company)
    if not can_edit_pdca(request.user, cycle):
        messages.error(request, 'Accès refusé.')
        return redirect('continuous_improvement:cycle_detail', pk=pk)

    if request.method == 'POST':
        plan_obj, _ = PDCAPlan.objects.get_or_create(cycle=cycle)
        form = PDCAPlanForm(request.POST, instance=plan_obj)
        if form.is_valid():
            form.save()
            if 'validate' in request.POST:
                validate_plan(cycle, user=request.user)
                messages.success(request, 'Plan validé.')
            else:
                messages.success(request, 'Phase PLAN enregistrée.')

    return redirect('continuous_improvement:cycle_detail', pk=pk)


@login_required
def save_do(request, pk):
    company = request.current_company
    cycle = get_object_or_404(PDCACycle, pk=pk, company=company)
    if not can_edit_pdca(request.user, cycle):
        messages.error(request, 'Accès refusé.')
        return redirect('continuous_improvement:cycle_detail', pk=pk)

    if request.method == 'POST':
        do_obj, _ = PDCADo.objects.get_or_create(cycle=cycle)
        form = PDCADoForm(request.POST, instance=do_obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'Phase FAIRE enregistrée.')

    return redirect('continuous_improvement:cycle_detail', pk=pk)


@login_required
def save_check(request, pk):
    company = request.current_company
    cycle = get_object_or_404(PDCACycle, pk=pk, company=company)
    if not can_edit_pdca(request.user, cycle):
        messages.error(request, 'Accès refusé.')
        return redirect('continuous_improvement:cycle_detail', pk=pk)

    if request.method == 'POST':
        check_obj, _ = PDCACheck.objects.get_or_create(cycle=cycle)  # related_name='pdca_check'
        form = PDCACheckForm(request.POST, instance=check_obj)
        if form.is_valid():
            form.save()
            if 'finalize' in request.POST:
                finalize_check(cycle, user=request.user)
                messages.success(request, 'Vérification finalisée.')
            else:
                messages.success(request, 'Phase VÉRIFIER enregistrée.')

    return redirect('continuous_improvement:cycle_detail', pk=pk)


@login_required
def save_act(request, pk):
    company = request.current_company
    cycle = get_object_or_404(PDCACycle, pk=pk, company=company)
    if not can_edit_pdca(request.user, cycle):
        messages.error(request, 'Accès refusé.')
        return redirect('continuous_improvement:cycle_detail', pk=pk)

    if request.method == 'POST':
        act_obj, _ = PDCAAct.objects.get_or_create(cycle=cycle)
        form = PDCAActForm(request.POST, instance=act_obj)
        if form.is_valid():
            cleaned = form.cleaned_data
            decision = cleaned.get('decision', '')
            record_act_decision(
                cycle=cycle,
                decision=decision,
                reason=cleaned.get('decision_reason', ''),
                standardization_notes=cleaned.get('standardization_notes', ''),
                next_steps=cleaned.get('next_steps', ''),
                user=request.user,
            )
            if cleaned.get('create_new_cycle') and decision == 'restart_cycle':
                new_cycle = create_followup_cycle(cycle, request.user)
                messages.success(request, f'Nouveau cycle créé : {new_cycle.title}')
                return redirect('continuous_improvement:cycle_detail', pk=new_cycle.pk)
            messages.success(request, 'Décision ACT enregistrée.')

    return redirect('continuous_improvement:cycle_detail', pk=pk)


@login_required
def advance_cycle_stage(request, pk):
    company = request.current_company
    cycle = get_object_or_404(PDCACycle, pk=pk, company=company)
    if not perm_advance(request.user, cycle):
        messages.error(request, 'Accès refusé.')
        return redirect('continuous_improvement:cycle_detail', pk=pk)

    if request.method == 'POST':
        try:
            advance_stage(cycle, user=request.user)
            messages.success(request, f'Étape avancée : {cycle.get_stage_display()}')
        except ValueError as e:
            messages.error(request, str(e))

    return redirect('continuous_improvement:cycle_detail', pk=pk)


@login_required
def activate_cycle_view(request, pk):
    company = request.current_company
    cycle = get_object_or_404(PDCACycle, pk=pk, company=company)
    if not can_edit_pdca(request.user, cycle):
        messages.error(request, 'Accès refusé.')
        return redirect('continuous_improvement:cycle_detail', pk=pk)

    if request.method == 'POST':
        try:
            activate_cycle(cycle, user=request.user)
            messages.success(request, 'Cycle activé.')
        except ValueError as e:
            messages.error(request, str(e))

    return redirect('continuous_improvement:cycle_detail', pk=pk)


@login_required
def cancel_cycle_view(request, pk):
    company = request.current_company
    cycle = get_object_or_404(PDCACycle, pk=pk, company=company)
    if not can_edit_pdca(request.user, cycle):
        messages.error(request, 'Accès refusé.')
        return redirect('continuous_improvement:cycle_detail', pk=pk)

    if request.method == 'POST':
        reason = request.POST.get('reason', '')
        cancel_cycle(cycle, reason=reason, user=request.user)
        messages.warning(request, 'Cycle annulé.')
        return redirect('continuous_improvement:cycle_list')

    return redirect('continuous_improvement:cycle_detail', pk=pk)


# ─── Action views ─────────────────────────────────────────────────────────────

@login_required
def add_action_view(request, pk):
    company = request.current_company
    cycle = get_object_or_404(PDCACycle, pk=pk, company=company)
    if not can_edit_pdca(request.user, cycle):
        messages.error(request, 'Accès refusé.')
        return redirect('continuous_improvement:cycle_detail', pk=pk)

    if request.method == 'POST':
        form = PDCAActionForm(request.POST)
        if form.is_valid():
            create_action(
                cycle=cycle,
                title=form.cleaned_data['title'],
                description=form.cleaned_data.get('description', ''),
                assigned_to=form.cleaned_data.get('assigned_to'),
                due_date=form.cleaned_data.get('due_date'),
                order=form.cleaned_data.get('order', 100),
                user=request.user,
            )
            messages.success(request, 'Action ajoutée.')

    return redirect('continuous_improvement:cycle_detail', pk=pk)


@login_required
def complete_action_view(request, action_pk):
    company = request.current_company
    action = get_object_or_404(PDCAAction, pk=action_pk, cycle__company=company)
    if not can_edit_pdca(request.user, action.cycle):
        messages.error(request, 'Accès refusé.')
        return redirect('continuous_improvement:cycle_detail', pk=action.cycle_id)

    if request.method == 'POST':
        evidence = request.POST.get('evidence', '')
        complete_action(action, evidence=evidence, user=request.user)
        messages.success(request, f'Action « {action.title} » terminée.')

    return redirect('continuous_improvement:cycle_detail', pk=action.cycle_id)


# ─── KPI views ────────────────────────────────────────────────────────────────

@login_required
def add_kpi_view(request, pk):
    company = request.current_company
    cycle = get_object_or_404(PDCACycle, pk=pk, company=company)
    if not can_edit_pdca(request.user, cycle):
        messages.error(request, 'Accès refusé.')
        return redirect('continuous_improvement:cycle_detail', pk=pk)

    if request.method == 'POST':
        form = PDCAKPIForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            kpi = add_kpi(
                cycle=cycle,
                name=cd['name'],
                unit=cd.get('unit', ''),
                description=cd.get('description', ''),
                before_value=cd.get('before_value'),
                target_value=cd.get('target_value'),
            )
            if cd.get('after_value') is not None:
                record_kpi_result(kpi, cd['after_value'], user=request.user)
            messages.success(request, f'KPI « {kpi.name} » ajouté.')

    return redirect('continuous_improvement:cycle_detail', pk=pk)


# ─── Standards & templates ────────────────────────────────────────────────────

@login_required
def standards_list(request):
    company = request.current_company
    if not company:
        return redirect('core:dashboard')

    standards = get_standards_for_company(company)
    return render(request, 'continuous_improvement/standards_list.html', {
        'page_title': 'Standards & bonnes pratiques',
        'standards': standards,
    })


@login_required
def templates_list(request):
    templates = get_active_templates()
    return render(request, 'continuous_improvement/templates_list.html', {
        'page_title': 'Modèles PDCA',
        'templates': templates,
        'category_choices': PDCACycle.CATEGORY_CHOICES,
    })
