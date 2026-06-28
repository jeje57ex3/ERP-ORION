"""
apps/websites/services/language_resolver.py

Resout la langue active pour un site web et retourne les contenus traduits.
Priorite : prefixe URL > parametre GET ?lang= > session > navigateur > langue par defaut du site > fr
"""
from django.utils import translation as dj_translation


def get_website_language_from_request(request, website):
    """Retourne le code langue a utiliser pour un site web donne."""
    # 1. Parametre GET ?lang=
    lang = request.GET.get('lang', '').strip()
    if lang and _is_enabled(lang, website):
        request.session[f'site_{website.pk}_lang'] = lang
        return lang

    # 2. Session specifique au site
    lang = request.session.get(f'site_{website.pk}_lang', '')
    if lang and _is_enabled(lang, website):
        return lang

    # 3. Accept-Language navigateur (si auto_redirect actif)
    try:
        if website.language_settings.auto_redirect_by_browser:
            accept = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
            for part in accept.split(','):
                code = part.strip().split(';')[0].split('-')[0].lower()
                if _is_enabled(code, website):
                    return code
    except Exception:
        pass

    # 4. Langue par defaut du site
    from apps.translations.services import get_website_default_language
    return get_website_default_language(website)


def get_translated_page(page, language_code):
    """
    Retourne un objet avec les champs de la page traduits.
    Fallback : champs originaux de la page.
    """
    try:
        from apps.websites.models import WebsitePageTranslation
        t = WebsitePageTranslation.objects.filter(
            page=page, language=language_code
        ).first()
        if t:
            return _overlay(page, t, ['title', 'slug', 'content', 'meta_title', 'meta_description', 'meta_keywords'])
    except Exception:
        pass
    return page


def get_translated_section(section, language_code):
    """Retourne un objet avec les champs de la section traduits. Fallback : original."""
    try:
        from apps.websites.models import WebsiteSectionTranslation
        t = WebsiteSectionTranslation.objects.filter(
            section=section, language=language_code
        ).first()
        if t:
            return _overlay(section, t, ['title', 'subtitle', 'content', 'button_text', 'button_url'])
    except Exception:
        pass
    return section


def get_translated_menu_item(menu_item, language_code):
    """Retourne un objet avec le libelle du menu item traduit. Fallback : original."""
    try:
        from apps.websites.models import WebsiteMenuItemTranslation
        t = WebsiteMenuItemTranslation.objects.filter(
            menu_item=menu_item, language=language_code
        ).first()
        if t:
            return _overlay(menu_item, t, ['label', 'url'])
    except Exception:
        pass
    return menu_item


def get_language_url(website, language_code, path):
    """
    Genere l URL de la version traduite d une page.
    Si use_language_prefix_urls=True : /fr/path, /en/path
    Sinon : path?lang=language_code
    """
    try:
        ls = website.language_settings
        if ls.use_language_prefix_urls:
            clean_path = path.lstrip('/')
            return f'/{language_code}/{clean_path}'
    except Exception:
        pass
    separator = '&' if '?' in path else '?'
    return f'{path}{separator}lang={language_code}'


def get_hreflang_links(page, website, current_path):
    """
    Genere la liste des balises hreflang pour le SEO multilingue.
    Retourne une liste de dicts {lang, url}.
    """
    links = []
    try:
        ls = website.language_settings
        for lang in ls.enabled_languages.filter(is_active=True):
            url = get_language_url(website, lang.code, current_path)
            links.append({'lang': lang.code, 'url': url})
    except Exception:
        pass
    return links


# ── helpers ──────────────────────────────────────────────────────────────────

def _is_enabled(lang_code, website):
    try:
        ls = website.language_settings
        return ls.enabled_languages.filter(code=lang_code, is_active=True).exists()
    except Exception:
        return False


class _Overlay:
    """Wrapper qui superpose des champs traduits sur un objet Django sans modifier l original."""
    __slots__ = ('_base', '_overrides')

    def __init__(self, base, overrides):
        object.__setattr__(self, '_base', base)
        object.__setattr__(self, '_overrides', overrides)

    def __getattr__(self, name):
        overrides = object.__getattribute__(self, '_overrides')
        if name in overrides:
            return overrides[name]
        return getattr(object.__getattribute__(self, '_base'), name)


def _overlay(base, translation_obj, fields):
    overrides = {}
    for field in fields:
        val = getattr(translation_obj, field, None)
        if val:
            overrides[field] = val
    return _Overlay(base, overrides)
