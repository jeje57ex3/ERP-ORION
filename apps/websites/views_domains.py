"""
apps/websites/views_domains.py — Vues de gestion complète des domaines Orion ERP
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone

from .models import WebsiteDomain, Website
from .models_domains import DomainRedirect, DomainConnectionLog
from .forms_domains import (
    DomainCreateForm, DomainRedirectForm, DomainSSLForm,
    CloudflareAccountForm,
    DomainWizardStep1Form, DomainWizardStep2Form, DomainWizardStep3Form,
)
from .domain_services import (
    generate_verification_token, normalize_domain, validate_domain_format,
    get_expected_dns_records, verify_domain_ownership, set_primary_domain,
    disable_domain, build_public_url, log_domain_action,
)


def _company(request):
    return request.current_company


# ─── Dashboard domaines ───────────────────────────────────────────────────────

@login_required
def domain_dashboard(request):
    """Vue principale — liste tous les domaines de l'entreprise."""
    company = _company(request)
    all_domains = (
        WebsiteDomain.objects
        .filter(company=company)
        .select_related('website')
        .order_by('-is_primary', 'domain')
    )

    # Filtres
    status_filter = request.GET.get('status', '')
    if status_filter:
        all_domains = all_domains.filter(status=status_filter)

    target_filter = request.GET.get('target', '')
    if target_filter:
        all_domains = all_domains.filter(target_type=target_filter)

    # KPIs
    total            = all_domains.count()
    active_count     = all_domains.filter(status='active').count()
    pending_dns      = all_domains.filter(status__in=['dns_pending', 'pending']).count()
    ssl_active_count = all_domains.filter(ssl_status='active').count()

    from .services.ssl_service import get_expiring_soon
    expiring_ssl = get_expiring_soon(30).filter(company=company).count()

    return render(request, 'websites/domains/domain_list.html', {
        'domains':           all_domains,
        'total':             total,
        'active_count':      active_count,
        'pending_dns':       pending_dns,
        'ssl_active_count':  ssl_active_count,
        'expiring_ssl':      expiring_ssl,
        'status_filter':     status_filter,
        'target_filter':     target_filter,
        'page_title':        'Domaines',
        'active_module':     'websites',
        'STATUS_CHOICES':    WebsiteDomain.STATUS_CHOICES,
        'TARGET_CHOICES':    getattr(WebsiteDomain, 'TARGET_TYPES', []),
    })


# ─── Créer un domaine ─────────────────────────────────────────────────────────

@login_required
def domain_create(request):
    """Formulaire simple d'ajout d'un domaine."""
    company = _company(request)
    form = DomainCreateForm(company=company, data=request.POST or None)

    if request.method == 'POST' and form.is_valid():
        cd     = form.cleaned_data
        domain = cd['domain']
        token  = generate_verification_token(domain)

        wd = WebsiteDomain.objects.create(
            website          = cd.get('website'),
            company          = company,
            domain           = domain,
            domain_type      = cd['domain_type'],
            target_type      = cd['target_type'],
            force_https      = cd['force_https'],
            redirect_www     = cd['redirect_www'],
            verification_token = token,
            expected_txt_record = f'orion-verification={token}',
            status           = 'pending',
            created_by       = request.user,
        )

        log_domain_action(wd, 'created', f'Domaine {domain} ajouté.', 'success', request.user)
        messages.success(request, f'Domaine « {domain} » ajouté. Configurez vos DNS.')
        return redirect('websites:domain_detail', pk=wd.pk)

    return render(request, 'websites/domains/domain_create.html', {
        'form':          form,
        'page_title':    'Ajouter un domaine',
        'active_module': 'websites',
    })


# ─── Détail domaine ───────────────────────────────────────────────────────────

