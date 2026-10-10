"""
apps/configurator/services/i18n.py — Traduction du contenu dynamique du
configurateur (domaines, prestations, questions, options, message de
sécurité, mots-clés de danger) demandée après le système de traduction du
site vitrine (React) qui, lui, ne couvre que le "chrome" statique de
l'interface — pas le contenu qui vient d'Orion.

Convention : même idiome que apps.websites.models (WebsitePageTranslation,
etc.) — une table sœur `*Translation` par modèle, `unique_together
(objet, langue)`, repli silencieux sur la valeur française du modèle de
base si aucune traduction n'existe pour la langue demandée. Le français
n'a pas de table de traduction : il est la langue "source" portée par les
champs du modèle principal.
"""
SUPPORTED_LANGUAGES = {'fr', 'en', 'de', 'pt'}
DEFAULT_LANGUAGE = 'fr'


def normalize_language(value):
    """Ne fait jamais confiance à l'entrée (query param / JSON body) :
    une langue non supportée retombe silencieusement sur le français plutôt
    que de lever une erreur ou d'exposer un comportement indéfini."""
    value = (value or '').strip().lower()[:5]
    return value if value in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def overlay(obj, language, fields, related_name='translations'):
    """Retourne un dict {champ: valeur} dans la langue demandée pour un
    objet donné, avec repli sur la valeur du modèle de base par champ (une
    traduction partielle — ex: nom traduit mais description encore vide —
    ne doit jamais faire disparaître le texte français correspondant)."""
    base = {f: getattr(obj, f) for f in fields}
    if language == DEFAULT_LANGUAGE or not obj.pk:
        return base
    translation = getattr(obj, related_name).filter(language=language).first()
    if not translation:
        return base
    for f in fields:
        val = getattr(translation, f, None)
        if val:
            base[f] = val
    return base
