"""
apps/websites/views_cloudflare.py — Vues de connexion et gestion du compte Cloudflare
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models_domains import CloudflareAccount, CloudflareTunnel, TunnelIngressRule
from .forms_domains import CloudflareAccountForm
from .cloudflare_service import test_token, get_zones, refresh_account, fetch_cf_tunnels, fetch_tunnel_ingress


def _company(request):
    return request.current_company


# ─── Dashboard Cloudflare ─────────────────────────────────────────────────────

@login_required
def cloudflare_dashboard(request):
    company  = _company(request)
    accounts = CloudflareAccount.objects.filter(company=company).order_by('-is_active', 'label')
    db_tunnels = CloudflareTunnel.objects.filter(company=company).order_by('-created_at')

    active_account = accounts.filter(is_active=True).first()
    zones        = []
    zones_error  = None
    cf_tunnels   = []   # tunnels réels depuis l'API CF
    cf_error     = None

    if active_account:
        # Zones
        zone_result = get_zones(active_account.api_token)
        if zone_result['success']:
            zones = zone_result['zones']
        else:
            zones_error = zone_result.get('error')

        # Tunnels réels depuis l'API CF
        if active_account.account_id:
            tresult = fetch_cf_tunnels(active_account)
            if tresult['success']:
                imported_ids = set(db_tunnels.values_list('tunnel_id', flat=True))
                for t in tresult['tunnels']:
                    t['imported'] = t['id'] in imported_ids
                    t['db_pk'] = next(
                        (dt.pk for dt in db_tunnels if dt.tunnel_id == t['id']), None
                    )
                cf_tunnels = tresult['tunnels']
            else:
                cf_error = tresult.get('error')

    return render(request, 'websites/cloudflare/cloudflare_dashboard.html', {
        'accounts':       accounts,
        'active_account': active_account,
        'db_tunnels':     db_tunnels,
        'cf_tunnels':     cf_tunnels,
        'cf_error':       cf_error,
        'zones':          zones,
        'zones_error':    zones_error,
        'total_accounts': accounts.count(),
        'total_tunnels':  db_tunnels.count(),
        'page_title':     'Cloudflare',
        'active_module':  'websites',
    })


# ─── Connecter un compte Cloudflare ──────────────────────────────────────────

@login_required
def cloudflare_connect(request):
    company = _company(request)
    if request.method == 'POST':
        form = CloudflareAccountForm(request.POST)
        if form.is_valid():
            api_token = form.cleaned_data['api_token']

            # Tester le token avant d'enregistrer
            test_result = test_token(api_token)
            if not test_result['success']:
                form.add_error('api_token', f"Token invalide : {test_result.get('error', 'Erreur inconnue')}")
            else:
                account = form.save(commit=False)
                account.company = company
                # Pré-remplir account_id s'il a été récupéré
                if not account.account_id and test_result.get('account_id'):
                    account.account_id = test_result['account_id']
                account.save()

                account_name = test_result.get('account_name', account.label)
                messages.success(
                    request,
                    f'Compte Cloudflare « {account.label} » connecté avec succès. '
                    f'{test_result.get("account_name", "")}',
                )
                return redirect('websites:cloudflare_dashboard')
    else:
        form = CloudflareAccountForm()

    return render(request, 'websites/cloudflare/cloudflare_form.html', {
        'form': form,
        'action': 'connect',
        'page_title': 'Connecter Cloudflare',
        'active_module': 'websites',
    })


# ─── Modifier un compte ───────────────────────────────────────────────────────

@login_required
def cloudflare_edit(request, pk):
    company = _company(request)
    account = get_object_or_404(CloudflareAccount, pk=pk, company=company)
    if request.method == 'POST':
        form = CloudflareAccountForm(request.POST, instance=account)
        if form.is_valid():
            form.save()
            messages.success(request, 'Compte Cloudflare mis à jour.')
            return redirect('websites:cloudflare_dashboard')
    else:
        form = CloudflareAccountForm(instance=account)
    return render(request, 'websites/cloudflare/cloudflare_form.html', {
        'form': form,
        'account': account,
        'action': 'edit',
        'page_title': f'Modifier — {account.label}',
        'active_module': 'websites',
    })


# ─── Tester la connexion ──────────────────────────────────────────────────────

@login_required
@require_POST
def cloudflare_test(request, pk):
    company = _company(request)
    account = get_object_or_404(CloudflareAccount, pk=pk, company=company)
    result = refresh_account(account)
    if result['success']:
        messages.success(
            request,
            f'Connexion Cloudflare OK — {result.get("zones_count", 0)} zone(s) accessible(s).'
        )
    else:
        messages.error(request, f'Connexion échouée : {result.get("error", "Erreur inconnue")}')
    return redirect('websites:cloudflare_dashboard')


# ─── Activer / désactiver un compte ──────────────────────────────────────────

@login_required
@require_POST
def cloudflare_toggle(request, pk):
    company = _company(request)
    account = get_object_or_404(CloudflareAccount, pk=pk, company=company)
    # Un seul compte actif à la fois
    if not account.is_active:
        CloudflareAccount.objects.filter(company=company, is_active=True).update(is_active=False)
        account.is_active = True
        account.save(update_fields=['is_active'])
        messages.success(request, f'Compte « {account.label} » activé.')
    else:
        account.is_active = False
        account.save(update_fields=['is_active'])
        messages.info(request, f'Compte « {account.label} » désactivé.')
    return redirect('websites:cloudflare_dashboard')


# ─── Supprimer un compte ──────────────────────────────────────────────────────

@login_required
@require_POST
def cloudflare_delete(request, pk):
    company = _company(request)
    account = get_object_or_404(CloudflareAccount, pk=pk, company=company)
    label = account.label
    account.delete()
    messages.success(request, f'Compte « {label} » supprimé.')
    return redirect('websites:cloudflare_dashboard')


# ─── Synchroniser tous les tunnels depuis l'API Cloudflare ───────────────────

@login_required
@require_POST
def cloudflare_sync_tunnels(request):
    """
    Récupère TOUS les Named Tunnels depuis l'API Cloudflare et les importe
    en base (CloudflareTunnel + TunnelIngressRule). Idempotent — ne duplique pas.
    """
    company = _company(request)
    account_pk = request.POST.get('account_pk', '').strip()

    if account_pk:
        account = get_object_or_404(CloudflareAccount, pk=account_pk, company=company)
    else:
        account = CloudflareAccount.objects.filter(company=company, is_active=True).first()
        if not account:
            account = CloudflareAccount.objects.filter(company=company).first()

    if not account:
        messages.error(request, 'Aucun compte Cloudflare disponible. Connectez-en un d\'abord.')
        return redirect('websites:cloudflare_dashboard')

    if not account.account_id:
        messages.error(
            request,
            f'L\'account_id est manquant sur le compte « {account.label} ». '
            'Testez la connexion depuis le dashboard pour le récupérer automatiquement.'
        )
        return redirect('websites:cloudflare_dashboard')

    # 1. Récupérer les tunnels CF
    result = fetch_cf_tunnels(account)
    if not result['success']:
        messages.error(request, f'API Cloudflare : {result.get("error", "Erreur inconnue")}')
        return redirect('websites:cloudflare_dashboard')

    cf_tunnels     = result['tunnels']
    created_tunnels = 0
    created_rules   = 0

    for ct in cf_tunnels:
        tunnel_id   = ct.get('id', '')
        tunnel_name = ct.get('name', '') or f'Tunnel {tunnel_id[:8]}'
        if not tunnel_id:
            continue

        # Créer ou récupérer le tunnel en DB
        tunnel, t_created = CloudflareTunnel.objects.get_or_create(
            company=company,
            tunnel_id=tunnel_id,
            defaults={
                'name':               tunnel_name,
                'cloudflare_account': account,
                'is_active':          True,
            },
        )
        if not t_created:
            # Mettre à jour le compte CF si pas encore lié
            if not tunnel.cloudflare_account:
                tunnel.cloudflare_account = account
                tunnel.save(update_fields=['cloudflare_account'])
        else:
            created_tunnels += 1

        # 2. Récupérer les règles d'ingress depuis l'API
        ingress_result = fetch_tunnel_ingress(account, tunnel_id)
        if ingress_result['success']:
            for i, rule in enumerate(ingress_result.get('ingress', [])):
                hostname = rule.get('hostname', '').strip()
                service  = rule.get('service', '').strip()
                if not hostname or not service:
                    continue
                _, r_created = TunnelIngressRule.objects.get_or_create(
                    tunnel=tunnel,
                    hostname=hostname,
                    defaults={'service': service, 'order': i, 'is_active': True},
                )
                if r_created:
                    created_rules += 1

    if created_tunnels or created_rules:
        messages.success(
            request,
            f'Synchronisation terminée — {created_tunnels} tunnel(s) importé(s), '
            f'{created_rules} règle(s) d\'ingress ajoutée(s).'
        )
    else:
        messages.info(request, 'Tout est déjà synchronisé — aucun nouvel élément.')

    return redirect('websites:tunnel_list')


# ─── Importer un seul tunnel CF (depuis le dashboard, bouton par ligne) ───────

@login_required
@require_POST
def cloudflare_import_one(request):
    """Import rapide d'un seul tunnel CF identifié par son tunnel_id."""
    company    = _company(request)
    account_pk = request.POST.get('account_pk', '').strip()
    tunnel_id  = request.POST.get('tunnel_id', '').strip()
    tunnel_name = request.POST.get('tunnel_name', '').strip()

    if not tunnel_id:
        messages.error(request, 'tunnel_id manquant.')
        return redirect('websites:cloudflare_dashboard')

    account = get_object_or_404(CloudflareAccount, pk=account_pk, company=company)

    tunnel, created = CloudflareTunnel.objects.get_or_create(
        company=company,
        tunnel_id=tunnel_id,
        defaults={
            'name':               tunnel_name or f'Tunnel {tunnel_id[:8]}',
            'cloudflare_account': account,
            'is_active':          True,
        },
    )
    if not created and not tunnel.cloudflare_account:
        tunnel.cloudflare_account = account
        tunnel.save(update_fields=['cloudflare_account'])

    ingress_result = fetch_tunnel_ingress(account, tunnel_id)
    created_rules  = 0
    if ingress_result['success']:
        for i, rule in enumerate(ingress_result.get('ingress', [])):
            hostname = rule.get('hostname', '').strip()
            service  = rule.get('service', '').strip()
            if not hostname or not service:
                continue
            _, r_created = TunnelIngressRule.objects.get_or_create(
                tunnel=tunnel,
                hostname=hostname,
                defaults={'service': service, 'order': i, 'is_active': True},
            )
            if r_created:
                created_rules += 1

    action = 'importé' if created else 'mis à jour'
    messages.success(request, f'Tunnel « {tunnel.name} » {action} — {created_rules} règle(s) d\'ingress.')
    return redirect('websites:tunnel_detail', pk=tunnel.pk)


# ─── API JSON — tester token (pour le formulaire live) ───────────────────────

@login_required
def api_test_token(request):
    """POST avec {token} — retourne JSON {success, account_name, zones_count, error}"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST requis'}, status=405)
    import json
    try:
        body = json.loads(request.body)
        api_token = body.get('token', '').strip()
    except Exception:
        api_token = request.POST.get('token', '').strip()

    if not api_token:
        return JsonResponse({'success': False, 'error': 'Token manquant'})

    result = test_token(api_token)
    if result['success']:
        zones_result = get_zones(api_token)
        return JsonResponse({
            'success': True,
            'account_name': result.get('account_name', ''),
            'account_id': result.get('account_id', ''),
            'zones_count': zones_result.get('total', 0),
            'zones': [{'name': z['name'], 'status': z['status']} for z in zones_result.get('zones', [])[:10]],
        })
    return JsonResponse({'success': False, 'error': result.get('error', 'Erreur')})


# ─── API JSON — zones d'un compte ────────────────────────────────────────────

@login_required
def api_cloudflare_zones(request, pk):
    company = _company(request)
    account = get_object_or_404(CloudflareAccount, pk=pk, company=company)
    result = get_zones(account.api_token)
    return JsonResponse(result)
