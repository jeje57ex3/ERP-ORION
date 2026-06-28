"""
apps/translations/email_services.py — Emails multilingues Orion ERP

Priorite langue pour les emails :
  1. langue du destinataire (client)
  2. langue par defaut de l entreprise
  3. francais
"""
from pathlib import Path
from django.conf import settings
from django.template.loader import render_to_string


def get_email_template(template_name, language_code='fr'):
    """
    Retourne le chemin du template email pour la langue demandee.
    Fallback : fr si le template n existe pas dans la langue cible.
    """
    candidates = [
        f'emails/{language_code}/{template_name}',
        f'emails/fr/{template_name}',
        f'emails/{template_name}',
    ]
    from django.template.loader import get_template
    from django.template.exceptions import TemplateDoesNotExist

    for candidate in candidates:
        try:
            get_template(candidate)
            return candidate
        except TemplateDoesNotExist:
            continue
    return f'emails/{template_name}'


def render_email(template_name, context, language_code='fr'):
    """Render un email dans la langue cible avec fallback fr."""
    tpl = get_email_template(template_name, language_code)
    return render_to_string(tpl, context)


def get_recipient_language(user=None, client=None, company=None):
    """
    Determine la langue a utiliser pour l email d un destinataire.
    Priorite : utilisateur > client > entreprise > fr
    """
    # 1. Preference utilisateur connecte
    if user and user.is_authenticated:
        from apps.translations.models import UserLanguagePreference
        pref = UserLanguagePreference.objects.filter(user=user).select_related('language').first()
        if pref and pref.language.is_active:
            return pref.language.code

    # 2. Langue entreprise par defaut
    if company:
        from apps.translations.services import get_company_default_language
        return get_company_default_language(company)

    return 'fr'
