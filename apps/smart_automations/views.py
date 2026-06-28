import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.core.paginator import Paginator

from .models import AutomationRule, AutomationRun
from .services import execute_rule, get_rule_stats, trigger_event
from .forms import AutomationRuleForm


@login_required
def rule_list(request):
    company = request.current_company
    if not company:
        return redirect('core:dashboard')
    rules = AutomationRule.objects.filter(company=company).order_by('-updated_at')
    stats = get_rule_stats(company)
    return render(request, 'smart_automations/rule_list.html', {
        'page_title': 'Automatisations',
        'rules': rules,
        'stats': stats,
    })


@login_required
def rule_create(request):
    company = request.current_company
    if not company:
        return redirect('core:dashboard')
    if request.method == 'POST':
        form = AutomationRuleForm(request.POST)
        if form.is_valid():
            rule = form.save(commit=False)
            rule.company = company
            rule.created_by = request.user
            rule.save()
            messages.success(request, f'Règle « {rule.name} » créée.')
            return redirect('smart_automations:list')
    else:
        form = AutomationRuleForm()
    return render(request, 'smart_automations/rule_form.html', {
        'page_title': 'Nouvelle automatisation',
        'form': form,
    })


@login_required
def rule_edit(request, pk):
    company = request.current_company
    rule = get_object_or_404(AutomationRule, pk=pk, company=company)
    if request.method == 'POST':
        form = AutomationRuleForm(request.POST, instance=rule)
        if form.is_valid():
            form.save()
            messages.success(request, f'Règle « {rule.name} » modifiée.')
            return redirect('smart_automations:list')
    else:
        form = AutomationRuleForm(instance=rule)
    return render(request, 'smart_automations/rule_form.html', {
        'page_title': f'Modifier — {rule.name}',
        'form': form,
        'rule': rule,
    })


@login_required
@require_POST
def rule_toggle(request, pk):
    company = request.current_company
    rule = get_object_or_404(AutomationRule, pk=pk, company=company)
    rule.is_active = not rule.is_active
    rule.save(update_fields=['is_active'])
    status = 'activée' if rule.is_active else 'désactivée'
    messages.success(request, f'Règle {status}.')
    return redirect('smart_automations:list')


@login_required
@require_POST
def rule_run(request, pk):
    company = request.current_company
    rule = get_object_or_404(AutomationRule, pk=pk, company=company)
    run = execute_rule(rule, trigger_payload={'manual': True}, triggered_by=request.user)
    messages.success(request, f'Règle exécutée : {run.get_status_display()}.')
    return redirect('smart_automations:run_list', pk=pk)


@login_required
def run_list(request, pk):
    company = request.current_company
    rule = get_object_or_404(AutomationRule, pk=pk, company=company)
    runs = AutomationRun.objects.filter(rule=rule).order_by('-started_at')
    paginator = Paginator(runs, 20)
    page = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'smart_automations/run_list.html', {
        'page_title': f'Historique — {rule.name}',
        'rule': rule,
        'runs': page,
    })
