"""
apps/websites/middleware.py — Résolution de site web par domaine HTTP

Ce middleware identifie si la requête entrante correspond à un site web public
d'Orion ERP (via le host HTTP) et attache request.website si trouvé.

Il ne redirige PAS les pages ERP internes. Il se contente d'annoter la requête.
Les vues publiques (public_views.py) utilisent ensuite request.website.
"""
from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin

# Hosts internes ERP — ne pas résoudre ces hosts comme sites publics
INTERNAL_HOSTS = {
    'localhost',
    '127.0.0.1',
    'erp.local',
    'orion.local',
    'testserver',
}


def _is_internal_host(host: str) -> bool:
    """Retourne True si le host correspond à une interface ERP interne."""
    if not host:
        return True
    host_clean = host.split(':')[0].lower()
    if host_clean in INTERNAL_HOSTS:
        return True
    if host_clean.endswith('.local') or host_clean.endswith('.internal'):
        return True
    return False


class WebsiteResolverMiddleware(MiddlewareMixin):
    """
    Résout le site web correspondant au host HTTP entrant.

    - Si le host est un domaine ERP interne → request.website = None
    - Si un WebsiteDomain actif correspond → request.website = website instance
    - Si le site est en maintenance → retourne la page de maintenance
    - Si le site n'est pas publié → request.website = None (ou page 404)
    """

    def process_request(self, request):
        request.website = None
        request.website_company = None

        host = request.get_host()
        if _is_internal_host(host):
            return None

        try:
            from apps.websites.domain_services import get_website_by_host, normalize_domain
            website = get_website_by_host(host)
        except Exception:
            return None

        if website is None:
            return None

        # Mode maintenance
        if website.maintenance_mode:
            company = website.company
            request.website = website
            request.website_company = company
            try:
                from django.template.loader import render_to_string
                from django.template import RequestContext
                html = render_to_string(
                    'websites/public/maintenance.html',
                    {'site': website, 'company': company},
                    request=request,
                )
                return HttpResponse(html, status=503)
            except Exception:
                return HttpResponse(
                    '<h1>Ce site est en maintenance.</h1>',
                    content_type='text/html',
                    status=503,
                )

        # Site non publié : laisser passer pour que la vue gère le 404
        if not website.is_published or website.status != 'published':
            return None

        request.website = website
        request.website_company = website.company
        return None
