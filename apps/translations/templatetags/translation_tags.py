"""
apps/translations/templatetags/translation_tags.py

Usage dans un template :
  {% load translation_tags %}
  {% get_translation "sales.invoices" request %}
  {% website_languages site as langs %}
  {% active_language request as lang_code %}
"""
from django import template
from django.utils import translation

register = template.Library()


@register.simple_tag
def get_translation(key, request=None, fallback=''):
    """Retourne la traduction personnalisee d une cle pour le contexte courant."""
    try:
        from apps.translations.models import InterfaceTranslation
        lang_code = getattr(request, 'LANGUAGE_CODE', translation.get_language()) or 'fr'
        company   = getattr(request, 'company', None) if request else None

        qs = InterfaceTranslation.objects.filter(key=key)
        # Priorite : entreprise > global
        if company:
            t = qs.filter(language__code=lang_code, company=company).first()
            if t:
                return t.translated_text
        t = qs.filter(language__code=lang_code, company=None).first()
        if t:
            return t.translated_text
    except Exception:
        pass
    return fallback or key


@register.simple_tag(takes_context=True)
def website_languages(context, website):
    """
    Retourne la liste des langues actives d un site web avec l URL courante.
    Usage : {% website_languages site as langs %}
    """
    try:
        from apps.translations.models import WebsiteLanguageSettings
        ls = website.language_settings
        request = context.get('request')
        langs = []
        for lang in ls.enabled_languages.filter(is_active=True).order_by('order', 'name'):
            current = getattr(request, 'LANGUAGE_CODE', 'fr') if request else 'fr'
            langs.append({
                'code':        lang.code,
                'native_name': lang.native_name,
                'flag_icon':   lang.flag_icon,
                'is_current':  lang.code == current,
                'url':         f'?lang={lang.code}',
            })
        return langs
    except Exception:
        return []


@register.simple_tag(takes_context=True)
def active_language(context):
    """Retourne le code langue actif."""
    request = context.get('request')
    if request:
        return getattr(request, 'LANGUAGE_CODE', translation.get_language()) or 'fr'
    return translation.get_language() or 'fr'


@register.filter
def trans_key(key, request=None):
    """Filtre : {{ "sales.invoices"|trans_key:request }}"""
    return get_translation(key, request)
