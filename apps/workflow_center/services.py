from django.utils import timezone
from .models import WorkflowInstance, WorkflowAction, WorkflowTemplate


def start_workflow(company, object_type, object_id, template_code, created_by=None):
    try:
        template = WorkflowTemplate.objects.get(company=company, code=template_code, is_active=True)
    except WorkflowTemplate.DoesNotExist:
        return None
    return WorkflowInstance.objects.create(
        company=company, template=template,
        object_type=object_type, object_id=str(object_id),
        status='pending', created_by=created_by,
    )


def approve_step(instance, user, comment=''):
    action = WorkflowAction.objects.create(
        instance=instance, user=user,
        action='approve', step_index=instance.current_step_index, comment=comment,
    )
    steps = instance.template.steps if instance.template else []
    if instance.current_step_index + 1 >= len(steps):
        instance.status = 'approved'
        instance.completed_at = timezone.now()
    else:
        instance.current_step_index += 1
        instance.status = 'in_progress'
    instance.save(update_fields=['status', 'current_step_index', 'completed_at'])
    return action


def reject_step(instance, user, comment=''):
    action = WorkflowAction.objects.create(
        instance=instance, user=user,
        action='reject', step_index=instance.current_step_index, comment=comment,
    )
    instance.status = 'rejected'
    instance.completed_at = timezone.now()
    instance.save(update_fields=['status', 'completed_at'])
    return action


def get_pending_instances(company, user=None):
    qs = WorkflowInstance.objects.filter(
        company=company, status__in=('pending', 'in_progress')
    ).select_related('template', 'created_by')
    return qs.order_by('-created_at')


def get_workflow_stats(company):
    qs = WorkflowInstance.objects.filter(company=company)
    return {
        'pending': qs.filter(status='pending').count(),
        'in_progress': qs.filter(status='in_progress').count(),
        'approved': qs.filter(status='approved').count(),
        'rejected': qs.filter(status='rejected').count(),
    }
