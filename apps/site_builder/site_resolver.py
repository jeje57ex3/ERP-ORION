"""
apps/site_builder/site_resolver.py — Résout les vrais Website existants pour le builder.

Règle absolue : ne jamais créer de Website ici. Uniquement lire.
"""
from apps.websites.models import Website


class SiteResolverError(Exception):
    pass


def get_real_website_for_brand(company, brand_slug: str) -> Website:
    """
    Retourne le vrai Website existant correspondant au slug de marque.
    Lève SiteResolverError si introuvable — ne crée jamais de site.
    """
    website = Website.objects.filter(
        company=company,
        slug=brand_slug,
        is_active=True,
    ).first()

    if not website:
        raise SiteResolverError(
            f"Site réel introuvable pour slug='{brand_slug}'. "
            "Allez dans Sites web > Mes sites et vérifiez que le site existe et est actif."
        )

    return website


def get_real_siecle_website(company) -> Website:
    return get_real_website_for_brand(company, 'siecle')


def get_real_lunea_website(company) -> Website:
    return get_real_website_for_brand(company, 'lunea')
