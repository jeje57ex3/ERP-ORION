from django.db import transaction

from apps.domain_manager.dns_service import detect_domain_type, normalize_domain, verify_domain_dns
from apps.domain_manager.models import CustomDomain
from apps.domain_manager.ssl_service import verify_domain_ssl


@transaction.atomic
def create_custom_domain(*, company, user, domain, brand_key='', target_type='shop'):
    domain = normalize_domain(domain)
    domain_type = detect_domain_type(domain)

    custom_domain = CustomDomain.objects.create(
        company=company,
        domain=domain,
        brand_key=brand_key,
        target_type=target_type,
        domain_type=domain_type,
        created_by=user,
        status='pending',
    )
    return custom_domain


def verify_custom_domain(custom_domain):
    dns_result = verify_domain_dns(custom_domain)
    ssl_result = None

    if dns_result['valid']:
        ssl_result = verify_domain_ssl(custom_domain)

    return {
        'dns': dns_result,
        'ssl': ssl_result,
        'domain_status': custom_domain.status,
    }


@transaction.atomic
def make_primary_domain(custom_domain):
    CustomDomain.objects.filter(
        company=custom_domain.company,
        brand_key=custom_domain.brand_key,
        target_type=custom_domain.target_type,
    ).update(is_primary=False)

    custom_domain.is_primary = True
    custom_domain.save(update_fields=['is_primary', 'updated_at'])
    return custom_domain
