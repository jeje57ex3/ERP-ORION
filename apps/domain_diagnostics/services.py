from django.conf import settings
from django.utils import timezone

from apps.domain_diagnostics.cloudflare import CloudflareClient, CloudflareAPIError
from apps.domain_diagnostics.dns_checks import domain_points_to_expected_ip
from apps.domain_diagnostics.http_checks import check_http_https
from apps.domain_diagnostics.nginx_checks import check_nginx_server_name
from apps.domain_diagnostics.models import (
    DomainDiagnosticRun,
    DomainIssue,
)


def _create_issue(run, issue_type, severity, title, description='',
                  repair_code='', repair_payload=None, can_auto_repair=False):
    return DomainIssue.objects.create(
        company=run.company,
        target=run.target,
        run=run,
        issue_type=issue_type,
        severity=severity,
        title=title,
        description=description,
        repair_code=repair_code,
        repair_payload=repair_payload or {},
        can_auto_repair=can_auto_repair,
    )


def _get_expected_content(target):
    if target.expected_record_content:
        return target.expected_record_content
    if target.expected_origin_ip:
        return str(target.expected_origin_ip)
    return getattr(settings, 'ORION_EXPECTED_ORIGIN_IP', '')


def _get_zone_name(target):
    if target.cloudflare_zone:
        return target.cloudflare_zone.zone_name
    return getattr(settings, 'ORION_CLOUDFLARE_ZONE_NAME', 'elysiums.fr')


def _resolve_zone_id(client, target):
    """Retourne le zone_id, en le persistant sur cloudflare_zone si besoin."""
    if target.cloudflare_zone and target.cloudflare_zone.zone_id:
        return target.cloudflare_zone.zone_id
    zone_id = client.get_zone_id(_get_zone_name(target))
    if target.cloudflare_zone:
        target.cloudflare_zone.zone_id = zone_id
        target.cloudflare_zone.save(update_fields=['zone_id', 'updated_at'])
    return zone_id


# ── Checks individuels ────────────────────────────────────────────────────────

def check_website_link(run):
    target = run.target
    if target.target_type != 'website':
        return {'ok': True, 'skipped': True}

    if not target.website:
        _create_issue(run, 'website_link', 'critical',
                      'Domaine non relié à un Website Orion',
                      f'{target.domain} n\'est relié à aucun Website Orion.',
                      repair_code='link_website_manually', can_auto_repair=False)
        return {'ok': False}

    # Vérification brand_key / slug Orion
    if target.brand_key and target.website.slug != target.brand_key:
        _create_issue(run, 'brand_mismatch', 'critical',
                      'Mauvaise marque liée au domaine',
                      f'{target.domain} attend slug={target.brand_key}, '
                      f'mais Website.slug={target.website.slug}.',
                      repair_code='fix_website_brand_link', can_auto_repair=False)
        return {'ok': False}

    if target.website.domain != target.domain:
        _create_issue(run, 'website_link', 'warning',
                      'Le domaine Website ne correspond pas',
                      f'Website.domain={target.website.domain}, diagnostic domain={target.domain}.',
                      repair_code='sync_website_domain',
                      repair_payload={'website_id': target.website_id, 'domain': target.domain},
                      can_auto_repair=True)
        return {'ok': False}

    return {'ok': True}


def check_cloudflare_dns(run):
    target = run.target
    expected_content = _get_expected_content(target)
    expected_type = target.expected_record_type or 'A'
    expected_proxy = target.expected_proxy

    result = {'ok': False, 'zone_id': '', 'records': [], 'error': ''}
    try:
        client = CloudflareClient()
        zone_id = _resolve_zone_id(client, target)
        records = client.list_dns_records(zone_id=zone_id, name=target.domain, record_type=expected_type)

        result['zone_id'] = zone_id
        result['records'] = records

        if not records:
            _create_issue(run, 'dns_missing', 'critical',
                          'DNS Cloudflare manquant',
                          f'Aucun record {expected_type} trouvé pour {target.domain}.',
                          repair_code='create_cloudflare_dns_record',
                          repair_payload={
                              'zone_id': zone_id, 'record_type': expected_type,
                              'name': target.domain, 'content': expected_content,
                              'proxied': expected_proxy != 'dns_only',
                          }, can_auto_repair=True)
            return result

        record = records[0]
        wrong_content = expected_content and record.get('content') != expected_content
        expected_proxied = expected_proxy != 'dns_only'
        wrong_proxy = expected_proxy != 'auto' and record.get('proxied') != expected_proxied

        if wrong_content:
            _create_issue(run, 'dns_wrong_content', 'critical',
                          'DNS Cloudflare pointe vers la mauvaise cible',
                          f'{target.domain} pointe vers {record.get("content")} au lieu de {expected_content}.',
                          repair_code='update_cloudflare_dns_record',
                          repair_payload={
                              'zone_id': zone_id, 'record_id': record.get('id'),
                              'record_type': expected_type, 'name': target.domain,
                              'content': expected_content, 'proxied': record.get('proxied', True),
                          }, can_auto_repair=True)

        if wrong_proxy:
            _create_issue(run, 'cloudflare_proxy', 'warning',
                          'Proxy Cloudflare incorrect',
                          f'Proxy actuel={record.get("proxied")}, attendu={expected_proxied}.',
                          repair_code='update_cloudflare_proxy',
                          repair_payload={
                              'zone_id': zone_id, 'record_id': record.get('id'),
                              'proxied': expected_proxied,
                          }, can_auto_repair=True)

        result['ok'] = not wrong_content and not wrong_proxy
        return result

    except CloudflareAPIError as exc:
        result['error'] = str(exc)
        _create_issue(run, 'dns_missing', 'warning',
                      'Impossible de vérifier Cloudflare', str(exc), can_auto_repair=False)
        return result


