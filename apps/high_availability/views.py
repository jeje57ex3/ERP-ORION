from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from apps.high_availability import mesh_service
from apps.high_availability.cluster import explorer_grappe, raccorder_grappe
from apps.high_availability.connection import (
    diagnose_node_connection,
    normaliser_base_url,
    prochain_rang_libre,
)
from apps.high_availability.forms import (
    OrionHAClusterForm,
    OrionHAMeshForm,
    OrionHAPeerForm,
    OrionHAConnectForm,
    OrionHANodeForm,
    OrionHASettingsForm,
)
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
    update_node_from_health,
)
from apps.high_availability.failover import run_manual_failover_to_node
from apps.high_availability.takeover import precedence_order


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
        'precedence': precedence_order(),
    })


@super_admin_required
def ha_node_detail_view(request, pk):
    node = get_object_or_404(OrionHANode, pk=pk)
    diagnostic = None

    if request.method == 'POST' and request.POST.get('action') == 'test':
        # Le noeud est passe au diagnostic pour qu'il n'y voie pas son propre
        # identifiant comme deja pris.
        diagnostic = diagnose_node_connection(node.base_url, node=node)
        form = OrionHANodeForm(instance=node)
    elif request.method == 'POST':
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
        'diagnostic': diagnostic,
    })


@super_admin_required
def ha_connect_node_view(request):
    """Raccorde un serveur au cluster, apres epreuve de la liaison.

    Deux actions sur le même formulaire : « tester », qui ne touche à rien, et
    « raccorder », qui refait le test puis enregistre. Le test est refait à
    l'enregistrement à dessein : un résultat affiché depuis plusieurs minutes
    ne prouve plus rien.

    Seul le contrôle d'identité bloque l'enregistrement. Les autres défauts
    sont affichés comme avertissements : une base encore inscriptible, par
    exemple, est grave, mais la fiche du serveur n'est pas nuisible en
    elle-même et la règle de retour la refusera de toute façon.
    """
    diagnostic = None

    if request.method == 'POST':
        form = OrionHAConnectForm(request.POST)
        action = request.POST.get('action', 'test')

        if form.is_valid():
            url, _hote = normaliser_base_url(form.cleaned_data['base_url'])
            diagnostic = diagnose_node_connection(url)

            if action == 'connect':
                if not diagnostic['identity_ok']:
                    messages.error(
                        request,
                        "Raccordement refusé : le serveur n'a pas pu être "
                        'identifié de manière fiable. Corrigez les points '
                        'signalés ci-dessous, puis retestez.',
                    )
                else:
                    node = OrionHANode.objects.create(
                        node_id=diagnostic['node_id'],
                        name=form.cleaned_data['name'],
                        role='secondary',
                        status='healthy' if diagnostic['ok'] else 'warning',
                        base_url=url,
                        region=form.cleaned_data['region'],
                        priority=form.cleaned_data['priority'],
                        is_enabled=True,
                        is_current_active=False,
                        is_failover_target=form.cleaned_data['is_failover_target'],
                        allow_auto_failover=form.cleaned_data['allow_auto_failover'],
                    )
                    if diagnostic['payload']:
                        update_node_from_health(node, diagnostic['payload'])
                    messages.success(
                        request,
                        f'Serveur « {node.name} » raccordé au cluster sous '
                        f"l'identifiant {node.node_id}.",
                    )
                    return redirect('high_availability:admin_nodes')
    else:
        form = OrionHAConnectForm(initial={'priority': prochain_rang_libre()})

    return render(request, 'high_availability/admin_connect.html', {
        'form': form,
        'diagnostic': diagnostic,
        'nodes': OrionHANode.objects.all().order_by('priority'),
    })


