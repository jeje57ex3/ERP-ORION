"""
apps/ecommerce/public_api.py — API publique générique par site boutique.

Endpoint :
  GET /api/v1/public/<site_slug>/products/
  GET /api/v1/public/<site_slug>/products/?category=<slug>

Utilise public_selectors.py comme source unique.
Ne jamais exposer les brouillons, les drops privés non autorisés,
ni les données internes ERP (company_id, ERP FK, etc.).
"""
from django.http import JsonResponse
from django.views import View

from apps.ecommerce.public_selectors import (
    get_public_products_for_site,
    get_public_categories_for_site,
)


class PublicProductListView(View):
    """GET /api/v1/public/<site_slug>/products/"""

    def get(self, request, site_slug):
        category_slug = request.GET.get('category', '').strip()

        products, website = get_public_products_for_site(
            site_slug=site_slug,
            user=request.user,
            category_slug=category_slug or None,
        )

        if website is None:
            return JsonResponse({'detail': 'Site introuvable ou inactif.'}, status=404)

        categories, _ = get_public_categories_for_site(site_slug)

        products_data = []
        for p in products:
            imgs = list(p.images.all())  # uses prefetch cache — no extra query
            img = next((i for i in imgs if i.is_primary), imgs[0] if imgs else None)
            image_url = img.image.url if (img and img.image) else None

            products_data.append({
                'id':               p.pk,
                'name':             p.name,
                'slug':             p.slug,
                'sku':              p.sku,
                'price':            str(p.price),
                'compare_at_price': str(p.compare_at_price) if p.compare_at_price else None,
                'stock_quantity':   p.stock_quantity,
                'in_stock':         p.stock_quantity > 0,
                'status':           p.status,
                'is_featured':      p.is_featured,
                'is_popular':       p.is_popular,
                'image':            image_url,
                'category':         p.category.name if p.category else None,
                'category_slug':    p.category.slug if p.category else None,
                'short_description': p.short_description,
                'url':              f'/objects/{p.slug}/' if site_slug == 'siecle' else f'/products/{p.slug}/',
            })

        categories_data = [
            {
                'id':          c.pk,
                'name':        c.name,
                'slug':        c.slug,
                'description': c.description,
                'order':       c.order,
            }
            for c in categories
        ]

        return JsonResponse({
            'site_slug': site_slug,
            'website': {
                'id':     website.pk,
                'name':   website.name,
                'domain': website.domain or '',
            },
            'categories': categories_data,
            'products': products_data,
            'count':    len(products_data),
        })
