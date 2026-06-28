from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from .models import WorkflowInstance, WorkflowTemplate
from .services import approve_step, reject_step, get_pending_instances, get_workflow_stats


@login_required
def instance_list(request):
    company = request.current_company
    if not company:
        return redirect('core:dashboard')
    instances = get_pending_instances(company)
    stats = get_workflow_stats(company)
    return render(request, 'workflow_center/instance_list.html', {
        'page_title': 'Workflows', 'instances': instances, 'stats': stats,
    })


@login_required
def instance_detail(request, pk):
    company = request.current_company
    instance = get_object_or_404(WorkflowInstance, pk=pk, company=company)
    return render(request, 'workflow_center/instance_detail.html', {
        'page_title': f'Workflow — {instance.object_type}', 'instance': instance,
        'actions': instance.actions.all().order_by('created_at'),
    })


@login_required
@require_POST
def instance_approve(request, pk):
    company = request.current_company
    instance = get_object_or_404(WorkflowInstance, pk=pk, company=company)
    comment = request.POST.get('comment', '')
    approve_step(instance, request.user, comment=comment)
    messages.success(request, 'Étape approuvée.')
    return redirect('workflow_center:list')


@login_required
@require_POST
def instance_reject(request, pk):
    company = request.current_company
    instance = get_object_or_404(WorkflowInstance, pk=pk, company=company)
    comment = request.POST.get('comment', '')
    reject_step(instance, request.user, comment=comment)
    messages.warning(request, 'Workflow rejeté.')
    return redirect('workflow_center:list')
