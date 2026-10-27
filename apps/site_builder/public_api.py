"""
apps/site_builder/public_api.py — API publique pour les pages éditées avec le builder.

Endpoints (montés sous /api/v1/public/<site_slug>/builder/) :
  GET /api/v1/public/<site_slug>/builder/pages/
  GET /api/v1/public/<site_slug>/builder/pages/home/
  GET /api/v1/public/<site_slug>/builder/pages/<slug>/

Règle absolue : ne jamais exposer les pages non publiées.
"""
from django.http import JsonResponse
from django.views import View

from apps.websites.models import Website

from .models import BuilderPage, BuilderSection
from .selectors import get_published_pages_for_website, get_published_page


def _get_active_website(site_slug: str):
    return Website.objects.filter(slug=site_slug, is_active=True).first()


def _serialize_section(section: BuilderSection) -> dict:
    return {
        'id':          section.pk,
        'module_type': section.module_type,
        'position':    section.position,
        'settings':    section.settings,
        'is_visible':  section.is_visible,
    }


def _serialize_page(page: BuilderPage, include_sections: bool = True) -> dict:
    data = {
        'id':           page.pk,
        'title':        page.title,
        'slug':         page.slug,
        'brand_key':    page.brand_key,
        'is_homepage':  page.is_homepage,
        'status':       page.status,
        'published_at': page.published_at.isoformat() if page.published_at else None,
        'meta_title':       page.meta_title,
        'meta_description': page.meta_description,
    }
    if include_sections:
        data['sections'] = [
            _serialize_section(s)
            for s in page.sections.filter(is_visible=True).order_by('position')
        ]
    return data


class PublicBuilderPageListView(View):
    """GET /api/v1/public/<site_slug>/builder/pages/"""

    def get(self, request, site_slug):
        website = _get_active_website(site_slug)
        if not website:
            return JsonResponse({'detail': 'Site introuvable ou inactif.'}, status=404)

        pages = get_published_pages_for_website(website)

        return JsonResponse({
            'site_slug': site_slug,
            'pages': [_serialize_page(p, include_sections=False) for p in pages],
            'count': pages.count(),
        })


class PublicBuilderPageView(View):
    """
    GET /api/v1/public/<site_slug>/builder/pages/home/   → homepage publiée
    GET /api/v1/public/<site_slug>/builder/pages/<slug>/ → page par slug
    """

    def get(self, request, site_slug, slug):
        website = _get_active_website(site_slug)
        if not website:
            return JsonResponse({'detail': 'Site introuvable ou inactif.'}, status=404)

        if slug == 'home':
            page = get_published_page(website, homepage=True)
        else:
            page = get_published_page(website, slug=slug)

        if not page:
            return JsonResponse({'detail': 'Page introuvable ou non publiée.'}, status=404)

        return JsonResponse({
            'site_slug': site_slug,
            'page': _serialize_page(page, include_sections=True),
        })
