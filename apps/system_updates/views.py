from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.system_updates.forms import (
    ConfirmRollbackForm,
    ConfirmUpdateForm,
    ServerActionConfirmForm,
    SystemUpdateSettingsForm,
)
from apps.system_updates.models import ServerActionLog, SystemUpdateRun
from apps.system_updates.permissions import super_admin_required
from apps.system_updates.rollback import rollback_update
from apps.system_updates.selectors import (
    get_latest_update_check,
    get_latest_update_run,
    get_recent_server_actions,
    get_recent_update_runs,
    get_update_settings,
    has_update_running,
)
from apps.system_updates.server_actions import (
    ServerActionError,
    cancel_scheduled_action,
    schedule_reboot,
    schedule_shutdown,
)
from apps.system_updates.services import check_for_updates
from apps.system_updates.update_runner import run_system_update


@super_admin_required
def updates_dashboard(request):
    settings_obj = get_update_settings()

    if request.method == 'POST':
        form = SystemUpdateSettingsForm(request.POST, instance=settings_obj)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.updated_by = request.user
            obj.save()
            messages.success(request, 'Paramètres de mise à jour enregistrés.')
            return redirect('system_updates:dashboard')
    else:
        form = SystemUpdateSettingsForm(instance=settings_obj)

    return render(request, 'system_updates/dashboard.html', {
        'form': form,
        'settings_obj': settings_obj,
        'latest_check': get_latest_update_check(),
        'latest_run': get_latest_update_run(),
        'recent_runs': get_recent_update_runs(),
        'recent_server_actions': get_recent_server_actions(),
        'running': has_update_running(),
    })


@super_admin_required
def check_updates_view(request):
    check = check_for_updates(user=request.user)
    if check.status == 'update_available':
        messages.success(request, 'Une mise à jour est disponible.')
    elif check.status == 'up_to_date':
        messages.info(request, 'Orion ERP est déjà à jour.')
    else:
        messages.error(request, f'Vérification échouée : {check.error_message}')
    return redirect('system_updates:dashboard')


@super_admin_required
def update_confirm_view(request):
    latest_check = get_latest_update_check()

    if has_update_running():
        messages.error(request, 'Une mise à jour est déjà en cours.')
        return redirect('system_updates:dashboard')

    if request.method == 'POST':
        form = ConfirmUpdateForm(request.POST)
        if form.is_valid():
            try:
                update_run = run_system_update(started_by=request.user)
                messages.success(request, f'Mise à jour terminée : #{update_run.id}')
                return redirect('system_updates:update_detail', pk=update_run.pk)
            except Exception as exc:
                messages.error(request, f'Mise à jour échouée : {exc}')
                return redirect('system_updates:dashboard')
    else:
        form = ConfirmUpdateForm()

    return render(request, 'system_updates/update_confirm.html', {
        'form': form,
        'latest_check': latest_check,
    })


@super_admin_required
def update_detail_view(request, pk):
    update_run = get_object_or_404(SystemUpdateRun, pk=pk)
    return render(request, 'system_updates/update_detail.html', {
        'update_run': update_run,
        'logs': update_run.logs.all(),
    })


@super_admin_required
def update_logs_view(request, pk):
    update_run = get_object_or_404(SystemUpdateRun, pk=pk)
    return render(request, 'system_updates/update_logs.html', {
        'update_run': update_run,
        'logs': update_run.logs.all(),
    })


@super_admin_required
def rollback_confirm_view(request, pk):
    update_run = get_object_or_404(SystemUpdateRun, pk=pk)

    if request.method == 'POST':
        form = ConfirmRollbackForm(request.POST)
        if form.is_valid():
            try:
                rollback = rollback_update(update_run, started_by=request.user)
                messages.success(request, f'Rollback terminé : #{rollback.id}')
                return redirect('system_updates:update_detail', pk=update_run.pk)
            except Exception as exc:
                messages.error(request, f'Rollback échoué : {exc}')
                return redirect('system_updates:update_detail', pk=update_run.pk)
    else:
        form = ConfirmRollbackForm()

    return render(request, 'system_updates/rollback_confirm.html', {
        'form': form,
        'update_run': update_run,
    })


@super_admin_required
def server_reboot_confirm(request):
    if request.method == 'POST':
        form = ServerActionConfirmForm(request.POST, expected_text='REDEMARRER')
        if form.is_valid():
            try:
                schedule_reboot()
                ServerActionLog.objects.create(
                    action='reboot', status='success', executed_by=request.user,
                    message='Redémarrage programmé dans 1 minute.',
                )
                messages.success(request, 'Redémarrage programmé — le serveur va redémarrer dans 1 minute.')
            except ServerActionError as exc:
                ServerActionLog.objects.create(
                    action='reboot', status='failed', executed_by=request.user, message=str(exc),
                )
                messages.error(request, f'Redémarrage impossible : {exc}')
            return redirect('system_updates:dashboard')
    else:
        form = ServerActionConfirmForm(expected_text='REDEMARRER')

    return render(request, 'system_updates/server_action_confirm.html', {
        'form': form,
        'action': 'reboot',
        'page_title': 'Redémarrer le serveur',
    })


@super_admin_required
def server_shutdown_confirm(request):
    if request.method == 'POST':
        form = ServerActionConfirmForm(request.POST, expected_text='ETEINDRE')
        if form.is_valid():
            try:
                schedule_shutdown()
                ServerActionLog.objects.create(
                    action='shutdown', status='success', executed_by=request.user,
                    message='Extinction programmée dans 1 minute.',
                )
                messages.success(request, "Extinction programmée — le serveur va s'éteindre dans 1 minute.")
            except ServerActionError as exc:
                ServerActionLog.objects.create(
                    action='shutdown', status='failed', executed_by=request.user, message=str(exc),
                )
                messages.error(request, f'Extinction impossible : {exc}')
            return redirect('system_updates:dashboard')
    else:
        form = ServerActionConfirmForm(expected_text='ETEINDRE')

    return render(request, 'system_updates/server_action_confirm.html', {
        'form': form,
        'action': 'shutdown',
        'page_title': 'Éteindre le serveur',
    })


@super_admin_required
@require_POST
def server_action_cancel(request):
    try:
        cancel_scheduled_action()
        ServerActionLog.objects.create(
            action='cancel', status='success', executed_by=request.user,
            message='Redémarrage/extinction programmé annulé.',
        )
        messages.success(request, 'Redémarrage/extinction programmé annulé.')
    except ServerActionError as exc:
        messages.error(request, f'Annulation impossible : {exc}')
    return redirect('system_updates:dashboard')