@super_admin_required
def ha_cluster_view(request):
    """Relie les serveurs par convention de nommage, avec validation croisee.

    Trois actions sur une seule page : enregistrer les reglages de la grappe,
    explorer les rangs, puis raccorder ceux qui sont valides. L'exploration ne
    modifie rien -- elle sonde et rapporte.

    Le raccordement REFAIT l'exploration avant d'ecrire : un resultat affiche
    depuis plusieurs minutes ne prouve plus rien, et un serveur peut etre tombe
    entre-temps.
    """
    settings_obj = OrionHASettings.get_solo()
    action = request.POST.get('action', '') if request.method == 'POST' else ''
    exploration = None

    if action == 'save':
        form = OrionHAClusterForm(request.POST, instance=settings_obj)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.updated_by = request.user
            obj.save()
            messages.success(request, 'Reglages de la grappe enregistres.')
            return redirect('high_availability:admin_cluster')
    else:
        form = OrionHAClusterForm(instance=settings_obj)

    if action in ('scan', 'join'):
        if not settings_obj.cluster_base_domain:
            messages.error(
                request,
                "Renseignez d'abord le domaine de la grappe, puis enregistrez.",
            )
        else:
            exploration = explorer_grappe(settings_obj)

            if action == 'join':
                resultat = raccorder_grappe(exploration, settings_obj)
                poses = len(resultat['poses'])
                ignores = len(resultat['ignores'])
                if poses:
                    messages.success(
                        request,
                        f'{poses} serveur(s) raccorde(s) a la grappe.',
                    )
                if ignores:
                    messages.warning(
                        request,
                        f'{ignores} serveur(s) ecarte(s) : validation incomplete. '
                        'Voir les motifs ci-dessous.',
                    )
                if not poses and not ignores:
                    messages.info(
                        request,
                        'Aucun serveur Orion trouve aux rangs explores.',
                    )
                # Nouvelle exploration pour refleter l'etat ecrit en base.
                exploration = explorer_grappe(settings_obj)

    return render(request, 'high_availability/admin_cluster.html', {
        'form': form,
        'settings_obj': settings_obj,
        'exploration': exploration,
        'nodes': OrionHANode.objects.all().order_by('priority'),
    })

@super_admin_required
def ha_mesh_view(request):
    """Reseau prive entre serveurs, pilote depuis l'interface.

    Tout ceci n'existait qu'en ligne de commande, et les deux reglages
    (sous-reseau, port) n'etaient exposes nulle part : impossible de les
    changer autrement qu'en base.

    L'echange de cles reste manuel et le restera : aucune des deux cles
    n'existe avant que les deux machines soient installees, et aucune ne peut
    etre devinee par l'une pour l'autre. La page se contente de rendre cet
    echange lisible -- elle affiche la cle a copier, et accepte celle d'en
    face.
    """
    settings_obj = OrionHASettings.get_solo()
    action = request.POST.get('action', '') if request.method == 'POST' else ''

    form = OrionHAMeshForm(instance=settings_obj)
    form_pair = OrionHAPeerForm()

    if action == 'save':
        form = OrionHAMeshForm(request.POST, instance=settings_obj)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.updated_by = request.user
            obj.save()
            messages.success(request, 'Reglages du reseau prive enregistres.')
            return redirect('high_availability:admin_mesh')

    elif action == 'add-peer':
        # Le rang et la cle de CE serveur lui sont passes pour qu'il refuse les
        # deux saisies qui produisent une configuration que WireGuard rejette
        # -- avec, a la cle, une interface arretee et un message qui ne
        # designe pas la cause. La page affichant la cle locale juste au-dessus
        # du formulaire, la coller ici est l'erreur naturelle.
        local_courant = mesh_service.contexte_local(settings_obj)
        form_pair = OrionHAPeerForm(
            request.POST,
            rang_local=local_courant['config'].get('ORION_MESH_RANK'),
            cle_locale=local_courant['cle_publique'],
        )
        if form_pair.is_valid():
            ok, sortie = mesh_service.ajouter_pair(
                form_pair.cleaned_data['rang'],
                form_pair.cleaned_data['cle_publique'],
                form_pair.cleaned_data.get('endpoint') or '',
            )
            if ok:
                messages.success(request, sortie)
                return redirect('high_availability:admin_mesh')
            messages.error(request, sortie)

    elif action in ('init', 'hosts', 'up', 'media-key'):
        operations = {
            'init': mesh_service.initialiser,
            'hosts': mesh_service.poser_hosts,
            'up': mesh_service.activer,
            'media-key': mesh_service.cle_media,
        }
        ok, sortie = operations[action]()
        # La sortie est affichee telle quelle : « init » et « media-key »
        # contiennent la cle publique a copier, qui n'a d'interet que vue.
        if ok:
            messages.success(request, sortie)
        else:
            messages.error(request, sortie)
        return redirect('high_availability:admin_mesh')

    pairs = mesh_service.tableau_des_pairs(settings_obj)

    return render(request, 'high_availability/admin_mesh.html', {
        'form': form,
        'form_pair': form_pair,
        'settings_obj': settings_obj,
        'local': mesh_service.contexte_local(settings_obj),
        'etat': pairs['etat'],
        'lignes': pairs['lignes'],
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