@login_required
def domain_detail(request, pk):
    """Page détail d'un domaine — instructions DNS, SSL, redirections, historique."""
    company   = _company(request)
    domain    = get_object_or_404(
        WebsiteDomain, pk=pk, company=company
    )
    dns_records = get_expected_dns_records(domain)
    redirects   = DomainRedirect.objects.filter(domain=domain).order_by('-created_at')
    logs        = DomainConnectionLog.objects.filter(domain=domain).order_by('-created_at')[:20]

    ssl_form        = DomainSSLForm()
    redirect_form   = DomainRedirectForm()
    public_url      = build_public_url(domain)

    return render(request, 'websites/domains/domain_detail.html', {
        'domain':        domain,
        'dns_records':   dns_records,
        'redirects':     redirects,
        'logs':          logs,
        'ssl_form':      ssl_form,
        'redirect_form': redirect_form,
        'public_url':    public_url,
        'page_title':    f'Domaine — {domain.domain}',
        'active_module': 'websites',
    })


# ─── Vérifier DNS ─────────────────────────────────────────────────────────────

@login_required
@require_POST
def domain_verify(request, pk):
    """Lance la vérification DNS d'un domaine et redirige avec résultat."""
    company = _company(request)
    domain  = get_object_or_404(WebsiteDomain, pk=pk, company=company)

    verified = verify_domain_ownership(domain)
    log_domain_action(
        domain,
        'dns_verified' if verified else 'dns_checked',
        'DNS vérifié avec succès.' if verified else f'DNS non vérifié. {domain.last_error}',
        'success' if verified else 'warning',
        request.user,
    )
    if verified:
        messages.success(request, f'✓ DNS vérifié pour {domain.domain}.')
    else:
        messages.warning(request, f'DNS non vérifié pour {domain.domain}. {domain.last_error}')

    # Réponse JSON si AJAX
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'verified': verified, 'status': domain.status, 'error': domain.last_error})

    return redirect('websites:domain_detail', pk=pk)


# ─── Demander SSL ─────────────────────────────────────────────────────────────

@login_required
@require_POST
def domain_request_ssl(request, pk):
    """Initie la demande SSL pour un domaine."""
    company = _company(request)
    domain  = get_object_or_404(WebsiteDomain, pk=pk, company=company)

    from .services.ssl_service import request_ssl_certificate
    result = request_ssl_certificate(domain)

    if result['success']:
        messages.success(request, 'Demande SSL enregistrée. Suivez les instructions.')
    else:
        messages.error(request, result.get('error', 'Erreur lors de la demande SSL.'))

    return redirect('websites:domain_detail', pk=pk)


@login_required
@require_POST
def domain_mark_ssl_active(request, pk):
    """Marque manuellement le SSL comme actif (après configuration serveur)."""
    company = _company(request)
    domain  = get_object_or_404(WebsiteDomain, pk=pk, company=company)

    from .services.ssl_service import mark_ssl_active, check_ssl_certificate
    # Vérification SSL réelle avant de marquer actif
    ssl_check = check_ssl_certificate(domain)
    if ssl_check['valid']:
        mark_ssl_active(domain, expires_at=ssl_check['expires_at'])
        messages.success(request, f'SSL activé pour {domain.domain}.')
    else:
        # Marquer actif sans vérification (configuration manuelle)
        mark_ssl_active(domain)
        messages.info(request, 'SSL marqué comme actif. Vérification automatique impossible pour l\'instant.')

    return redirect('websites:domain_detail', pk=pk)


# ─── Définir domaine principal ────────────────────────────────────────────────

@login_required
@require_POST
def domain_set_primary(request, pk):
    company = _company(request)
    domain  = get_object_or_404(WebsiteDomain, pk=pk, company=company)

    if not domain.dns_verified:
        messages.error(request, 'Le DNS doit être vérifié avant de définir un domaine principal.')
        return redirect('websites:domain_detail', pk=pk)

    set_primary_domain(domain)
    log_domain_action(domain, 'set_primary', f'{domain.domain} défini comme domaine principal.', 'success', request.user)
    messages.success(request, f'« {domain.domain} » est maintenant le domaine principal.')
    return redirect('websites:domain_detail', pk=pk)


