from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.private_saas.decorators import require_company_module
from apps.domain_diagnostics.forms import CloudflareZoneConfigForm, DomainDiagnosticTargetForm
from apps.domain_diagnostics.models import (
    CloudflareZoneConfig, DomainDiagnosticRun,
    DomainDiagnosticTarget, DomainIssue,
)
from apps.domain_diagnostics.repair_actions import execute_repair, RepairError
from apps.domain_diagnostics.selectors import get_company_targets, get_open_issues, get_recent_repairs
from apps.domain_diagnostics.services import run_domain_diagnostic


def _company_websites(company):
    try:
        from apps.websites.models import Website
        return Website.objects.filter(company=company).order_by('name')
    except Exception:
        return []


def _zone_configs(company):
    return CloudflareZoneConfig.objects.filter(company=company, is_active=True)


@login_required
@require_company_module('domain_diagnostics')
def diagnostics_dashboard(request):
    company = getattr(request, 'current_company', None)
    targets = get_company_targets(company)
    issues = get_open_issues(company)
    repairs = get_recent_repairs(company)
    return render(request, 'domain_diagnostics/dashboard.html', {
        'page_title': 'Diagnostic domaines & Cloudflare',
        'targets': targets,
        'issues': issues,
        'open_count': issues.count(),
        'repairs': repairs,
    })


@login_required
@require_company_module('domain_diagnostics')
def target_create(request):
    company = getattr(request, 'current_company', None)
    if request.method == 'POST':
        form = DomainDiagnosticTargetForm(request.POST)
        form.fields['website'].queryset = _company_websites(company)
        form.fields['cloudflare_zone'].queryset = _zone_configs(company)
        if form.is_valid():
            target = form.save(commit=False)
            target.company = company
            if target.website and target.website.company_id != company.id:
                form.add_error('website', "Ce site n'appartient pas à l'entreprise active.")
            else:
                if target.website and not target.brand_key:
                    target.brand_key = target.website.slug
                target.save()
                messages.success(request, 'Cible diagnostic créée.')
                return redirect('domain_diagnostics:dashboard')
    else:
        form = DomainDiagnosticTargetForm()
    form.fields['website'].queryset = _company_websites(company)
    form.fields['cloudflare_zone'].queryset = _zone_configs(company)
    return render(request, 'domain_diagnostics/domain_form.html', {
        'page_title': 'Nouvelle cible domaine',
        'form': form,
    })


@login_required
@require_company_module('domain_diagnostics')
def target_update(request, pk):
    company = getattr(request, 'current_company', None)
    target = get_object_or_404(DomainDiagnosticTarget, pk=pk, company=company)
    if request.method == 'POST':
        form = DomainDiagnosticTargetForm(request.POST, instance=target)
        form.fields['website'].queryset = _company_websites(company)
        form.fields['cloudflare_zone'].queryset = _zone_configs(company)
        if form.is_valid():
            updated = form.save(commit=False)
            if updated.website and updated.website.company_id != company.id:
                form.add_error('website', "Ce site n'appartient pas à l'entreprise active.")
            else:
                if updated.website and not updated.brand_key:
                    updated.brand_key = updated.website.slug
                updated.save()
                messages.success(request, 'Cible mise à jour.')
                return redirect('domain_diagnostics:dashboard')
    else:
        form = DomainDiagnosticTargetForm(instance=target)
    form.fields['website'].queryset = _company_websites(company)
    form.fields['cloudflare_zone'].queryset = _zone_configs(company)
    return render(request, 'domain_diagnostics/domain_form.html', {
        'page_title': f'Modifier — {target.domain}',
        'form': form,
        'target': target,
    })


@login_required
@require_company_module('domain_diagnostics')
def run_scan(request, pk):
    company = getattr(request, 'current_company', None)
    target = get_object_or_404(DomainDiagnosticTarget, pk=pk, company=company)
    run = run_domain_diagnostic(target, user=request.user)
    messages.success(request, f'Diagnostic terminé — {run.get_status_display()}.')
    return redirect('domain_diagnostics:scan_result', run_id=run.pk)


@login_required
@require_company_module('domain_diagnostics')
def scan_result(request, run_id):
    company = getattr(request, 'current_company', None)
    run = get_object_or_404(
        DomainDiagnosticRun.objects
        .select_related('target')
        .prefetch_related('issues'),
        pk=run_id, company=company,
    )
    return render(request, 'domain_diagnostics/scan_result.html', {
        'page_title': f'Résultat scan — {run.target.domain}',
        'run': run,
        'issues': run.issues.all(),
    })


@login_required
@require_company_module('domain_diagnostics')
def issue_list(request):
    company = getattr(request, 'current_company', None)
    issues = get_open_issues(company)
    return render(request, 'domain_diagnostics/issue_list.html', {
        'page_title': 'Problèmes détectés',
        'issues': issues,
    })


@login_required
@require_company_module('domain_diagnostics')
def repair_issue(request, issue_id):
    company = getattr(request, 'current_company', None)
    issue = get_object_or_404(DomainIssue, pk=issue_id, company=company, status='open')
    if request.method == 'POST':
        try:
            execute_repair(issue, user=request.user)
            messages.success(request, 'Correction appliquée avec succès.')
        except RepairError as exc:
            messages.error(request, str(exc))
        except Exception as exc:
            messages.error(request, f'Erreur lors de la correction : {exc}')
        return redirect('domain_diagnostics:issue_list')
    return render(request, 'domain_diagnostics/repair_confirm.html', {
        'page_title': 'Confirmer la correction',
        'issue': issue,
    })


@login_required
@require_company_module('domain_diagnostics')
def cloudflare_settings(request):
    company = getattr(request, 'current_company', None)
    config = CloudflareZoneConfig.objects.filter(company=company).first()
    if request.method == 'POST':
        form = CloudflareZoneConfigForm(request.POST, instance=config)
        if form.is_valid():
            cfg = form.save(commit=False)
            cfg.company = company
            cfg.created_by = request.user
            cfg.save()
            messages.success(request, 'Configuration Cloudflare enregistrée.')
            return redirect('domain_diagnostics:cloudflare_settings')
    else:
        form = CloudflareZoneConfigForm(instance=config)
    return render(request, 'domain_diagnostics/cloudflare_settings.html', {
        'page_title': 'Configuration Cloudflare',
        'form': form,
        'config': config,
    })
