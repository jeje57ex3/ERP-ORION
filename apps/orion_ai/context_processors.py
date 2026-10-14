"""Disponibilité d'Orion, pour l'icône de la barre du haut.

L'icône ne doit apparaître que si Orion peut réellement répondre. Un bouton
visible qui mène à « l'assistant est désactivé » est une promesse non tenue à
chaque page, et on finit par ne plus le voir — y compris le jour où il
marche.

Trois conditions, et aucune ne coûte de requête hors la lecture des réglages,
déjà mémorisée par le module :

- la fonctionnalité est activée au niveau du serveur ;
- elle est activée pour l'entreprise active ;
- l'utilisateur y a droit.
"""

from django.conf import settings


def orion_ai_context(request):
    utilisateur = getattr(request, 'user', None)
    if not utilisateur or not utilisateur.is_authenticated:
        return {'orion_ai_available': False}

    if not getattr(settings, 'ORION_AI_ENABLED', False):
        return {'orion_ai_available': False}

    try:
        from apps.orion_ai.permissions import can_use_ai
        from apps.orion_ai.services import get_ai_settings, get_request_company

        if not can_use_ai(utilisateur):
            return {'orion_ai_available': False}

        reglages = get_ai_settings(get_request_company(request))
        if not reglages.ai_enabled:
            return {'orion_ai_available': False}

        return {
            'orion_ai_available': True,
            'orion_ai_name': reglages.ai_name or 'Orion',
            # Affiché dans l'infobulle : la garantie que rien ne sort du
            # serveur est la raison d'être de cette IA, autant la rappeler là
            # où on la sollicite.
            'orion_ai_local_only': reglages.local_only,
        }
    except Exception:
        # Base non migrée, module en cours d'installation : l'icône disparaît
        # plutôt que de casser toutes les pages de l'ERP. Un processeur de
        # contexte qui lève une exception rend l'application entièrement
        # inutilisable, pour un bouton.
        return {'orion_ai_available': False}
