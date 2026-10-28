"""
apps/ecommerce/public_selectors.py — Source unique publique pour les produits boutique.

Utilisé par :
- La page SIÈCLE /objects (React SPA via /api/v1/siecle/products/)
- L'API publique générique /api/v1/public/<site_slug>/products/
- Tout futur consommateur public des produits boutique

Ne jamais bypasser ce selector pour accéder aux StoreProduct en public.
SIÈCLE et LUNEA ne sont jamais mélangés : l'isolation est garantie par le FK website.
"""
from django.db.models import Q, Prefetch
from django.utils import timezone

from apps.websites.models import StoreProduct, StoreProductImage, StoreCategory, Website


def get_public_website_by_slug(slug):
    """Retourne le Website actif de type e-commerce identifié par son slug."""
    return (
        Website.objects
        .filter(slug=slug, site_type='ecommerce', is_active=True)
        .select_related('company')
        .first()
    )


def get_public_categories_for_site(site_slug):
    """
    Retourne (queryset, website) des catégories publiques actives pour un site.
    Les catégories inactives ne sont jamais exposées publiquement.
    """
    website = get_public_website_by_slug(site_slug)
    if not website:
        return StoreCategory.objects.none(), None

    categories = (
        StoreCategory.objects
        .filter(website=website, is_active=True)
        .order_by('order', 'name')
    )
    return categories, website


def get_public_products_for_site(site_slug, user=None, category_slug=None):
    """
    Retourne (queryset, website) des produits publics pour le site donné.

    Filtres appliqués :
    - status = 'published'
    - available_from vide ou déjà passé
    - drops privés masqués pour les visiteurs anonymes
    - category_slug : filtre optionnel sur la catégorie (slug)
    """
    website = get_public_website_by_slug(site_slug)
    if not website:
        return StoreProduct.objects.none(), None

    now = timezone.now()
    images_qs = StoreProductImage.objects.order_by('-is_primary', 'order')

    qs = (
        StoreProduct.objects
        .filter(website=website, status='published')
        .filter(
            Q(available_from__isnull=True) | Q(available_from__lte=now),
        )
    )

    # Drops privés masqués pour les visiteurs non authentifiés
    is_authenticated = bool(user and getattr(user, 'is_authenticated', False))
    if not is_authenticated:
        qs = qs.filter(is_private_drop=False)

    # Filtre catégorie optionnel
    if category_slug:
        qs = qs.filter(category__slug=category_slug)

    qs = (
        qs
        .select_related('category', 'website')
        .prefetch_related(Prefetch('images', queryset=images_qs))
        .order_by('-is_featured', 'display_order', '-created_at')
    )

    return qs, website


def get_public_siecle_products(user=None, category_slug=None):
    """Raccourci pour le site SIÈCLE (slug='siecle')."""
    return get_public_products_for_site('siecle', user=user, category_slug=category_slug)


def get_public_siecle_categories():
    """Raccourci pour les catégories du site SIÈCLE."""
    return get_public_categories_for_site('siecle')


def get_related_products_for_product(product, limit=4):
    """
    Produits similaires au produit donné :
    - même site (website FK)
    - statut published
    - même catégorie principale si disponible (union catégorie principale + catégorie du produit)
    - exclut le produit courant
    - préfetch images pour éviter les N+1
    """
    images_qs = StoreProductImage.objects.order_by('-is_primary', 'order')

    qs = (
        StoreProduct.objects
        .filter(website=product.website, status='published')
        .exclude(pk=product.pk)
        .select_related('category', 'website')
        .prefetch_related(Prefetch('images', queryset=images_qs))
    )

    if product.category:
        qs = qs.filter(
            Q(category=product.category)
        )

    return qs.order_by('-is_featured', 'display_order', '-created_at')[:limit]
