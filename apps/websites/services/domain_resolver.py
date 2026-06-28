"""
apps/websites/services/domain_resolver.py — Résolution rapide domaine → site/service

Utilise Django cache (300 s) pour éviter une requête BD à chaque request HTTP.
Cache key: domain_resolve:<host>
"""
from django.core.cache import cache
from django.db.models import Q

CACHE_TTL = 300   # 5 minutes
_NONE_SENTINEL = '__none__'


# ─── Fonctions publiques ──────────────────────────────────────────────────────

def resolve_domain(host: str):
    """
    Résout un host HTTP vers son WebsiteDomain actif.
    Retourne l'instance WebsiteDomain ou None.
    """
    from apps.websites.models import WebsiteDomain

    host = _clean_host(host)
    if not host:
        return None

    cache_key = f'domain_resolve:{host}'
    cached_pk = cache.get(cache_key)

    if cached_pk is not None:
        if cached_pk == _NONE_SENTINEL:
            return None
        try:
            return (
                WebsiteDomain.objects
                .select_related('website', 'website__company')
                .get(pk=cached_pk)
            )
        except WebsiteDomain.DoesNotExist:
            cache.delete(cache_key)

    domain_obj = (
        WebsiteDomain.objects
        .filter(domain=host)
        .filter(Q(status='active') | Q(dns_verified=True, status='dns_verified'))
        .select_related('website', 'website__company')
        .first()
    )

    if domain_obj:
        cache.set(cache_key, domain_obj.pk, CACHE_TTL)
    else:
        cache.set(cache_key, _NONE_SENTINEL, CACHE_TTL)

    return domain_obj


def get_website_for_domain(host: str):
    """Retourne le site web correspondant au host, ou None."""
    domain = resolve_domain(host)
    return domain.website if domain else None


def get_company_for_domain(host: str):
    """Retourne l'entreprise correspondant au host, ou None."""
    domain = resolve_domain(host)
    if domain:
        return domain.website.company
    return None


def get_target_for_domain(host: str) -> str | None:
    """
    Retourne le target_type du domaine.
    Valeurs possibles: website, shop, client_portal, erp, landing_page, blog.
    """
    domain = resolve_domain(host)
    if domain:
        return getattr(domain, 'target_type', 'website')
    return None


def invalidate_domain_cache(host: str) -> None:
    """
    Invalide le cache de résolution pour un domaine.
    À appeler après modification / désactivation d'un WebsiteDomain.
    """
    host = _clean_host(host)
    if host:
        cache.delete(f'domain_resolve:{host}')


def preload_active_domains() -> int:
    """
    Précharge tous les domaines actifs en cache.
    Utile au démarrage du serveur ou après un déploiement.
    Retourne le nombre de domaines mis en cache.
    """
    from apps.websites.models import WebsiteDomain

    domains = (
        WebsiteDomain.objects
        .filter(Q(status='active') | Q(dns_verified=True, status='dns_verified'))
        .select_related('website', 'website__company')
    )
    count = 0
    for d in domains:
        cache.set(f'domain_resolve:{d.domain}', d.pk, CACHE_TTL)
        count += 1
    return count


# ─── Interne ──────────────────────────────────────────────────────────────────

def _clean_host(host: str) -> str:
    """Retire port et espaces, met en minuscules."""
    if not host:
        return ''
    return host.split(':')[0].strip().lower()
