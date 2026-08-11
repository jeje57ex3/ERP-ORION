"""
apps/websites/domain_services.py — Gestion des domaines personnalisés
"""
import secrets
import hashlib
import re
from django.utils import timezone


def generate_verification_token(domain: str) -> str:
    """Génère un token de vérification unique pour un domaine."""
    raw = f'{domain}-{secrets.token_hex(16)}'
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def normalize_domain(domain: str) -> str:
    """Normalise un nom de domaine (minuscules, sans http/www en tête optionnel)."""
    domain = domain.strip().lower()
    for prefix in ('https://', 'http://', 'www.'):
        if domain.startswith(prefix):
            domain = domain[len(prefix):]
    return domain.rstrip('/')


def validate_domain_format(domain: str) -> tuple[bool, str]:
    """Valide le format d'un nom de domaine. Retourne (valide, message)."""
    domain = normalize_domain(domain)
    if not domain:
        return False, 'Le domaine est vide.'
    if len(domain) > 253:
        return False, 'Le domaine est trop long (max 253 caractères).'
    pattern = re.compile(
        r'^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$'
    )
    if not pattern.match(domain):
        return False, 'Format de domaine invalide.'
    return True, ''


def get_expected_dns_records(website_domain) -> dict:
    """Retourne les enregistrements DNS attendus pour un domaine."""
    from django.conf import settings
    public_ip   = getattr(settings, 'ORION_PUBLIC_IP',   '0.0.0.0')
    sites_cname = getattr(settings, 'ORION_SITES_CNAME', 'sites.orion-erp.com')

    domain = website_domain.domain
    parts = domain.split('.', 1)
    is_subdomain = len(parts) > 1 and '.' in parts[1]

    if is_subdomain or website_domain.domain_type == 'subdomain':
        subdomain_label = parts[0] if len(parts) > 1 else domain
        return {
            'primary': {
                'type': 'CNAME',
                'name': subdomain_label,
                'value': website_domain.expected_cname or sites_cname,
                'description': 'Pointez votre sous-domaine vers le serveur Orion ERP.',
            },
            'verification': {
                'type': 'TXT',
                'name': '_orion-verification',
                'value': f'orion-verification={website_domain.verification_token}',
                'description': 'Enregistrement de vérification de propriété.',
            },
        }
    else:
        return {
            'primary': {
                'type': 'A',
                'name': '@',
                'value': public_ip,
                'description': f'Pointez votre domaine racine vers l\'IP du serveur Orion ERP ({public_ip}).',
            },
            'www': {
                'type': 'CNAME',
                'name': 'www',
                'value': domain,
                'description': 'Alias www vers votre domaine racine.',
            },
            'verification': {
                'type': 'TXT',
                'name': '_orion-verification',
                'value': f'orion-verification={website_domain.verification_token}',
                'description': 'Enregistrement de vérification de propriété.',
            },
        }


def check_dns_record(website_domain) -> dict:
    """
    Vérifie les enregistrements DNS pour un domaine.
    Utilise dnspython si disponible, sinon simule la structure.
    """
    result = {
        'verified': False,
        'error': None,
        'details': {},
    }
    try:
        import dns.resolver
        domain = website_domain.domain

        if website_domain.domain_type in ('subdomain', 'temporary'):
            try:
                answers = dns.resolver.resolve(domain, 'CNAME')
                cname_val = str(answers[0].target).rstrip('.')
                expected = (website_domain.expected_cname or 'sites.orion-erp.com').rstrip('.')
                result['details']['cname'] = {
                    'expected': expected,
                    'found': cname_val,
                    'ok': cname_val == expected,
                }
                result['verified'] = cname_val == expected
            except Exception as e:
                result['error'] = f'CNAME non trouvé : {e}'
        else:
            try:
                txt_name = f'_orion-verification.{domain}'
                answers = dns.resolver.resolve(txt_name, 'TXT')
                expected_txt = f'orion-verification={website_domain.verification_token}'
                found_txts = [str(r).strip('"') for r in answers]
                found = any(t == expected_txt for t in found_txts)
                result['details']['txt'] = {
                    'expected': expected_txt,
                    'found': found_txts,
                    'ok': found,
                }
                result['verified'] = found
            except Exception as e:
                result['error'] = f'TXT non trouvé : {e}'
    except ImportError:
        result['error'] = 'dnspython non installé. Vérification DNS manuelle requise.'
        result['manual_check_required'] = True

    return result


