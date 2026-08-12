"""
apps/websites/views_tunnel.py — Vues de gestion des tunnels Cloudflare Orion ERP
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST

from .models_domains import CloudflareTunnel, TunnelIngressRule, CloudflareAccount
from .forms_tunnel import CloudflareTunnelForm, TunnelIngressRuleForm
from .tunnel_service import (
    generate_config_yml, write_config_yml, get_cloudflared_status,
    sync_tunnel_dns, parse_config_yml,
)


def _company(request):
    return request.current_company


# ─── Liste des tunnels ────────────────────────────────────────────────────────

@login_required
def tunnel_list(request):
    company = _company(request)
    tunnels = CloudflareTunnel.objects.filter(company=company).prefetch_related('ingress_rules')
    cf_status = get_cloudflared_status()
    return render(request, 'websites/tunnel/tunnel_list.html', {
        'tunnels': tunnels,
        'total': tunnels.count(),
        'active_count': tunnels.filter(is_active=True).count(),
        'cf_status': cf_status,
        'page_title': 'Tunnels Cloudflare',
        'active_module': 'websites',
    })


# ─── Détail d'un tunnel ───────────────────────────────────────────────────────

@login_required
def tunnel_detail(request, pk):
    company = _company(request)
    tunnel = get_object_or_404(CloudflareTunnel, pk=pk, company=company)
    rules = tunnel.ingress_rules.select_related('website').order_by('order', 'hostname')
    cf_status = get_cloudflared_status()
    config_preview = generate_config_yml(tunnel)
    return render(request, 'websites/tunnel/tunnel_detail.html', {
        'tunnel': tunnel,
        'rules': rules,
        'cf_status': cf_status,
        'config_preview': config_preview,
        'page_title': tunnel.name,
        'active_module': 'websites',
    })


# ─── Créer un tunnel ─────────────────────────────────────────────────────────

@login_required
def tunnel_create(request):
    company = _company(request)
    if request.method == 'POST':
        form = CloudflareTunnelForm(request.POST, company=company)
        if form.is_valid():
            tunnel = form.save(commit=False)
            tunnel.company = company
            tunnel.save()
            messages.success(request, f'Tunnel « {tunnel.name} » créé avec succès.')
            return redirect('websites:tunnel_detail', pk=tunnel.pk)
    else:
        form = CloudflareTunnelForm(company=company)
    return render(request, 'websites/tunnel/tunnel_form.html', {
        'form': form,
        'action': 'create',
        'page_title': 'Nouveau tunnel',
        'active_module': 'websites',
    })


# ─── Modifier un tunnel ───────────────────────────────────────────────────────

@login_required
def tunnel_edit(request, pk):
    company = _company(request)
    tunnel = get_object_or_404(CloudflareTunnel, pk=pk, company=company)
    if request.method == 'POST':
        form = CloudflareTunnelForm(request.POST, instance=tunnel, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, 'Tunnel mis à jour.')
            return redirect('websites:tunnel_detail', pk=tunnel.pk)
    else:
        form = CloudflareTunnelForm(instance=tunnel, company=company)
    return render(request, 'websites/tunnel/tunnel_form.html', {
        'form': form,
        'tunnel': tunnel,
        'action': 'edit',
        'page_title': f'Modifier — {tunnel.name}',
        'active_module': 'websites',
    })


# ─── Supprimer un tunnel ──────────────────────────────────────────────────────

@login_required
@require_POST
def tunnel_delete(request, pk):
    company = _company(request)
    tunnel = get_object_or_404(CloudflareTunnel, pk=pk, company=company)
    name = tunnel.name
    tunnel.delete()
    messages.success(request, f'Tunnel « {name} » supprimé.')
    return redirect('websites:tunnel_list')


# ─── Ajouter une règle d'ingress ─────────────────────────────────────────────

@login_required
def ingress_create(request, tunnel_pk):
    company = _company(request)
    tunnel = get_object_or_404(CloudflareTunnel, pk=tunnel_pk, company=company)
    if request.method == 'POST':
        form = TunnelIngressRuleForm(request.POST, company=company)
        if form.is_valid():
            rule = form.save(commit=False)
            rule.tunnel = tunnel
            rule.save()
            messages.success(request, f'Règle {rule.hostname} ajoutée.')
            return redirect('websites:tunnel_detail', pk=tunnel.pk)
    else:
        next_order = tunnel.ingress_rules.count()
        form = TunnelIngressRuleForm(company=company, initial={'order': next_order})
    return render(request, 'websites/tunnel/ingress_form.html', {
        'form': form,
        'tunnel': tunnel,
        'action': 'create',
        'page_title': 'Nouvelle règle d\'ingress',
        'active_module': 'websites',
    })


# ─── Modifier une règle d'ingress ────────────────────────────────────────────

@login_required
def ingress_edit(request, tunnel_pk, rule_pk):
    company = _company(request)
    tunnel = get_object_or_404(CloudflareTunnel, pk=tunnel_pk, company=company)
    rule = get_object_or_404(TunnelIngressRule, pk=rule_pk, tunnel=tunnel)
    if request.method == 'POST':
        form = TunnelIngressRuleForm(request.POST, instance=rule, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, 'Règle mise à jour.')
            return redirect('websites:tunnel_detail', pk=tunnel.pk)
    else:
        form = TunnelIngressRuleForm(instance=rule, company=company)
    return render(request, 'websites/tunnel/ingress_form.html', {
        'form': form,
        'tunnel': tunnel,
        'rule': rule,
        'action': 'edit',
        'page_title': f'Modifier — {rule.hostname}',
        'active_module': 'websites',
    })


# ─── Supprimer une règle d'ingress ───────────────────────────────────────────

@login_required
@require_POST
def ingress_delete(request, tunnel_pk, rule_pk):
    company = _company(request)
    tunnel = get_object_or_404(CloudflareTunnel, pk=tunnel_pk, company=company)
    rule = get_object_or_404(TunnelIngressRule, pk=rule_pk, tunnel=tunnel)
    hostname = rule.hostname
    rule.delete()
    messages.success(request, f'Règle {hostname} supprimée.')
    return redirect('websites:tunnel_detail', pk=tunnel.pk)


# ─── Mettre à jour le port d'une règle localhost ─────────────────────────────

@login_required
@require_POST
def ingress_update_port(request, tunnel_pk, rule_pk):
    company = _company(request)
    tunnel = get_object_or_404(CloudflareTunnel, pk=tunnel_pk, company=company)
    rule = get_object_or_404(TunnelIngressRule, pk=rule_pk, tunnel=tunnel)

    port_str = request.POST.get('port', '').strip()
    try:
        port = int(port_str)
        if not (1 <= port <= 65535):
            raise ValueError
    except (ValueError, TypeError):
        messages.error(request, 'Port invalide (1–65535).')
        return redirect('websites:tunnel_detail', pk=tunnel.pk)

    rule.service = f'http://localhost:{port}'
    rule.save(update_fields=['service'])

    if tunnel.config_file:
        success, msg = write_config_yml(tunnel)
        if success:
            messages.success(request, f'{rule.hostname} → port {port} — config.yml mis à jour automatiquement.')
        else:
            messages.warning(request, f'Port mis à jour mais erreur config.yml : {msg}')
    else:
        messages.success(request, f'Port mis à jour : {rule.hostname} → localhost:{port}')

    return redirect('websites:tunnel_detail', pk=tunnel.pk)


# ─── Synchroniser DNS d'une règle ────────────────────────────────────────────

@login_required
@require_POST
def ingress_sync_dns(request, tunnel_pk, rule_pk):
    company = _company(request)
    tunnel = get_object_or_404(CloudflareTunnel, pk=tunnel_pk, company=company)
    rule = get_object_or_404(TunnelIngressRule, pk=rule_pk, tunnel=tunnel)
    success, msg = sync_tunnel_dns(rule)
    if success:
        messages.success(request, msg)
    else:
        messages.error(request, msg)
    return redirect('websites:tunnel_detail', pk=tunnel.pk)


# ─── Écrire config.yml sur disque ────────────────────────────────────────────

@login_required
@require_POST
def tunnel_write_config(request, pk):
    company = _company(request)
    tunnel = get_object_or_404(CloudflareTunnel, pk=pk, company=company)
    success, msg = write_config_yml(tunnel)
    if success:
        messages.success(request, msg)
    else:
        messages.error(request, msg)
    return redirect('websites:tunnel_detail', pk=tunnel.pk)


# ─── Télécharger config.yml ───────────────────────────────────────────────────

@login_required
def tunnel_download_config(request, pk):
    company = _company(request)
    tunnel = get_object_or_404(CloudflareTunnel, pk=pk, company=company)
    content = generate_config_yml(tunnel)
    response = HttpResponse(content, content_type='text/yaml')
    response['Content-Disposition'] = f'attachment; filename="config-{tunnel.pk}.yml"'
    return response


# ─── Import depuis config.yml ou API Cloudflare ──────────────────────────────

@login_required
def tunnel_import(request):
    company = _company(request)
    accounts = CloudflareAccount.objects.filter(company=company)

    if request.method == 'POST':
        method = request.POST.get('method', '')

        # ── Méthode 1 : lecture du config.yml local ──────────────────────────
        if method == 'config_yml':
            config_path = request.POST.get('config_path', '').strip()
            tunnel_name = request.POST.get('tunnel_name', '').strip() or 'Tunnel importé'
            account_pk  = request.POST.get('cloudflare_account', '').strip()

            result = parse_config_yml(config_path)
            if not result['success']:
                messages.error(request, f"Erreur lecture config.yml : {result['error']}")
                return redirect('websites:tunnel_import')
            if not result.get('ingress'):
                messages.warning(request, "Aucune règle d'ingress trouvée dans ce fichier.")
                return redirect('websites:tunnel_import')

            account = None
            if account_pk:
                try:
                    account = CloudflareAccount.objects.get(pk=account_pk, company=company)
                except CloudflareAccount.DoesNotExist:
                    pass

            tunnel, created = CloudflareTunnel.objects.get_or_create(
                company=company,
                tunnel_id=result['tunnel_id'],
                defaults={
                    'name': tunnel_name,
                    'credentials_file': result.get('credentials_file', ''),
                    'config_file': config_path,
                    'cloudflare_account': account,
                    'is_active': True,
                },
            )
            if not created:
                tunnel.name = tunnel_name
                tunnel.config_file = config_path
                if result.get('credentials_file'):
                    tunnel.credentials_file = result['credentials_file']
                if account:
                    tunnel.cloudflare_account = account
                tunnel.save()

            created_count = 0
            skipped_count = 0
            for i, rule_data in enumerate(result['ingress']):
                hostname = rule_data.get('hostname', '').strip()
                service  = rule_data.get('service', '').strip()
                if not hostname or not service:
                    continue
                _, rule_created = TunnelIngressRule.objects.get_or_create(
                    tunnel=tunnel,
                    hostname=hostname,
                    defaults={'service': service, 'order': i, 'is_active': True},
                )
                if rule_created:
                    created_count += 1
                else:
                    skipped_count += 1

            action = 'créé' if created else 'mis à jour'
            msg = (
                f'Tunnel « {tunnel.name} » {action} — '
                f'{created_count} règle(s) importée(s)'
            )
            if skipped_count:
                msg += f', {skipped_count} déjà existante(s)'
            messages.success(request, msg + '.')
            return redirect('websites:tunnel_detail', pk=tunnel.pk)

        # ── Méthode 2 : import depuis l'API Cloudflare ───────────────────────
        elif method == 'api':
            account_pk         = request.POST.get('cloudflare_account', '').strip()
            selected_tunnel_id = request.POST.get('tunnel_id', '').strip()
            tunnel_name        = request.POST.get('tunnel_name', '').strip()

            if not account_pk:
                messages.error(request, 'Sélectionnez un compte Cloudflare.')
                return redirect('websites:tunnel_import')
            try:
                account = CloudflareAccount.objects.get(pk=account_pk, company=company)
            except CloudflareAccount.DoesNotExist:
                messages.error(request, 'Compte Cloudflare introuvable.')
                return redirect('websites:tunnel_import')

            if not account.account_id:
                messages.error(
                    request,
                    "L'account_id est manquant. Testez d'abord la connexion depuis le dashboard Cloudflare."
                )
                return redirect('websites:tunnel_import')

            if not selected_tunnel_id:
                messages.error(request, 'Aucun tunnel sélectionné.')
                return redirect('websites:tunnel_import')

            from .cloudflare_service import fetch_tunnel_ingress
            ingress_result = fetch_tunnel_ingress(account, selected_tunnel_id)
            if not ingress_result['success']:
                messages.warning(
                    request,
                    f"Impossible de récupérer les règles d'ingress via API : {ingress_result.get('error', '')}. "
                    "Le tunnel sera créé sans règles — ajoutez-les manuellement."
                )

            tunnel, created = CloudflareTunnel.objects.get_or_create(
                company=company,
                tunnel_id=selected_tunnel_id,
                defaults={
                    'name': tunnel_name or f'Tunnel {selected_tunnel_id[:8]}',
                    'cloudflare_account': account,
                    'is_active': True,
                },
            )
            if not created:
                if tunnel_name:
                    tunnel.name = tunnel_name
                tunnel.cloudflare_account = account
                tunnel.save()

            created_count = 0
            for i, rule_data in enumerate(ingress_result.get('ingress', [])):
                hostname = rule_data.get('hostname', '').strip()
                service  = rule_data.get('service', '').strip()
                if not hostname or not service:
                    continue
                _, rule_created = TunnelIngressRule.objects.get_or_create(
                    tunnel=tunnel,
                    hostname=hostname,
                    defaults={'service': service, 'order': i, 'is_active': True},
                )
                if rule_created:
                    created_count += 1

            action = 'créé' if created else 'mis à jour'
            messages.success(
                request,
                f'Tunnel « {tunnel.name} » {action} — {created_count} règle(s) importée(s).'
            )
            return redirect('websites:tunnel_detail', pk=tunnel.pk)

    return render(request, 'websites/tunnel/tunnel_import.html', {
        'accounts': accounts,
        'default_config_path': r'C:\Users\jessy\.cloudflared\config.yml',
        'page_title': 'Importer un tunnel',
        'active_module': 'websites',
    })


# ─── API JSON — tunnels CF d'un compte (pour le formulaire live) ─────────────

@login_required
def api_fetch_cf_tunnels(request):
    """GET ?account=<pk> — liste les Named Tunnels Cloudflare d'un compte."""
    company    = _company(request)
    account_pk = request.GET.get('account', '').strip()
    if not account_pk:
        return JsonResponse({'success': False, 'error': 'account manquant'})
    try:
        account = CloudflareAccount.objects.get(pk=account_pk, company=company)
    except CloudflareAccount.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Compte introuvable'})
    from .cloudflare_service import fetch_cf_tunnels
    return JsonResponse(fetch_cf_tunnels(account))


# ─── API JSON — preview d'un config.yml avant import ─────────────────────────

@login_required
def api_preview_config_yml(request):
    """POST {path} — retourne le contenu parsé d'un config.yml sans rien créer."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST requis'}, status=405)
    import json
    try:
        body = json.loads(request.body)
        path = body.get('path', '').strip()
    except Exception:
        path = request.POST.get('path', '').strip()
    if not path:
        return JsonResponse({'success': False, 'error': 'Chemin manquant'})
    return JsonResponse(parse_config_yml(path))


# ─── API JSON — statut cloudflared ───────────────────────────────────────────

@login_required
def api_tunnel_status(request):
    return JsonResponse(get_cloudflared_status())
