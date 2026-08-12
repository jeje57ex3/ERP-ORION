"""
apps/private_saas/views.py — Super Admin Orion ERP (SaaS privé)
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Count
from django.utils import timezone

from apps.core.models import Company
from .decorators import super_admin_required
from .models import CompanyModule, PrivateSaaSSettings, CompanyBackup, MODULE_LABELS, ALL_MODULE_CODES
from .forms import CompanyCreateForm, CompanyModuleForm, PrivateSaaSSettingsForm
from .services import (
    create_private_company, create_company_admin,
    seed_company_modules, get_accessible_companies,
    activate_company, archive_company,
)


# ─── Dashboard Super Admin ────────────────────────────────────────────────────

@super_admin_required
def super_admin_dashboard(request):
    companies = Company.objects.all()
    active    = companies.filter(is_active=True)

    try:
        from apps.websites.models import Website
        sites_count = Website.objects.filter(is_active=True).count()
    except Exception:
        sites_count = 0

    try:
        from apps.websites.models import WebsiteDomain
        domains_count = WebsiteDomain.objects.filter(status='active').count()
    except Exception:
        domains_count = 0

    from django.contrib.auth.models import User
    users_count = User.objects.filter(is_active=True).count()

    recent_backups = CompanyBackup.objects.select_related('company').order_by('-created_at')[:5]

    saas_settings = PrivateSaaSSettings.get()

    return render(request, 'private_saas/super_admin_dashboard.html', {
        'page_title':      'Super Admin — Orion ERP',
        'active_module':   'private_saas',
        'companies_count': companies.count(),
        'active_count':    active.count(),
        'sites_count':     sites_count,
        'domains_count':   domains_count,
        'users_count':     users_count,
        'recent_backups':  recent_backups,
        'saas_settings':   saas_settings,
    })


# ─── Liste des entreprises ────────────────────────────────────────────────────

@super_admin_required
def company_list(request):
    q = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '')

    qs = Company.objects.all().order_by('name')
    if q:
        qs = qs.filter(name__icontains=q)
    if status_filter:
        qs = qs.filter(status=status_filter)

    companies = qs.annotate(
        modules_enabled=Count('modules', filter=__import__('django.db.models', fromlist=['Q']).Q(modules__is_enabled=True)),
    )

    return render(request, 'private_saas/company_list.html', {
        'page_title':     'Entreprises',
        'active_module':  'private_saas',
        'companies':      companies,
        'q':              q,
        'status_filter':  status_filter,
        'status_choices': Company.STATUS_CHOICES if hasattr(Company, 'STATUS_CHOICES') else [],
    })


# ─── Détail entreprise ────────────────────────────────────────────────────────

@super_admin_required
def company_detail(request, pk):
    company = get_object_or_404(Company, pk=pk)
    modules = CompanyModule.objects.filter(company=company).order_by('module_code')
    backups = CompanyBackup.objects.filter(company=company).order_by('-created_at')[:5]

    try:
        from apps.websites.models import Website
        sites = Website.objects.filter(company=company)
    except Exception:
        sites = []

    try:
        from apps.access_control.models import UserCompanyAccess
        users = UserCompanyAccess.objects.filter(company=company, is_active=True).select_related('user')
    except Exception:
        try:
            from apps.core.models import CompanyAccess
            users = CompanyAccess.objects.filter(company=company).select_related('user')
        except Exception:
            users = []

    return render(request, 'private_saas/company_detail.html', {
        'page_title':    company.name,
        'active_module': 'private_saas',
        'company':       company,
        'modules':       modules,
        'backups':       backups,
        'sites':         sites,
        'users':         users,
    })


# ─── Créer une entreprise ─────────────────────────────────────────────────────

@super_admin_required
def company_create(request):
    if request.method == 'POST':
        form = CompanyCreateForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data
            try:
                company = create_private_company(
                    name=d['name'],
                    company_type=d['company_type'],
                    created_by=request.user,
                )
                if d.get('legal_name'):
                    company.legal_name = d['legal_name']
                if d.get('currency'):
                    company.currency = d['currency']
                if d.get('timezone'):
                    company.timezone = d['timezone']
                company.save(update_fields=['legal_name', 'currency', 'timezone'])

                user, pwd, created = create_company_admin(
                    company, d['admin_email'],
                    password=d.get('admin_password') or None,
                )
                msg = f'Entreprise « {company.name} » créée avec succès.'
                if created:
                    msg += f' Admin : {user.email} / mot de passe : {pwd}'
                messages.success(request, msg)
                return redirect('private_saas:company_detail', pk=company.pk)
            except Exception as e:
                messages.error(request, f'Erreur : {e}')
    else:
        form = CompanyCreateForm()

    return render(request, 'private_saas/company_create.html', {
        'page_title':    'Nouvelle entreprise',
        'active_module': 'private_saas',
        'form':          form,
    })


# ─── Modules d'une entreprise ─────────────────────────────────────────────────

@super_admin_required
def company_modules(request, pk):
    company = get_object_or_404(Company, pk=pk)
    seed_company_modules(company, company.sector or 'generic')

    if request.method == 'POST':
        for code in ALL_MODULE_CODES:
            try:
                mod = CompanyModule.objects.get(company=company, module_code=code)
            except CompanyModule.DoesNotExist:
                continue
            wanted = request.POST.get(f'module_{code}') == 'on'
            if wanted and not mod.is_enabled:
                mod.enable(user=request.user)
            elif not wanted and mod.is_enabled:
                mod.disable()
        messages.success(request, 'Modules mis à jour.')
        return redirect('private_saas:company_modules', pk=pk)

    form = CompanyModuleForm(company)
    modules = CompanyModule.objects.filter(company=company).order_by('module_code')

    return render(request, 'private_saas/company_modules.html', {
        'page_title':    f'Modules — {company.name}',
        'active_module': 'private_saas',
        'company':       company,
        'form':          form,
        'modules':       modules,
        'module_labels': MODULE_LABELS,
    })


# ─── Utilisateurs d'une entreprise ───────────────────────────────────────────

@super_admin_required
def company_users(request, pk):
    company = get_object_or_404(Company, pk=pk)

    if request.method == 'POST' and request.POST.get('action') == 'add_user':
        email = request.POST.get('email', '').strip()
        if email:
            try:
                user, pwd, created = create_company_admin(company, email)
                if created:
                    messages.success(request, f'Utilisateur {email} créé. Mot de passe : {pwd}')
                else:
                    messages.success(request, f'Utilisateur {email} rattaché à {company.name}.')
            except Exception as e:
                messages.error(request, f'Erreur : {e}')
        return redirect('private_saas:company_users', pk=pk)

    try:
        from apps.access_control.models import UserCompanyAccess
        users = UserCompanyAccess.objects.filter(company=company).select_related('user').order_by('user__email')
    except Exception:
        users = []

    return render(request, 'private_saas/company_users.html', {
        'page_title':    f'Utilisateurs — {company.name}',
        'active_module': 'private_saas',
        'company':       company,
        'users':         users,
    })


# ─── Santé système ────────────────────────────────────────────────────────────

@super_admin_required
def company_health(request):
    from django.db import connections
    checks = []

    # Base centrale
    try:
        from django.db import connection
        connection.ensure_connection()
        checks.append({'label': 'Base centrale (default)', 'ok': True, 'detail': 'Connectée'})
    except Exception as e:
        checks.append({'label': 'Base centrale (default)', 'ok': False, 'detail': str(e)})

    # Entreprises
    companies = Company.objects.filter(is_active=True)
    for company in companies:
        db_name = getattr(company, 'database_name', None) or ''
        checks.append({
            'label':  f'Entreprise : {company.name}',
            'ok':     company.status == 'active',
            'detail': f'Base: {db_name or "partagée (default)"}',
        })

    # Modules
    total_modules = CompanyModule.objects.count()
    enabled_modules = CompanyModule.objects.filter(is_enabled=True).count()
    checks.append({
        'label':  'Modules configurés',
        'ok':     total_modules > 0,
        'detail': f'{enabled_modules} activés / {total_modules} configurés',
    })

    # Sauvegardes récentes
    last_backup = CompanyBackup.objects.filter(status='success').order_by('-created_at').first()
    checks.append({
        'label':  'Dernière sauvegarde',
        'ok':     last_backup is not None,
        'detail': last_backup.created_at.strftime('%d/%m/%Y %H:%M') if last_backup else 'Aucune sauvegarde trouvée',
    })

    saas = PrivateSaaSSettings.get()

    return render(request, 'private_saas/company_health.html', {
        'page_title':    'Santé système',
        'active_module': 'private_saas',
        'checks':        checks,
        'saas_settings': saas,
    })


# ─── Paramètres SaaS privé ────────────────────────────────────────────────────

@super_admin_required
def saas_settings(request):
    saas = PrivateSaaSSettings.get()

    if request.method == 'POST':
        form = PrivateSaaSSettingsForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data
            saas.private_mode_enabled      = d['private_mode_enabled']
            saas.public_signup_enabled     = d['public_signup_enabled']
            saas.allow_domain_management   = d['allow_domain_management']
            saas.allow_module_management   = d['allow_module_management']
            saas.maintenance_mode          = d['maintenance_mode']
            saas.save()
            messages.success(request, 'Paramètres SaaS mis à jour.')
            return redirect('private_saas:saas_settings')
    else:
        form = PrivateSaaSSettingsForm(initial={
            'private_mode_enabled':    saas.private_mode_enabled,
            'public_signup_enabled':   saas.public_signup_enabled,
            'allow_domain_management': saas.allow_domain_management,
            'allow_module_management': saas.allow_module_management,
            'maintenance_mode':        saas.maintenance_mode,
        })

    return render(request, 'private_saas/saas_settings.html', {
        'page_title':    'Paramètres SaaS privé',
        'active_module': 'private_saas',
        'form':          form,
        'saas':          saas,
    })


# ─── Sélecteur d'entreprise ───────────────────────────────────────────────────

def company_switcher(request):
    """Page de sélection / changement d'entreprise active."""
    if not request.user.is_authenticated:
        return redirect('accounts:login')

    companies = get_accessible_companies(request.user)

    if request.method == 'POST':
        company_id = request.POST.get('company_id')
        try:
            company = companies.get(pk=company_id)
            request.session['current_company_id'] = company.pk
            try:
                profile = request.user.profile
                profile.current_company = company
                profile.save(update_fields=['current_company'])
            except Exception:
                pass
            messages.success(request, f'Entreprise active : {company.name}')
        except Company.DoesNotExist:
            messages.error(request, 'Entreprise introuvable.')
        next_url = request.POST.get('next') or 'core:dashboard'
        return redirect(next_url)

    current = getattr(request, 'current_company', None)
    return render(request, 'private_saas/company_switcher.html', {
        'page_title':      'Changer d\'entreprise',
        'companies':       companies,
        'current_company': current,
    })


# ─── Actions rapides ──────────────────────────────────────────────────────────

@super_admin_required
def company_toggle_status(request, pk):
    """Active ou archive une entreprise."""
    if request.method != 'POST':
        return redirect('private_saas:company_detail', pk=pk)
    company = get_object_or_404(Company, pk=pk)
    action  = request.POST.get('action')
    if action == 'activate':
        activate_company(company)
        messages.success(request, f'{company.name} activée.')
    elif action == 'archive':
        archive_company(company)
        messages.warning(request, f'{company.name} archivée.')
    return redirect('private_saas:company_detail', pk=pk)