# ─── Désactiver un domaine ────────────────────────────────────────────────────

@login_required
@require_POST
def domain_disable(request, pk):
    company = _company(request)
    domain  = get_object_or_404(WebsiteDomain, pk=pk, company=company)

    if domain.is_primary:
        messages.error(request, 'Impossible de désactiver le domaine principal. Définissez d\'abord un autre domaine principal.')
        return redirect('websites:domain_detail', pk=pk)

    disable_domain(domain)
    log_domain_action(domain, 'disabled', 'Domaine désactivé.', 'warning', request.user)
    messages.warning(request, f'Domaine « {domain.domain} » désactivé.')
    return redirect('websites:domain_dashboard')


# ─── Supprimer un domaine ─────────────────────────────────────────────────────

@login_required
@require_POST
def domain_delete(request, pk):
    company = _company(request)
    domain  = get_object_or_404(WebsiteDomain, pk=pk, company=company)

    if domain.is_primary:
        messages.error(request, 'Impossible de supprimer le domaine principal.')
        return redirect('websites:domain_detail', pk=pk)

    name = domain.domain
    log_domain_action(domain, 'deleted', f'Domaine {name} supprimé.', 'warning', request.user)
    domain.delete()

    from .services.domain_resolver import invalidate_domain_cache
    invalidate_domain_cache(name)

    messages.success(request, f'Domaine « {name} » supprimé.')
    return redirect('websites:domain_dashboard')


# ─── Redirections ─────────────────────────────────────────────────────────────

@login_required
def domain_redirects(request, pk):
    """Liste et gestion des redirections d'un domaine."""
    company    = _company(request)
    domain     = get_object_or_404(WebsiteDomain, pk=pk, company=company)
    redirects  = DomainRedirect.objects.filter(domain=domain)
    form       = DomainRedirectForm()

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'add_redirect':
            form = DomainRedirectForm(request.POST)
            if form.is_valid():
                r = form.save(commit=False)
                r.domain  = domain
                r.company = company
                r.save()
                log_domain_action(domain, 'redirect_created', f'Redirection {r.source_path} → {r.target_url}', 'info', request.user)
                messages.success(request, 'Redirection créée.')
                return redirect('websites:domain_redirects', pk=pk)

        elif action == 'delete_redirect':
            rid = request.POST.get('redirect_id')
            r   = get_object_or_404(DomainRedirect, pk=rid, domain=domain)
            log_domain_action(domain, 'redirect_deleted', f'Redirection {r.source_path} supprimée.', 'warning', request.user)
            r.delete()
            messages.success(request, 'Redirection supprimée.')
            return redirect('websites:domain_redirects', pk=pk)

    return render(request, 'websites/domains/domain_redirects.html', {
        'domain':        domain,
        'redirects':     redirects,
        'form':          form,
        'page_title':    f'Redirections — {domain.domain}',
        'active_module': 'websites',
    })


# ─── Wizard ───────────────────────────────────────────────────────────────────

