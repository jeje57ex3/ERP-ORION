"""
apps/backups/views.py — Vues système de sauvegarde Orion ERP
"""
import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import FileResponse, Http404
from django.core.paginator import Paginator
from django.db.models import Q

from .models import BackupJob, BackupSchedule, BackupRestoreLog
from .forms import BackupCreateForm, BackupScheduleForm, RestoreConfirmForm, BackupImportForm
from .services import (
    create_database_backup, create_media_backup, create_full_backup,
    verify_backup_integrity, restore_backup, get_backup_stats,
    create_portable_backup, import_portable_backup,
)


def _is_staff(user):
    return user.is_authenticated and (user.is_superuser or user.is_staff)


@login_required
def dashboard(request):
    stats = get_backup_stats()
    recent = BackupJob.objects.select_related('company', 'created_by').order_by('-created_at')[:10]
    schedules = BackupSchedule.objects.filter(is_active=True).select_related('company').order_by('frequency', 'time')
    return render(request, 'backups/backup_dashboard.html', {
        'page_title': 'Sauvegardes',
        'stats': stats,
        'recent_jobs': recent,
        'schedules': schedules,
    })


@login_required
def backup_list(request):
    qs = BackupJob.objects.select_related('company', 'created_by').order_by('-created_at')

    status_filter = request.GET.get('status', '')
    scope_filter  = request.GET.get('scope', '')
    search        = request.GET.get('q', '')

    if status_filter:
        qs = qs.filter(status=status_filter)
    if scope_filter:
        qs = qs.filter(scope=scope_filter)
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(company__name__icontains=search))

    paginator = Paginator(qs, 25)
    page_obj  = paginator.get_page(request.GET.get('page'))

    return render(request, 'backups/backup_list.html', {
        'page_title':  'Liste des sauvegardes',
        'page_obj':    page_obj,
        'status_filter': status_filter,
        'scope_filter':  scope_filter,
        'search':        search,
        'status_choices': BackupJob.STATUS_CHOICES,
        'scope_choices':  BackupJob.SCOPE_CHOICES,
    })


@login_required
def backup_detail(request, pk):
    job = get_object_or_404(BackupJob.objects.select_related('company', 'created_by'), pk=pk)
    integrity_ok, integrity_msg = verify_backup_integrity(job)
    restore_logs = job.restore_logs.order_by('-created_at')[:5]
    return render(request, 'backups/backup_detail.html', {
        'page_title':    f'Sauvegarde #{job.pk}',
        'job':           job,
        'integrity_ok':  integrity_ok,
        'integrity_msg': integrity_msg,
        'restore_logs':  restore_logs,
    })


@login_required
@user_passes_test(_is_staff)
def backup_create(request):
    from apps.core.models import Company
    companies = Company.objects.filter(is_active=True).order_by('name')

    if request.method == 'POST':
        form = BackupCreateForm(request.POST, companies=companies)
        if form.is_valid():
            scope      = form.cleaned_data['scope']
            company_id = form.cleaned_data.get('company')
            company    = None
            if company_id:
                try:
                    company = Company.objects.get(pk=company_id)
                except Company.DoesNotExist:
                    pass

            if scope == 'full_system':
                db_job, media_job = create_full_backup(company=company, created_by=request.user)
                messages.success(request, f'Sauvegarde complète lancée (DB: {db_job.status}, Médias: {media_job.status})')
                return redirect('backups:detail', pk=db_job.pk)
            elif scope == 'media_files':
                job = create_media_backup(company=company, created_by=request.user)
            else:
                job = create_database_backup(company=company, scope=scope, created_by=request.user)

            if job.status == 'success':
                messages.success(request, f'Sauvegarde créée avec succès — {job.file_size_display}')
            else:
                messages.error(request, f'Sauvegarde échouée : {job.error_message[:200]}')
            return redirect('backups:detail', pk=job.pk)
    else:
        form = BackupCreateForm(companies=companies)

    return render(request, 'backups/backup_create.html', {
        'page_title': 'Créer une sauvegarde',
        'form': form,
    })


@login_required
@user_passes_test(lambda u: u.is_superuser)
def restore_backup_view(request, pk):
    job = get_object_or_404(BackupJob, pk=pk, status='success')

    if request.method == 'POST':
        form = RestoreConfirmForm(request.POST)
        if form.is_valid():
            log = restore_backup(job, restored_by=request.user)
            if log.status == 'success':
                messages.success(request, 'Restauration effectuée avec succès.')
            else:
                messages.error(request, f'Erreur restauration : {log.error_message[:300]}')
            return redirect('backups:detail', pk=job.pk)
    else:
        form = RestoreConfirmForm()

    return render(request, 'backups/restore_backup.html', {
        'page_title': f'Restaurer #{job.pk}',
        'job':  job,
        'form': form,
    })


