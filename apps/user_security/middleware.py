from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect

from apps.user_security.services import (
    TWO_FACTOR_PENDING_USER_KEY,
    is_2fa_verified,
    is_trusted_device,
    mark_2fa_verified,
    user_has_2fa_enabled,
    user_requires_2fa,
)


EXEMPT_PREFIXES = (
    "/accounts/login/",
    "/accounts/logout/",
    "/login/",
    "/auth/2fa/",
    "/account/security/",
    "/static/",
    "/media/",
    "/orion/",
    "/api/v1/",       # Les API vérifient l'auth via request.user.is_authenticated elles-mêmes
    "/health/",
    "/mobile/",       # Page publique de téléchargement de l'app mobile — pas d'auth requise
)


class RequireTwoFactorMiddleware:
    """Redirige vers la vérification 2FA si l'utilisateur ne l'a pas encore faite."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)

        if (
            user
            and user.is_authenticated
            and not any(request.path.startswith(p) for p in EXEMPT_PREFIXES)
            and user_requires_2fa(user)
        ):
            if is_trusted_device(request, user):
                mark_2fa_verified(request, user)
            elif not is_2fa_verified(request):
                if not user_has_2fa_enabled(user):
                    # 2FA requise mais pas configurée → forcer le setup uniquement
                    if not request.path.startswith("/account/security/"):
                        return redirect("user_security:two_factor_setup")
                elif not request.session.get(TWO_FACTOR_PENDING_USER_KEY):
                    # Session authentifiée, 2FA activée, mais ni vérification
                    # ni clef d'attente : il ne reste qu'à faire reprendre la
                    # connexion depuis le début, car cette vue n'a aucun moyen
                    # de savoir qui est à demi authentifié.
                    #
                    # Ce cas ne doit plus se produire à la connexion -- c'est
                    # login_view qui pose la clef. Il subsiste pour les
                    # sessions ouvertes avant ce correctif, et pour celles dont
                    # le marqueur de vérification a été effacé.
                    #
                    # Le message n'est pas un ornement : sans lui, le mot de
                    # passe est accepté et l'écran de connexion revient sans
                    # un mot, ce qui est indiscernable d'un mot de passe
                    # refusé. C'est ce silence qui a verrouillé un compte.
                    logout(request)
                    messages.warning(
                        request,
                        "Votre session a expiré pour raison de sécurité. "
                        "Reconnectez-vous, puis saisissez votre code de "
                        "double authentification.",
                    )
                    return redirect("accounts:login")
                else:
                    return redirect("user_security:two_factor_verify")

        return self.get_response(request)
