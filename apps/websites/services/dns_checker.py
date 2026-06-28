"""
apps/websites/services/dns_checker.py — Vérification DNS des domaines Orion ERP

Installe dnspython si nécessaire : pip install dnspython
"""
from django.conf import settings
from django.utils import timezone


def _get_setting(key: str, default: str) -> str:
    return getattr(settings, key, default)


def check_a_record(domain: str, expected_ip: str) -> dict:
    """Vérifie l'enregistrement A (IPv4) d'un domaine."""
    result = {'ok': False, 'found': [], 'expected': expected_ip, 'error': None}
    try:
        import dns.resolver
        answers = dns.resolver.resolve(domain, 'A')
        ips = [str(r) for r in answers]
        result['found'] = ips
        result['ok'] = expected_ip in ips
    except ImportError:
        result['error'] = 'dnspython non installé — pip install dnspython'
    except Exception as e:
        result['error'] = str(e)
    return result


def check_cname_record(domain: str, expected_cname: str) -> dict:
    """Vérifie l'enregistrement CNAME d'un domaine."""
    result = {'ok': False, 'found': None, 'expected': expected_cname, 'error': None}
    try:
        import dns.resolver
        answers = dns.resolver.resolve(domain, 'CNAME')
        cname_val = str(answers[0].target).rstrip('.')
        expected = expected_cname.rstrip('.')
        result['found'] = cname_val
        result['ok'] = cname_val == expected
    except ImportError:
        result['error'] = 'dnspython non installé — pip install dnspython'
    except Exception as e:
        result['error'] = str(e)
    return result


def check_txt_record(domain: str, expected_txt: str) -> dict:
    """Vérifie un enregistrement TXT (propriété ou vérification)."""
    result = {'ok': False, 'found': [], 'expected': expected_txt, 'error': None}
    try:
        import dns.resolver
        answers = dns.resolver.resolve(domain, 'TXT')
        txts = [str(r).strip('"') for r in answers]
        result['found'] = txts
        result['ok'] = any(t == expected_txt for t in txts)
    except ImportError:
        result['error'] = 'dnspython non installé — pip install dnspython'
    except Exception as e:
        result['error'] = str(e)
    return result


def check_domain_records(domain_obj) -> dict:
    """
    Vérifie tous les enregistrements DNS nécessaires d'un WebsiteDomain.
    Met à jour les DomainDNSRecord associés.

    Retourne:
        {
          'domain': str,
          'verified': bool,
          'details': { 'cname': {...}, 'a_record': {...}, 'txt_verification': {...} },
          'error': str | None,
          'manual_check_required': bool,
        }
    """
    try:
        import dns.resolver  # noqa — vérifie la disponibilité
    except ImportError:
        return {
            'domain': domain_obj.domain,
            'verified': False,
            'details': {},
            'error': 'dnspython non installé. Installez-le : pip install dnspython',
            'manual_check_required': True,
        }

    public_ip    = _get_setting('ORION_PUBLIC_IP', '0.0.0.0')
    sites_cname  = _get_setting('ORION_SITES_CNAME', 'sites.orion-erp.com')
    verif_prefix = _get_setting('ORION_DOMAIN_VERIFICATION_PREFIX', 'orion-verification')

    domain      = domain_obj.domain
    token       = domain_obj.verification_token
    domain_type = domain_obj.domain_type
    expected_txt = f'{verif_prefix}={token}'
    txt_name     = f'_{verif_prefix}.{domain}'

    results = {
        'domain': domain,
        'verified': False,
        'details': {},
        'error': None,
        'manual_check_required': False,
    }

    if domain_type == 'subdomain':
        expected_cname = domain_obj.expected_cname or sites_cname
        cname_res = check_cname_record(domain, expected_cname)
        txt_res   = check_txt_record(txt_name, expected_txt)
        results['details']['cname']            = cname_res
        results['details']['txt_verification'] = txt_res
        results['verified'] = cname_res['ok']  # TXT optionnel pour sous-domaines

    elif domain_type == 'root':
        a_res   = check_a_record(domain, public_ip)
        www_res = check_cname_record(f'www.{domain}', domain)
        txt_res = check_txt_record(txt_name, expected_txt)
        results['details']['a_record']         = a_res
        results['details']['www_cname']        = www_res
        results['details']['txt_verification'] = txt_res
        results['verified'] = a_res['ok'] and txt_res['ok']

    else:
        txt_res = check_txt_record(txt_name, expected_txt)
        results['details']['txt_verification'] = txt_res
        results['verified'] = txt_res['ok']

    # Mise à jour des DomainDNSRecord en base
    _sync_dns_records(domain_obj, results['details'])

    return results


def _sync_dns_records(domain_obj, details: dict) -> None:
    """Met à jour les DomainDNSRecord en base après une vérification."""
    try:
        from apps.websites.models_domains import DomainDNSRecord

        type_map = {
            'a_record':         ('A',     '@'),
            'www_cname':        ('CNAME', 'www'),
            'cname':            ('CNAME', _subdomain_label(domain_obj.domain)),
            'txt_verification': ('TXT',   f'_orion-verification'),
        }

        for key, check in details.items():
            if key not in type_map:
                continue
            rtype, rname = type_map[key]
            expected = check.get('expected', '')
            found    = check.get('found')
            if isinstance(found, list):
                found = ', '.join(found)
            status = 'valid' if check.get('ok') else ('missing' if not found else 'invalid')

            DomainDNSRecord.objects.update_or_create(
                domain=domain_obj,
                record_type=rtype,
                name=rname,
                defaults={
                    'expected_value': expected,
                    'detected_value': found or '',
                    'status': status,
                    'last_checked_at': timezone.now(),
                },
            )
    except Exception:
        pass


def _subdomain_label(full_domain: str) -> str:
    """Extrait le label du sous-domaine (ex: 'boutique' de 'boutique.monsite.fr')."""
    parts = full_domain.split('.', 1)
    return parts[0] if len(parts) > 1 else full_domain