@login_required
@user_passes_test(lambda u: u.is_superuser)
def backup_download(request, pk):
    job = get_object_or_404(BackupJob, pk=pk, status='success')
    if not job.file_path or not os.path.exists(job.file_path):
        raise Http404('Fichier de sauvegarde introuvable.')
    return FileResponse(
        open(job.file_path, 'rb'),
        as_attachment=True,
        filename=os.path.basename(job.file_path),
    )


@login_required
@user_passes_test(lambda u: u.is_superuser)
def backup_export(request):
    """
    Crée une sauvegarde portable (base + médias en une seule archive .zip)
    et redirige vers sa page détail — le téléchargement se fait ensuite via
    la vue backup_download existante (fichier prêt à transférer vers une
    autre instance Orion ERP).
    """
    if request.method == 'POST':
        job = create_portable_backup(created_by=request.user)
        if job.status == 'success':
            messages.success(request, f'Export portable créé — {job.file_size_display}. Téléchargez-le ci-dessous.')
        else:
            messages.error(request, f'Export échoué : {job.error_message[:200]}')
        return redirect('backups:detail', pk=job.pk)

    return render(request, 'backups/backup_export.html', {
        'page_title': 'Exporter vers une autre instance',
    })


@login_required
@user_passes_test(lambda u: u.is_superuser)
def backup_import(request):
    """
    Importe une sauvegarde portable (exportée depuis cette instance ou une
    autre) : REMPLACE la base de données et les médias actuels. Une
    sauvegarde de sécurité de l'état actuel est créée automatiquement avant
    l'import (restaurable via backups:restore en cas de problème).
    """
    if request.method == 'POST':
        form = BackupImportForm(request.POST, request.FILES)
        if form.is_valid():
            log = import_portable_backup(form.cleaned_data['file'], created_by=request.user)
            if log.status == 'success':
                messages.success(
                    request,
                    'Import réussi. Base de données et médias remplacés par le contenu de l\'archive.',
                )
            else:
                messages.error(request, f'Import échoué : {log.error_message[:300]}')
            return redirect('backups:detail', pk=log.backup_id)
    else:
        form = BackupImportForm()

    return render(request, 'backups/backup_import.html', {
        'page_title': 'Importer depuis une autre instance',
        'form': form,
    })


@login_required
@user_passes_test(_is_staff)
def backup_schedules(request):
    schedules = BackupSchedule.objects.select_related('company', 'created_by').order_by('-created_at')
    return render(request, 'backups/backup_schedules.html', {
        'page_title': 'Planification des sauvegardes',
        'schedules':  schedules,
    })


@login_required
@user_passes_test(_is_staff)
def schedule_create(request):
    from apps.core.models import Company
    if request.method == 'POST':
        form = BackupScheduleForm(request.POST)
        if form.is_valid():
            schedule = form.save(commit=False)
            schedule.created_by = request.user
            company_id = request.POST.get('company_id')
            if company_id:
                try:
                    schedule.company = Company.objects.get(pk=company_id)
                except Company.DoesNotExist:
                    pass
            schedule.save()
            messages.success(request, 'Planification créée.')
            return redirect('backups:schedules')
    else:
        form = BackupScheduleForm()

    companies = Company.objects.filter(is_active=True).order_by('name')
    return render(request, 'backups/schedule_form.html', {
        'page_title': 'Nouvelle planification',
        'form':       form,
        'companies':  companies,
    })


@login_required
@user_passes_test(_is_staff)
def backup_settings(request):
    stats = get_backup_stats()
    return render(request, 'backups/backup_settings.html', {
        'page_title': 'Paramètres de sauvegarde',
        'stats':      stats,
    })


@login_required
@user_passes_test(_is_staff)
def backup_delete(request, pk):
    job = get_object_or_404(BackupJob, pk=pk)
    if request.method == 'POST':
        if job.file_path and os.path.exists(job.file_path):
            try:
                os.remove(job.file_path)
            except OSError:
                pass
        job.delete()
        messages.success(request, 'Sauvegarde supprimée.')
        return redirect('backups:list')
    return render(request, 'backups/backup_confirm_delete.html', {
        'page_title': 'Supprimer sauvegarde',
        'job': job,
    })
