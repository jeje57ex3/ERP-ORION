from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from apps.high_availability.forms import OrionHASettingsForm, OrionHANodeForm
from apps.high_availability.models import (
    OrionHANode,
    OrionHASettings,
    OrionHAReplicationStatus,
    OrionHAFailoverEvent,
    OrionHAClusterLock,
)
from apps.high_availability.permissions import super_admin_required
from apps.high_availability.services import (
    check_all_ha_nodes,
    count_healthy_secondaries,
    get_active_node,
    select_best_failover_target,
)
from apps.high_availability.failover import run_manual_failover_to_node


@super_admin_required
def ha_settings_view(request):
    settings_obj = OrionHASettings.get_solo()

    if request.method == 'POST':
        form = OrionHASettingsForm(request.POST, instance=settings_obj)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.updated_by = request.user
            obj.save()
            messages.success(request, 'Paramètres haute disponibilité enregistrés.')
            return redirect('high_availability:admin_settings')
    else:
        form = OrionHASettingsForm(instance=settings_obj)

    return render(request, 'high_availability/admin_settings.html', {
        'form': form,
        'settings_obj': settings_obj,
        'nodes': OrionHANode.objects.all(),
        'active_node': get_active_node(),
        'healthy_secondaries': count_healthy_secondaries(),
        'cluster_lock': OrionHAClusterLock.get_lock(),
    })


@super_admin_required
def ha_nodes_view(request):
    return render(request, 'high_availability/admin_nodes.html', {
        'nodes': OrionHANode.objects.all().order_by('priority'),
    })


@super_admin_required
def ha_node_detail_view(request, pk):
    node = get_object_or_404(OrionHANode, pk=pk)

    if request.method == 'POST':
        form = OrionHANodeForm(request.POST, instance=node)
        if form.is_valid():
            form.save()
            messages.success(request, 'Serveur Orion mis à jour.')
            return redirect('high_availability:admin_node_detail', pk=node.pk)
    else:
        form = OrionHANodeForm(instance=node)

    return render(request, 'high_availability/admin_node_detail.html', {
        'node': node,
        'form': form,
    })


@super_admin_required
def ha_replication_view(request):
    return render(request, 'high_availability/admin_replication.html', {
        'statuses': OrionHAReplicationStatus.objects.select_related('node').all(),
    })


@super_admin_required
def ha_failover_view(request):
    return render(request, 'high_availability/admin_failover.html', {
        'active_node': get_active_node(),
        'best_target': select_best_failover_target(),
        'candidates': OrionHANode.objects.filter(
            role='secondary',
            is_enabled=True,
            is_failover_target=True,
        ).order_by('priority'),
    })


@super_admin_required
def ha_run_failover_view(request):
    if request.method != 'POST':
        return redirect('high_availability:admin_failover')

    node_id = request.POST.get('to_node')
    reason = request.POST.get('reason', 'Bascule manuelle depuis Super Admin')
    target_node = get_object_or_404(OrionHANode, node_id=node_id)

    try:
        event = run_manual_failover_to_node(
            target_node=target_node,
            started_by=request.user,
            reason=reason,
        )
        messages.success(
            request,
            f'Bascule terminée vers {target_node.name}. Événement #{event.id}.',
        )
    except Exception as exc:
        messages.error(request, f'Bascule échouée : {exc}')

    return redirect('high_availability:admin_failover')


@super_admin_required
def ha_events_view(request):
    return render(request, 'high_availability/admin_events.html', {
        'events': OrionHAFailoverEvent.objects.select_related(
            'from_node', 'to_node', 'started_by'
        ).all()[:100],
    })


@super_admin_required
def ha_check_nodes_view(request):
    results = check_all_ha_nodes()
    ok_count = sum(1 for r in results if r.get('ok'))
    messages.info(
        request,
        f'Vérification terminée : {ok_count} OK, {len(results) - ok_count} erreur(s).',
    )
    return redirect('high_availability:admin_nodes')