@login_required
def domain_wizard(request):
    """
    Assistant de connexion domaine en 6 étapes.
    Stocke l'état en session.
    """
    company  = _company(request)
    step_key = 'domain_wizard_step'
    data_key = 'domain_wizard_data'

    if request.GET.get('reset'):
        request.session.pop(step_key, None)
        request.session.pop(data_key, None)
        return redirect('websites:domain_wizard')

    step      = request.session.get(step_key, 1)
    saved     = request.session.get(data_key, {})
    context   = {
        'step': step,
        'saved': saved,
        'page_title': 'Assistant de connexion domaine',
        'active_module': 'websites',
    }

    if request.method == 'POST':
        if step == 1:
            form = DomainWizardStep1Form(request.POST)
            if form.is_valid():
                saved['target_type'] = form.cleaned_data['target_type']
                request.session[data_key] = saved
                request.session[step_key] = 2
                return redirect('websites:domain_wizard')
            context['form'] = form

        elif step == 2:
            form = DomainWizardStep2Form(request.POST)
            if form.is_valid():
                saved['domain']      = form.cleaned_data['domain']
                saved['domain_type'] = form.cleaned_data['domain_type']
                request.session[data_key] = saved
                request.session[step_key] = 3
                return redirect('websites:domain_wizard')
            context['form'] = form

        elif step == 3:
            form = DomainWizardStep3Form(company=company, data=request.POST)
            if form.is_valid():
                ws = form.cleaned_data.get('website')
                saved['website_id'] = ws.pk if ws else None
                request.session[data_key] = saved
                request.session[step_key] = 4
                return redirect('websites:domain_wizard')
            context['form'] = form

        elif step == 4:
            # Étape 4 : Créer le domaine et afficher les instructions DNS
            domain_name = saved.get('domain', '')
            domain_type = saved.get('domain_type', 'subdomain')
            target_type = saved.get('target_type', 'website')
            website_id  = saved.get('website_id')
            website     = Website.objects.filter(pk=website_id, company=company).first() if website_id else None

            if not website:
                website = Website.objects.filter(company=company).first()

            if not website:
                messages.error(request, 'Aucun site web disponible. Créez d\'abord un site.')
                return redirect('websites:website_create')

            token = generate_verification_token(domain_name)
            wd, created = WebsiteDomain.objects.get_or_create(
                website=website,
                domain=domain_name,
                defaults={
                    'company':            company,
                    'domain_type':        domain_type,
                    'target_type':        target_type,
                    'verification_token': token,
                    'expected_txt_record': f'orion-verification={token}',
                    'status':             'pending',
                    'created_by':         request.user,
                },
            )
            if created:
                log_domain_action(wd, 'created', f'Domaine {domain_name} créé via wizard.', 'info', request.user)

            saved['domain_pk'] = wd.pk
            request.session[data_key] = saved
            context['domain']      = wd
            context['dns_records'] = get_expected_dns_records(wd)
            # Afficher l'étape 4 sans avancer automatiquement
            context['step'] = 4

        elif step == 5:
            # Étape 5 : Vérification DNS
            domain_pk = saved.get('domain_pk')
            if domain_pk:
                wd = get_object_or_404(WebsiteDomain, pk=domain_pk, company=company)
                verified = verify_domain_ownership(wd)
                context['domain']   = wd
                context['verified'] = verified
                if verified:
                    request.session[step_key] = 6
            context['step'] = 5

        elif step == 6:
            # Étape 6 : SSL
            domain_pk = saved.get('domain_pk')
            if domain_pk:
                wd = get_object_or_404(WebsiteDomain, pk=domain_pk, company=company)
                from .services.ssl_service import request_ssl_certificate
                result = request_ssl_certificate(wd)
                context['domain']        = wd
                context['ssl_result']    = result
                context['ssl_instructions'] = result.get('instructions', [])
            # Avancer vers l'étape finale
            request.session[step_key] = 7
            context['step'] = 7

        elif step == 7:
            # Terminer le wizard
            domain_pk = saved.get('domain_pk')
            request.session.pop(step_key, None)
            request.session.pop(data_key, None)
            if domain_pk:
                return redirect('websites:domain_detail', pk=domain_pk)
            return redirect('websites:domain_dashboard')

    else:
        # GET : afficher le formulaire de l'étape courante
        if step == 1:
            context['form'] = DomainWizardStep1Form(initial=saved)
        elif step == 2:
            context['form'] = DomainWizardStep2Form(initial=saved)
        elif step == 3:
            context['form'] = DomainWizardStep3Form(company=company, initial=saved)
        elif step == 4:
            domain_pk = saved.get('domain_pk')
            if domain_pk:
                try:
                    wd = WebsiteDomain.objects.get(pk=domain_pk, company=company)
                    context['domain']      = wd
                    context['dns_records'] = get_expected_dns_records(wd)
                except WebsiteDomain.DoesNotExist:
                    pass
        elif step in (5, 6, 7):
            domain_pk = saved.get('domain_pk')
            if domain_pk:
                try:
                    context['domain'] = WebsiteDomain.objects.get(pk=domain_pk, company=company)
                except WebsiteDomain.DoesNotExist:
                    pass

    return render(request, 'websites/domains/domain_wizard.html', context)


