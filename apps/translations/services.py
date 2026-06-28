"""
apps/translations/services.py — Services langue pour Orion ERP
"""
from django.utils import translation as dj_translation


def get_user_language(user, company=None):
    """Retourne le code langue actif pour un utilisateur."""
    try:
        from apps.translations.models import UserLanguagePreference
        qs = UserLanguagePreference.objects.select_related('language').filter(user=user)
        if company:
            pref = qs.filter(company=company).first()
            if pref and pref.language.is_active:
                return pref.language.code
        pref = qs.filter(company=None).first()
        if pref and pref.language.is_active:
            return pref.language.code
    except Exception:
        pass
    return get_company_default_language(company) if company else 'fr'


def set_user_language(user, language_code, company=None, request=None):
    """Enregistre la preference de langue d un utilisateur."""
    from apps.translations.models import UserLanguagePreference, Language
    lang = Language.objects.filter(code=language_code, is_active=True).first()
    if not lang:
        return False
    UserLanguagePreference.objects.update_or_create(
        user=user, company=company,
        defaults={'language': lang}
    )
    if request is not None:
        request.session['_language'] = language_code
        dj_translation.activate(language_code)
        request.LANGUAGE_CODE = language_code
    return True


def get_company_default_language(company):
    """Retourne le code langue par defaut d une entreprise."""
    try:
        ls = company.language_settings
        if ls.default_language and ls.default_language.is_active:
            return ls.default_language.code
    except Exception:
        pass
    return 'fr'


def get_enabled_languages_for_company(company):
    """Retourne la liste (code, native_name) des langues actives pour une entreprise."""
    try:
        ls = company.language_settings
        return list(
            ls.enabled_languages.filter(is_active=True)
            .order_by('order', 'name')
            .values_list('code', 'native_name')
        )
    except Exception:
        pass
    return [('fr', 'Français')]


def get_enabled_languages_for_website(website):
    """Retourne la liste Language des langues actives pour un site web."""
    try:
        ls = website.language_settings
        return list(ls.enabled_languages.filter(is_active=True).order_by('order', 'name'))
    except Exception:
        pass
    return []


def activate_user_language(request):
    """Active la langue de l utilisateur connecte et la stocke sur request."""
    lang = 'fr'
    if request.user.is_authenticated:
        company = getattr(request, 'company', None)
        lang = get_user_language(request.user, company)
    dj_translation.activate(lang)
    request.LANGUAGE_CODE = lang
    return lang


def get_website_default_language(website):
    """Retourne le code langue par defaut d un site web."""
    try:
        ls = website.language_settings
        if ls.default_language and ls.default_language.is_active:
            return ls.default_language.code
    except Exception:
        pass
    return 'fr'
