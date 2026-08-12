from django.conf import settings

from apps.domain_diagnostics.cloudflare import CloudflareClient
from apps.domain_diagnostics.models import DomainRepairLog


class RepairError(Exception):
    pass


def _log(issue, status, message, user=None, payload=None):
    return DomainRepairLog.objects.create(
        company=issue.company,
        issue=issue,
        target=issue.target,
        repair_code=issue.repair_code,
        status=status,
        message=message,
        payload=payload or {},
        executed_by=user,
    )


def repair_create_cloudflare_dns_record(issue, user=None):
    if not getattr(settings, 'ORION_DOMAIN_AUTO_REPAIR_DNS', False):
        raise RepairError('Correction DNS automatique désactivée (ORION_DOMAIN_AUTO_REPAIR_DNS=false).')
    p = issue.repair_payload
    result = CloudflareClient().create_dns_record(
        zone_id=p['zone_id'], record_type=p['record_type'],
        name=p['name'], content=p['content'], proxied=p.get('proxied', True),
    )
    issue.mark_fixed()
    _log(issue, 'success', 'DNS record créé.', user=user, payload=result or {})
    return result


def repair_update_cloudflare_dns_record(issue, user=None):
    if not getattr(settings, 'ORION_DOMAIN_AUTO_REPAIR_DNS', False):
        raise RepairError('Correction DNS automatique désactivée (ORION_DOMAIN_AUTO_REPAIR_DNS=false).')
    p = issue.repair_payload
    result = CloudflareClient().update_dns_record(
        zone_id=p['zone_id'], record_id=p['record_id'],
        record_type=p['record_type'], name=p['name'],
        content=p['content'], proxied=p.get('proxied', True),
    )
    issue.mark_fixed()
    _log(issue, 'success', 'DNS record corrigé.', user=user, payload=result or {})
    return result


def repair_update_cloudflare_proxy(issue, user=None):
    if not getattr(settings, 'ORION_DOMAIN_AUTO_REPAIR_DNS', False):
        raise RepairError('Correction proxy automatique désactivée (ORION_DOMAIN_AUTO_REPAIR_DNS=false).')
    p = issue.repair_payload
    result = CloudflareClient().patch_dns_record(
        zone_id=p['zone_id'], record_id=p['record_id'], proxied=p['proxied'],
    )
    issue.mark_fixed()
    _log(issue, 'success', 'Proxy Cloudflare corrigé.', user=user, payload=result or {})
    return result


def repair_set_cloudflare_ssl_mode(issue, user=None):
    if not getattr(settings, 'ORION_DOMAIN_AUTO_REPAIR_SSL', False):
        raise RepairError('Correction SSL automatique désactivée (ORION_DOMAIN_AUTO_REPAIR_SSL=false).')
    p = issue.repair_payload
    result = CloudflareClient().set_ssl_mode(zone_id=p['zone_id'], value=p['value'])
    issue.mark_fixed()
    _log(issue, 'success', 'Mode SSL Cloudflare corrigé.', user=user, payload=result or {})
    return result


def repair_sync_website_domain(issue, user=None):
    p = issue.repair_payload
    from apps.websites.models import Website
    website = Website.objects.filter(id=p.get('website_id'), company=issue.company).first()
    if not website:
        raise RepairError('Website introuvable.')
    website.domain = p['domain']
    website.save(update_fields=['domain', 'updated_at'])
    issue.mark_fixed()
    _log(issue, 'success', 'Domaine Website synchronisé.', user=user, payload=p)
    return {'website_id': website.id, 'domain': website.domain}


REPAIR_HANDLERS = {
    'create_cloudflare_dns_record': repair_create_cloudflare_dns_record,
    'update_cloudflare_dns_record': repair_update_cloudflare_dns_record,
    'update_cloudflare_proxy':      repair_update_cloudflare_proxy,
    'set_cloudflare_ssl_mode':      repair_set_cloudflare_ssl_mode,
    'sync_website_domain':          repair_sync_website_domain,
}


def execute_repair(issue, user=None):
    if not issue.can_auto_repair:
        raise RepairError('Cette correction ne peut pas être automatisée.')
    handler = REPAIR_HANDLERS.get(issue.repair_code)
    if not handler:
        raise RepairError(f'Aucun handler de réparation pour : {issue.repair_code}')
    try:
        return handler(issue, user=user)
    except RepairError:
        raise
    except Exception as exc:
        _log(issue, 'failed', str(exc), user=user, payload=issue.repair_payload)
        raise
