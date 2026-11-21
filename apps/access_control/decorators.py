"""
access_control/decorators.py
Décorateurs de protection des vues Django.

**AVERTISSEMENT MESURÉ, et il porte sur ce fichier.** Les trois décorateurs
`module_required`, `view_required` et `action_required` ci-dessous, ainsi
que les trois mixins de `mixins.py`, ont **zéro appelant dans tout le
projet** (mesuré le 21/11/2026). Les rôles, permissions, modules, actions
et dérogations que l'écran `/access_control/` permet de configurer ne
gouvernent donc l'accès à aucune page : les vues de l'ERP sont gardées par
`@login_required`, et le reste est décoratif.

Les brancher n'est pas une correction mais un chantier : il faut décider,
module par module, qui a le droit de quoi, et toute erreur enferme dehors
quelqu'un qui travaille. Cela demande votre arbitrage et ne peut pas se
faire au détour d'un audit — c'est consigné comme tel dans
`docs/AUDIT-SECURITE-3.md`.

Ce qui **a** été corrigé tout de suite, c'est le plus pressant : les écrans
de CE module — ceux qui créent les rôles, accordent les permissions et
attribuent les accès — n'étaient eux-mêmes gardés que par
`@login_required`. N'importe quel compte connecté pouvait donc créer un
rôle, lui donner « accès complet » d'un clic (`action_type=full_access`) et
se l'attribuer. Un système de permissions que ses propres écrans
laissaient reconfigurer par tout le monde. D'où
`administration_requise` ci-dessous.
"""
from functools import wraps
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from .services import user_has_module_access, user_has_view_access, user_has_action_access


def _get_company(request):
    return getattr(request, 'current_company', None)


# Les codes de rôle qui valent administration de l'entreprise. Repris
# TELS QUELS de `apps/website_shop_settings/permissions.py`, qui posait
# déjà cette question : inventer une seconde règle, c'est garantir qu'un
# jour les deux divergeront et que personne ne saura laquelle s'applique.
CODES_ADMINISTRATEURS = ('admin', 'owner')


def est_administrateur_de_l_entreprise(request):
    """Vrai si ce compte administre l'entreprise courante.

    Le superadmin de l'installation passe toujours : c'est l'exploitant, il
    intervient légitimement sur toutes les entreprises, et c'est le même
    choix que `shop_settings_access_required`.

    `role` est une CLÉ ÉTRANGÈRE vers `Role`, pas une chaîne. Filtrer sur
    `role__in=('admin', 'owner')` faisait lever à Django « Field 'id'
    expected a number but got 'admin' » — une erreur 500 pour tout
    non-superadmin, donc un écran inutilisable par ceux à qui il est
    destiné. On compare le CODE du rôle. Le défaut a déjà été commis une
    fois dans ce dépôt ; il est écrit ici pour ne pas l'être deux fois.
    """
    utilisateur = getattr(request, 'user', None)
    if not (utilisateur and utilisateur.is_authenticated):
        return False
    if utilisateur.is_superuser:
        return True
    company = _get_company(request)
    if not company:
        return False
    if not hasattr(utilisateur, 'company_accesses'):
        return False
    return utilisateur.company_accesses.filter(
        company=company,
        role__code__in=CODES_ADMINISTRATEURS,
        is_active=True,
    ).exists()


def administration_requise(view_func):
    """Réserve une vue aux administrateurs de l'entreprise et au superadmin.

    Lève `PermissionDenied` (403) au lieu de rediriger : ces vues écrivent
    des permissions, et une redirection muette vers le tableau de bord se
    lit comme « la page n'a rien fait » alors qu'elle a refusé. Sur un
    écran de droits, savoir qu'on a été refusé fait partie de la réponse.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not getattr(request.user, 'is_authenticated', False):
            return redirect('accounts:login')
        if not est_administrateur_de_l_entreprise(request):
            raise PermissionDenied(
                'Seul un administrateur de l’entreprise peut modifier les '
                'rôles et les accès.')
        return view_func(request, *args, **kwargs)
    return wrapper


def module_required(module_code):
    """Exige l'accès au module. Redirige avec message si refusé."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('accounts:login')
            company = _get_company(request)
            if not company or not user_has_module_access(request.user, company, module_code):
                messages.error(request, f"Vous n'avez pas accès au module « {module_code} ».")
                return redirect('core:dashboard')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def view_required(view_code):
    """Exige l'accès à une vue précise."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('accounts:login')
            company = _get_company(request)
            if not company or not user_has_view_access(request.user, company, view_code):
                messages.error(request, "Vous n'avez pas accès à cette page.")
                return redirect('core:dashboard')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def action_required(module_code, action_code):
    """Exige la capacité d'effectuer une action dans un module."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('accounts:login')
            company = _get_company(request)
            if not company or not user_has_action_access(request.user, company, module_code, action_code):
                messages.error(request, "Vous n'avez pas la permission d'effectuer cette action.")
                return redirect('core:dashboard')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
