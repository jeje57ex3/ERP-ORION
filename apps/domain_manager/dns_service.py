from django.conf import settings
from django.utils import timezone

try:
    import dns.resolver
    DNSPYTHON_AVAILABLE = True
except ImportError:
    DNSPYTHON_AVAILABLE = False


def normalize_domain(domain):
    domain = str(domain or '').strip().lower()
    domain = domain.replace('https://', '').replace('http://', '')
    domain = domain.split('/')[0]
    return domain.strip('.')


def detect_domain_type(domain):
    domain = normalize_domain(domain)
    if domain.startswith('www.'):
        return 'www'
    parts = domain.split('.')
    if len(parts) > 2:
        return 'subdomain'
    return 'root'


def resolve_records(domain, record_type):
    if not DNSPYTHON_AVAILABLE:
        return []
    try:
        answers = dns.resolver.resolve(domain, record_type)
        return [str(answer).rstrip('.') for answer in answers]
    except Exception:
        return []


def check_a_record(domain, expected_ip):
    records = resolve_records(domain, 'A')
    return expected_ip in records, records


def check_cname_record(domain, expected_cname):
    records = resolve_records(domain, 'CNAME')
    expected_cname = str(expected_cname or '').rstrip('.')
    return expected_cname in records, records


def check_txt_record(name, expected_value):
    records = resolve_records(name, 'TXT')
    cleaned = [r.replace('"', '') for r in records]
    return expected_value in cleaned, cleaned


def verify_domain_dns(custom_domain):
    domain = normalize_domain(custom_domain.domain)

    if not DNSPYTHON_AVAILABLE:
        custom_domain.status = 'dns_pending'
        custom_domain.last_error = ''
        custom_domain.last_dns_check_at = timezone.now()
        custom_domain.save(update_fields=['status', 'last_error', 'last_dns_check_at', 'updated_at'])
        return {
            'domain': domain,
            'valid': False,
            'manual': True,
            'message': 'dnspython non disponible — vérification automatique désactivée.',
        }

    expected_ip = str(custom_domain.expected_a_record or getattr(settings, 'ORION_DOMAIN_TARGET_IP', ''))
    expected_cname = str(custom_domain.expected_cname or getattr(settings, 'ORION_DOMAIN_TARGET_CNAME', ''))

    result = {
        'domain': domain,
        'domain_type': custom_domain.domain_type,
        'a_valid': False,
        'a_records': [],
        'cname_valid': False,
        'cname_records': [],
        'txt_valid': False,
        'txt_records': [],
        'valid': False,
        'manual': False,
        'message': '',
    }

    txt_valid, txt_records = check_txt_record(
        custom_domain.expected_txt_name,
        custom_domain.expected_txt_value,
    )
    result['txt_valid'] = txt_valid
    result['txt_records'] = txt_records

    if custom_domain.domain_type in ['www', 'subdomain']:
        cname_valid, cname_records = check_cname_record(domain, expected_cname)
        result['cname_valid'] = cname_valid
        result['cname_records'] = cname_records
        result['valid'] = cname_valid and txt_valid
        if not cname_valid:
            result['message'] = f'CNAME non trouvé. Attendu : {expected_cname or "(non configuré)"}'
    else:
        if not expected_ip:
            result['message'] = 'IP cible non configurée (ORION_DOMAIN_TARGET_IP vide).'
            result['valid'] = False
        else:
            a_valid, a_records = check_a_record(domain, expected_ip)
            result['a_valid'] = a_valid
            result['a_records'] = a_records
            result['valid'] = a_valid and txt_valid
            if not a_valid:
                result['message'] = f'Record A non trouvé. Attendu : {expected_ip}'

    if result['valid']:
        result['message'] = 'DNS valides.'
        custom_domain.dns_is_valid = True
        custom_domain.status = 'dns_valid'
        custom_domain.last_error = ''
    else:
        custom_domain.dns_is_valid = False
        custom_domain.status = 'dns_pending'
        custom_domain.last_error = result['message'] or 'DNS pas encore propagés.'

    custom_domain.last_dns_check_at = timezone.now()
    custom_domain.save(update_fields=[
        'dns_is_valid', 'status', 'last_error', 'last_dns_check_at', 'updated_at',
    ])

    return result