def check_cloudflare_ssl(run):
    target = run.target
    result = {'ok': False, 'ssl_mode': '', 'error': ''}
    try:
        client = CloudflareClient()
        zone_id = _resolve_zone_id(client, target)
        ssl_mode = client.get_ssl_mode(zone_id)
        result['ssl_mode'] = ssl_mode

        if target.expected_ssl_mode and ssl_mode != target.expected_ssl_mode:
            _create_issue(run, 'cloudflare_ssl', 'warning',
                          'Mode SSL Cloudflare incorrect',
                          f'Mode actuel={ssl_mode}, attendu={target.expected_ssl_mode}.',
                          repair_code='set_cloudflare_ssl_mode',
                          repair_payload={'zone_id': zone_id, 'value': target.expected_ssl_mode},
                          can_auto_repair=True)
            return result

        result['ok'] = True
        return result

    except CloudflareAPIError as exc:
        result['error'] = str(exc)
        _create_issue(run, 'cloudflare_ssl', 'warning',
                      'Impossible de vérifier le SSL Cloudflare', str(exc), can_auto_repair=False)
        return result


def check_local_dns(run):
    target = run.target
    expected_ip = str(target.expected_origin_ip or getattr(settings, 'ORION_EXPECTED_ORIGIN_IP', '') or '')
    ok, ips = domain_points_to_expected_ip(target.domain, expected_ip)

    if expected_ip and not ok:
        _create_issue(run, 'dns_wrong_content', 'warning',
                      'Résolution DNS locale inattendue',
                      f'{target.domain} résout vers {ips}, attendu {expected_ip}. '
                      f'Propagation DNS en cours ou record incorrect.',
                      can_auto_repair=False)

    return {'ok': ok, 'resolved_ips': ips, 'expected_ip': expected_ip}


def check_http(run):
    target = run.target
    result = check_http_https(target.domain)
    https = result.get('https', {})

    if not https.get('ok'):
        _create_issue(run, 'https_error', 'critical',
                      'HTTPS ne répond pas correctement',
                      f'Erreur HTTPS : {https.get("error") or https.get("status_code")}',
                      can_auto_repair=False)
    elif target.expected_https_status and https.get('status_code') != target.expected_https_status:
        _create_issue(run, 'http_error', 'warning',
                      'Statut HTTPS inattendu',
                      f'Statut reçu={https.get("status_code")}, attendu={target.expected_https_status}.',
                      can_auto_repair=False)

    return result


def check_nginx(run):
    target = run.target
    result = check_nginx_server_name(target.domain)
    if not result.get('found'):
        _create_issue(run, 'nginx_missing', 'warning',
                      'Configuration Nginx introuvable',
                      f'Aucun fichier Nginx actif ne contient {target.domain}.',
                      repair_code='generate_nginx_vhost',
                      repair_payload={'domain': target.domain, 'brand_key': target.brand_key},
                      can_auto_repair=False)
    return result


# ── Orchestrateur ────────────────────────────────────────────────────────────

def run_domain_diagnostic(target, user=None):
    run = DomainDiagnosticRun.objects.create(
        company=target.company,
        target=target,
        created_by=user,
    )

    # Archiver les anciens problèmes ouverts
    from apps.domain_diagnostics.models import DomainIssue
    DomainIssue.objects.filter(company=target.company, target=target, status='open').update(status='ignored')

    raw_results = {
        'website_link':   check_website_link(run),
        'local_dns':      check_local_dns(run),
        'cloudflare_dns': check_cloudflare_dns(run),
        'cloudflare_ssl': check_cloudflare_ssl(run),
        'http':           check_http(run),
        'nginx':          check_nginx(run),
    }

    open_issues = run.issues.filter(status='open')
    if open_issues.filter(severity='critical').exists():
        status, summary = 'error', 'Des problèmes critiques ont été détectés.'
    elif open_issues.exists():
        status, summary = 'warning', 'Des avertissements ont été détectés.'
    else:
        status, summary = 'ok', 'Aucun problème détecté.'

    run.finish(status=status, summary=summary, raw_results=raw_results)

    target.last_scan_at = timezone.now()
    target.last_status = status
    target.save(update_fields=['last_scan_at', 'last_status', 'updated_at'])

    return run