def verify_domain_ownership(website_domain) -> bool:
    """
    Vérifie la propriété du domaine et met à jour le modèle.
    Retourne True si vérifié avec succès.
    """
    result = check_dns_record(website_domain)
    website_domain.last_checked_at = timezone.now()

    if result['verified']:
        website_domain.dns_verified = True
        website_domain.dns_verified_at = timezone.now()
        website_domain.status = 'dns_verified'
        website_domain.last_error = ''
    else:
        website_domain.dns_verified = False
        website_domain.last_error = result.get('error', 'Vérification échouée.')
        if website_domain.status not in ('active', 'error'):
            website_domain.status = 'dns_pending'

    website_domain.save(update_fields=[
        'dns_verified', 'dns_verified_at', 'status', 'last_error', 'last_checked_at'
    ])
    return result['verified']


def set_primary_domain(website_domain) -> None:
    """Définit un domaine comme domaine principal du site."""
    if website_domain.website_id:
        website_domain.website.domains.update(is_primary=False)
    website_domain.is_primary = True
    website_domain.save(update_fields=['is_primary'])


def disable_domain(website_domain) -> None:
    """Désactive un domaine."""
    website_domain.status = 'disabled'
    website_domain.save(update_fields=['status'])


def get_website_by_host(host: str):
    """Trouve le site web correspondant à un host HTTP."""
    from apps.websites.models import WebsiteDomain, Website
    host = normalize_domain(host)
    domain = WebsiteDomain.objects.filter(
        domain=host, status='active', website__is_active=True
    ).select_related('website').first()
    if domain:
        return domain.website
    domain = WebsiteDomain.objects.filter(
        domain=host, dns_verified=True, website__is_active=True
    ).select_related('website').first()
    if domain:
        return domain.website
    return None


def create_domain(company, website, domain: str, target_type: str = 'website',
                  domain_type: str = 'subdomain', created_by=None):
    """
    Crée un WebsiteDomain avec token de vérification.
    Retourne l'instance créée ou lève ValueError si invalide / doublon.
    """
    from apps.websites.models import WebsiteDomain

    domain = normalize_domain(domain)
    valid, err = validate_domain_format(domain)
    if not valid:
        raise ValueError(err)

    if WebsiteDomain.objects.filter(domain=domain).exists():
        raise ValueError(f'Le domaine « {domain} » est déjà utilisé dans Orion ERP.')

    token = generate_verification_token(domain)
    wd = WebsiteDomain.objects.create(
        company=company,
        website=website,
        domain=domain,
        domain_type=domain_type,
        target_type=target_type,
        verification_token=token,
        expected_txt_record=f'orion-verification={token}',
        status='pending',
        created_by=created_by,
    )
    log_domain_action(wd, 'created', f'Domaine {domain} ajouté.', 'info', created_by)
    return wd


def build_public_url(website_domain) -> str:
    """Construit l'URL publique d'un domaine (http ou https selon SSL)."""
    if not website_domain or not website_domain.domain:
        return ''
    scheme = 'https' if website_domain.ssl_enabled or getattr(website_domain, 'force_https', False) else 'http'
    return f'{scheme}://{website_domain.domain}'


def get_domain_connection_status(website_domain) -> dict:
    """
    Retourne le statut de connexion complet d'un domaine.
    Utilisé pour le dashboard et l'API.
    """
    d = website_domain
    return {
        'domain':          d.domain,
        'status':          d.status,
        'status_label':    d.get_status_display(),
        'dns_verified':    d.dns_verified,
        'ssl_enabled':     d.ssl_enabled,
        'ssl_status':      d.ssl_status,
        'is_primary':      d.is_primary,
        'target_type':     getattr(d, 'target_type', 'website'),
        'public_url':      build_public_url(d),
        'last_checked_at': d.last_checked_at.isoformat() if d.last_checked_at else None,
        'last_error':      d.last_error,
    }


def log_domain_action(website_domain, action: str, message: str,
                      status: str = 'info', user=None) -> None:
    """Logue une action dans DomainConnectionLog."""
    try:
        from apps.websites.models_domains import DomainConnectionLog
        DomainConnectionLog.objects.create(
            company=website_domain.company,
            domain=website_domain,
            domain_name=website_domain.domain,
            action=action,
            message=message,
            status=status,
            created_by=user,
        )
    except Exception:
        pass
