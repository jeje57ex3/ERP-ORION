"""
apps/websites/services/ssl_service.py — Gestion SSL / HTTPS des domaines Orion ERP

Compatible : Certbot, Caddy, Traefik, Let's Encrypt.
La première version ne génère pas automatiquement les certificats côté serveur
(environnements variés). Elle fournit les instructions adaptées et gère les statuts.
"""
import datetime
import ssl
import socket

from django.utils import timezone


# ─── Fonctions publiques ──────────────────────────────────────────────────────

def request_ssl_certificate(domain_obj) -> dict:
    """
    Initie une demande de certificat SSL.
    Ne touche pas au serveur — enregistre le statut et retourne les instructions.
    """
    if not domain_obj.dns_verified:
        return {
            'success': False,
            'error': 'Le DNS doit être vérifié avant de demander un certificat SSL.',
        }

    domain_obj.ssl_status = 'pending'
    domain_obj.save(update_fields=['ssl_status'])

    _log(domain_obj, 'ssl_requested', 'Demande SSL initiée.', 'info')

    return {
        'success': True,
        'message': 'Demande SSL enregistrée. Suivez les instructions ci-dessous pour votre serveur.',
        'instructions': get_ssl_instructions(domain_obj),
    }


def check_ssl_certificate(domain_obj) -> dict:
    """
    Vérifie l'état réel du certificat SSL via une connexion TLS.
    Ne nécessite pas dnspython.
    """
    result = {
        'valid': False,
        'expires_at': None,
        'issuer': None,
        'error': None,
    }
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((domain_obj.domain, 443), timeout=8) as sock:
            with ctx.wrap_socket(sock, server_hostname=domain_obj.domain) as ssock:
                cert = ssock.getpeercert()
                not_after = cert.get('notAfter', '')
                if not_after:
                    expires = datetime.datetime.strptime(not_after, '%b %d %H:%M:%S %Y %Z')
                    expires = expires.replace(tzinfo=datetime.timezone.utc)
                    result['expires_at'] = expires
                    result['valid'] = expires > timezone.now()
                issuer = dict(x[0] for x in cert.get('issuer', []))
                result['issuer'] = issuer.get('organizationName', '')
    except ssl.SSLCertVerificationError as e:
        result['error'] = f'Certificat invalide : {e}'
    except ConnectionRefusedError:
        result['error'] = 'Port 443 fermé ou HTTPS non configuré sur ce serveur.'
    except Exception as e:
        result['error'] = str(e)
    return result


def renew_ssl_certificate(domain_obj) -> dict:
    """Lance le renouvellement SSL (log + retour instructions)."""
    _log(domain_obj, 'ssl_requested', 'Renouvellement SSL demandé.', 'info')
    return {
        'success': True,
        'message': 'Renouvellement planifié.',
        'instructions': get_ssl_instructions(domain_obj),
    }


def mark_ssl_active(domain_obj, expires_at=None) -> None:
    """
    Marque le SSL comme actif (appelé après configuration manuelle ou vérification positive).
    """
    domain_obj.ssl_status  = 'active'
    domain_obj.ssl_enabled = True
    domain_obj.ssl_issued_at = timezone.now()
    if expires_at:
        domain_obj.ssl_expires_at = (
            expires_at.date() if hasattr(expires_at, 'date') else expires_at
        )
    if domain_obj.dns_verified:
        domain_obj.status = 'active'
    domain_obj.save(update_fields=[
        'ssl_status', 'ssl_enabled', 'ssl_issued_at', 'ssl_expires_at', 'status',
    ])
    _log(domain_obj, 'ssl_active', 'SSL activé avec succès.', 'success')


def get_ssl_instructions(domain_obj) -> list:
    """
    Retourne les commandes/instructions adaptées pour activer SSL
    sur les principaux serveurs web / reverse proxy.
    """
    domain = domain_obj.domain
    return [
        {
            'label': 'Certbot + Nginx',
            'cmd': f'sudo certbot --nginx -d {domain} -d www.{domain}',
            'doc': 'https://certbot.eff.org/instructions?os=ubuntufocal&http=nginx',
        },
        {
            'label': 'Certbot + Apache',
            'cmd': f'sudo certbot --apache -d {domain} -d www.{domain}',
            'doc': 'https://certbot.eff.org/instructions?os=ubuntufocal&http=apache',
        },
        {
            'label': 'Caddy (automatique)',
            'cmd': f'# Caddyfile\n{domain} {{\n    reverse_proxy localhost:8000\n}}',
            'doc': 'https://caddyserver.com/docs/automatic-https',
        },
        {
            'label': 'Traefik (automatique)',
            'cmd': (
                f'# docker-compose.yml\n'
                f'labels:\n'
                f'  - "traefik.http.routers.{domain.replace(".", "-")}.rule=Host(`{domain}`)"'
            ),
            'doc': 'https://doc.traefik.io/traefik/https/acme/',
        },
    ]


def get_expiring_soon(days: int = 30):
    """Retourne les domaines dont le SSL expire dans moins de X jours."""
    from apps.websites.models import WebsiteDomain
    threshold = timezone.now().date() + datetime.timedelta(days=days)
    return WebsiteDomain.objects.filter(
        ssl_status='active',
        ssl_expires_at__isnull=False,
        ssl_expires_at__lte=threshold,
    ).select_related('website', 'website__company')


# ─── Interne ──────────────────────────────────────────────────────────────────

def _log(domain_obj, action: str, message: str, status: str = 'info') -> None:
    try:
        from apps.websites.models_domains import DomainConnectionLog
        DomainConnectionLog.objects.create(
            company=domain_obj.website.company,
            domain=domain_obj,
            domain_name=domain_obj.domain,
            action=action,
            message=message,
            status=status,
        )
    except Exception:
        pass
