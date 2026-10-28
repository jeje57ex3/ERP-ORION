"""
apps/site_customization/public_api.py — API publique CMS pour SIÈCLE / LUNEA.

Endpoints (montés sous /api/v1/public/<site_slug>/) :
  GET /api/v1/public/<site_slug>/theme/
  GET /api/v1/public/<site_slug>/pages/home/
  GET /api/v1/public/<site_slug>/pages/<slug>/
  GET /api/v1/public/<site_slug>/pages/

Règle absolue : ne jamais exposer les pages/thèmes non publiés.
"""
from django.http import JsonResponse
from django.views import View

from apps.websites.models import Website
from .models import SitePageCustomization, SitePageSection, SiteContentBlock, SiteThemeSettings
from .selectors import get_public_page, get_published_theme
from .services import build_theme_css


def _get_active_website(site_slug: str):
    """Retourne le site actif correspondant au slug, ou None."""
    return Website.objects.filter(slug=site_slug, is_active=True).first()


def _serialize_block(block: SiteContentBlock) -> dict:
    return {
        'id':         block.pk,
        'block_type': block.block_type,
        'title':      block.title,
        'content':    block.content,
        'image':      block.image.url if block.image else None,
        'link_label': block.link_label,
        'link_url':   block.link_url,
        'position':   block.position,
        'extra_data': block.extra_data,
    }


def _serialize_section(section: SitePageSection) -> dict:
    return {
        'id':               section.pk,
        'section_type':     section.section_type,
        'title':            section.title,
        'subtitle':         section.subtitle,
        'image':            section.image.url if section.image else None,
        'content':          section.content,
        'custom_html':      section.custom_html,
        'cta_label':        section.cta_label,
        'cta_url':          section.cta_url,
        'position':         section.position,
        'background_color': section.background_color,
        'text_color':       section.text_color,
        'blocks':           [
            _serialize_block(b)
            for b in section.blocks.filter(is_visible=True).order_by('position')
        ],
    }


def _serialize_page(page: SitePageCustomization) -> dict:
    return {
        'id':              page.pk,
        'page_type':       page.page_type,
        'title':           page.title,
        'slug':            page.slug,
        'seo_title':       page.seo_title,
        'seo_description': page.seo_description,
        'hero_title':      page.hero_title,
        'hero_subtitle':   page.hero_subtitle,
        'hero_image':      page.hero_image.url if page.hero_image else None,
        'cta_label':       page.cta_label,
        'cta_url':         page.cta_url,
        'published_at':    page.published_at.isoformat() if page.published_at else None,
        'sections':        [
            _serialize_section(s)
            for s in page.sections.filter(is_visible=True).order_by('position')
        ],
    }


class PublicThemeView(View):
    """GET /api/v1/public/<site_slug>/theme/"""

    def get(self, request, site_slug):
        website = _get_active_website(site_slug)
        if not website:
            return JsonResponse({'detail': 'Site introuvable ou inactif.'}, status=404)

        theme = get_published_theme(website)
        if not theme:
            return JsonResponse({
                'site_slug': site_slug,
                'published': False,
                'colors': {},
                'fonts': {},
                'radii': {},
                'logo': None,
                'logo_dark': None,
                'favicon': None,
                'css': '',
                'head_scripts': '',
                'body_scripts': '',
            })

        return JsonResponse({
            'site_slug': site_slug,
            'published': True,
            'colors': {
                'primary':    theme.primary_color,
                'secondary':  theme.secondary_color,
                'background': theme.background_color,
                'surface':    theme.surface_color,
                'text':       theme.text_color,
                'muted':      theme.muted_text_color,
            },
            'fonts': {
                'family': theme.font_family,
            },
            'radii': {
                'border': theme.border_radius,
                'button': theme.button_radius,
            },
            'logo':         theme.logo.url     if theme.logo      else None,
            'logo_dark':    theme.logo_dark.url if theme.logo_dark else None,
            'favicon':      theme.favicon.url   if theme.favicon   else None,
            'css':          build_theme_css(theme),
            'head_scripts': theme.head_scripts,
            'body_scripts': theme.body_scripts,
        })


class PublicPageView(View):
    """
    GET /api/v1/public/<site_slug>/pages/home/     → page marquée is_homepage
    GET /api/v1/public/<site_slug>/pages/<slug>/   → page par slug
    """

    def get(self, request, site_slug, slug):
        website = _get_active_website(site_slug)
        if not website:
            return JsonResponse({'detail': 'Site introuvable ou inactif.'}, status=404)

        if slug == 'home':
            page = get_public_page(website, homepage=True)
        else:
            page = get_public_page(website, slug=slug)

        if not page:
            return JsonResponse({'detail': 'Page introuvable ou non publiée.'}, status=404)

        return JsonResponse({
            'site_slug': site_slug,
            'page': _serialize_page(page),
        })


class PublicPageListView(View):
    """GET /api/v1/public/<site_slug>/pages/ → liste des pages publiées (sans sections)."""

    def get(self, request, site_slug):
        website = _get_active_website(site_slug)
        if not website:
            return JsonResponse({'detail': 'Site introuvable ou inactif.'}, status=404)

        pages = SitePageCustomization.objects.filter(
            website=website, status='published',
        ).order_by('page_type', 'title')

        return JsonResponse({
            'site_slug': site_slug,
            'pages': [
                {
                    'id':          p.pk,
                    'page_type':   p.page_type,
                    'title':       p.title,
                    'slug':        p.slug,
                    'is_homepage': p.is_homepage,
                    'seo_title':   p.seo_title,
                }
                for p in pages
            ],
            'count': pages.count(),
        })