# ─── Instructions DNS (standalone) ───────────────────────────────────────────

@login_required
def domain_dns_instructions(request, pk):
    """Page complète des instructions DNS pour un domaine."""
    company = _company(request)
    domain  = get_object_or_404(WebsiteDomain, pk=pk, company=company)
    records = get_expected_dns_records(domain)

    if request.method == 'POST' and request.POST.get('action') == 'verify':
        verified = verify_domain_ownership(domain)
        if verified:
            messages.success(request, f'✓ DNS vérifié pour {domain.domain} !')
        else:
            messages.warning(request, f'DNS non encore propagé. Réessayez dans quelques minutes.')
        return redirect('websites:domain_dns_instructions', pk=pk)

    return render(request, 'websites/domains/domain_dns_instructions.html', {
        'domain':        domain,
        'records':       records,
        'page_title':    f'Instructions DNS — {domain.domain}',
        'active_module': 'websites',
        'PROVIDERS': [
            {'id': 'ovh',        'name': 'OVH'},
            {'id': 'ionos',      'name': 'Ionos'},
            {'id': 'gandi',      'name': 'Gandi'},
            {'id': 'cloudflare', 'name': 'Cloudflare'},
            {'id': 'godaddy',    'name': 'GoDaddy'},
            {'id': 'namecheap',  'name': 'Namecheap'},
            {'id': 'hostinger',  'name': 'Hostinger'},
            {'id': 'other',      'name': 'Autre fournisseur'},
        ],
    })


# ─── API JSON (pour le wizard AJAX et le dashboard temps réel) ───────────────

@login_required
def api_domain_list(request):
    """GET /websites/domaines/api/ — liste JSON des domaines de l'entreprise."""
    company = _company(request)
    domains = WebsiteDomain.objects.filter(company=company).select_related('website')
    data    = [
        {
            'id':           d.pk,
            'domain':       d.domain,
            'status':       d.status,
            'ssl_status':   d.ssl_status,
            'is_primary':   d.is_primary,
            'dns_verified': d.dns_verified,
            'target_type':  getattr(d, 'target_type', 'website'),
            'website':      d.website.name if d.website else None,
            'public_url':   build_public_url(d),
        }
        for d in domains
    ]
    return JsonResponse({'domains': data})


@login_required
def api_domain_status(request, pk):
    """GET /websites/domaines/<pk>/api/status/ — statut JSON d'un domaine."""
    company = _company(request)
    domain  = get_object_or_404(WebsiteDomain, pk=pk, company=company)
    return JsonResponse({
        'id':               domain.pk,
        'domain':           domain.domain,
        'status':           domain.status,
        'status_label':     domain.get_status_display(),
        'dns_verified':     domain.dns_verified,
        'ssl_status':       domain.ssl_status,
        'ssl_status_label': domain.get_ssl_status_display(),
        'is_primary':       domain.is_primary,
        'last_checked_at':  domain.last_checked_at.isoformat() if domain.last_checked_at else None,
        'public_url':       build_public_url(domain),
    })


@login_required
@require_POST
def api_domain_verify(request, pk):
    """POST /websites/domaines/<pk>/api/verify/ — vérifie DNS, retourne JSON."""
    company  = _company(request)
    domain   = get_object_or_404(WebsiteDomain, pk=pk, company=company)
    verified = verify_domain_ownership(domain)
    return JsonResponse({
        'verified':  verified,
        'status':    domain.status,
        'error':     domain.last_error,
        'checked_at': timezone.now().isoformat(),
    })
