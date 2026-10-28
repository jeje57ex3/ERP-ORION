import socket
import ssl
from datetime import datetime, timezone as dt_timezone

from django.utils import timezone


def check_ssl_certificate(domain):
    context = ssl.create_default_context()
    try:
        with socket.create_connection((domain, 443), timeout=5) as sock:
            with context.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()

        not_after = cert.get('notAfter')
        expires_at = datetime.strptime(not_after, '%b %d %H:%M:%S %Y %Z')
        expires_at = expires_at.replace(tzinfo=dt_timezone.utc)
        is_valid = expires_at > datetime.now(dt_timezone.utc)

        return {
            'valid': is_valid,
            'expires_at': expires_at.isoformat(),
            'issuer': cert.get('issuer'),
            'subject': cert.get('subject'),
            'error': '',
        }
    except Exception as exc:
        return {
            'valid': False,
            'expires_at': None,
            'issuer': None,
            'subject': None,
            'error': str(exc),
        }


def verify_domain_ssl(custom_domain):
    result = check_ssl_certificate(custom_domain.domain)

    custom_domain.ssl_is_valid = result['valid']
    custom_domain.last_ssl_check_at = timezone.now()

    if result['valid'] and custom_domain.dns_is_valid:
        custom_domain.status = 'active'
        custom_domain.last_error = ''
    elif not result['valid']:
        custom_domain.status = 'ssl_pending'
        custom_domain.last_error = result['error']

    custom_domain.save(update_fields=[
        'ssl_is_valid', 'last_ssl_check_at', 'status', 'last_error', 'updated_at',
    ])

    return result
