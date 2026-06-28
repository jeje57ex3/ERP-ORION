from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from .models import BackupJob
from .services import (
    create_job, start_backup_run, finish_backup_run,
    get_backup_runs, get_backup_stats, get_recent_failures,
)


@login_required
def backup_dashboard(request):
    company = request.current_company
    if not company:
        return redirect('core:dashboard')
    jobs = BackupJob.objects.filter(company=company).order_by('-created_at')
    stats = get_backup_stats(company)
    failures = get_recent_failures(company)
    return render(request, 'backup_center/dashboard.html', {
        'page_title': 'Centre de sauvegardes',
        'jobs': jobs, 'stats': stats, 'failures': failures,
    })


@login_required
def job_detail(request, pk):
    company = request.current_company
    job = get_object_or_404(BackupJob, pk=pk, company=company)
    runs = get_backup_runs(company, job=job, limit=30)
    return render(request, 'backup_center/job_detail.html', {
        'page_title': job.name, 'job': job, 'runs': runs,
    })


@login_required
@require_POST
def run_backup(request, pk):
    company = request.current_company
    job = get_object_or_404(BackupJob, pk=pk, company=company)
    run = start_backup_run(company, job, triggered_by=request.user)
    finish_backup_run(run, success=True, metadata={'triggered_by': request.user.username})
    messages.success(request, f'Sauvegarde « {job.name} » exécutée.')
    return redirect('backup_center:dashboard')


@login_required
@require_POST
def toggle_job(request, pk):
    company = request.current_company
    job = get_object_or_404(BackupJob, pk=pk, company=company)
    job.is_active = not job.is_active
    job.save(update_fields=['is_active', 'updated_at'])
    messages.success(request, f'Tâche {"activée" if job.is_active else "désactivée"}.')
    return redirect('backup_center:dashboard')
