"""« À la première connexion » : le passage obligé, et ce qui le ferait rater.

Un compte créé par `accounts:user_create` reçoit un code provisoire par
courriel et porte `profile.doit_changer_de_mot_de_passe`. Ce middleware
renvoie toute requête vers l'écran de changement tant que le drapeau est
posé.

**POURQUOI UN MIDDLEWARE ET NON UNE REDIRECTION APRÈS LA CONNEXION.**
Rediriger depuis `login_view` ne tiendrait que le temps d'une requête :
l'utilisateur taperait ensuite n'importe quelle adresse et travaillerait
toute la journée avec le code reçu par courriel. L'obligation doit porter
sur *chaque* requête, sinon elle ne porte que sur la première page.

**LES EXEMPTIONS, ET POURQUOI CHACUNE.** Une liste trop courte boucle, une
liste trop longue ouvre des trous. Chaque entrée a sa raison :

* l'écran de changement lui-même, sinon il se redirige vers lui-même ;
* la déconnexion, sans quoi un utilisateur qui refuse de changer son mot
  de passe serait enfermé dans la page sans pouvoir en sortir ;
* la connexion, sinon la redirection se déclencherait avant même d'avoir
  une session utilisable ;
* `/static/` et `/media/` : la page de changement charge ses propres
  feuilles de style et son logo. Sans cette exemption, elle s'afficherait
  nue — et une page de sécurité qui a l'air cassée se fait contourner ;
* `/setup/` : l'assistant de première installation tourne avant qu'aucun
  profil n'existe ;
* `/health/` : la sonde de supervision n'est pas un utilisateur et doit
  répondre 200 quoi qu'il arrive.

**LES API NE SONT PAS EXEMPTÉES, et c'est une différence assumée avec
`RequireTwoFactorMiddleware`.** Ce dernier laisse passer `/api/v1/` parce
qu'un second facteur ne se saisit pas dans un appel programmatique. Ici,
le compte porte un mot de passe que l'administrateur a vu passer dans les
journaux d'un serveur de courriel : lui ouvrir l'API reviendrait à dire
que l'obligation ne vaut que pour les écrans. Un appel d'API reçoit donc
**403 et un motif lisible**, et non une redirection — une redirection vers
du HTML, un client d'API la lit comme une réponse valide et s'embrouille.

**L'ORDRE DANS LA PILE.** Après `AuthenticationMiddleware`, qui pose
`request.user` ; après `RequireTwoFactorMiddleware`, pour que le second
facteur soit vérifié d'abord — changer son mot de passe est une action
sensible, et l'autoriser avant la 2FA ferait de ce passage obligé un
contournement de la 2FA.
"""

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect

CHEMINS_EXEMPTES = (
    '/accounts/profile/mot-de-passe/',
    '/accounts/logout/',
    '/accounts/login/',
    '/login/',
    '/logout/',
    '/static/',
    '/media/',
    '/setup/',
    '/health/',
    # ─── L'espace client ────────────────────────────────────────────────
    #
    # Un client de portail reçoit lui aussi un code provisoire par courriel
    # (`apps/portals/services/acces_portail.py`), donc le même drapeau. Ces
    # quatre chemins sont ceux qu'il doit pouvoir atteindre malgré lui :
    #
    # * son écran de changement, sinon il se redirige vers lui-même ;
    # * la connexion et la déconnexion, sans quoi il serait enfermé dans la
    #   page sans pouvoir quitter la session — sur un poste partagé, c'est
    #   un vrai problème ;
    # * `definir-mot-de-passe/`, le lien signé d'invitation. Il règle le mot
    #   de passe par un autre chemin et connecte lui-même : le rediriger
    #   casserait les invitations déjà envoyées.
    '/client/mot-de-passe/',
    '/client/connexion/',
    '/client/deconnexion/',
    '/client/definir-mot-de-passe/',
)

PREFIXES_D_API = ('/api/',)

MESSAGE = (
    'Votre compte utilise encore le code provisoire reçu par courriel. '
    'Choisissez votre mot de passe pour continuer.'
)


def _est_un_client_de_portail(utilisateur):
    """Délègue à `apps.portals`, en important À L'APPEL et non en tête.

    Ce middleware est chargé à la résolution de `MIDDLEWARE` ; importer une
    autre application depuis son en-tête crée une dépendance de chargement
    dont on n'a pas besoin, et que la moindre réorganisation de
    `INSTALLED_APPS` ferait tomber. L'import à l'appel coûte un accès au
    cache de modules.

    Rend faux si l'application du portail est absente : une installation
    sans espace client ne doit pas tomber ici.
    """
    try:
        from apps.portals.services.acces_portail import (
            est_un_client_de_portail,
        )
    except Exception:
        return False
    return est_un_client_de_portail(utilisateur)


def changement_requis(utilisateur):
    """Vrai si ce compte doit remplacer son mot de passe avant d'agir.

    Un compte SANS profil n'est pas concerné : il ne peut pas porter le
    drapeau, donc il ne peut pas l'avoir reçu. Le lire avec `getattr`
    plutôt que par l'attribut direct évite de faire tomber chaque requête
    sur une installation où un profil manquerait — une protection qui
    casse le site est une protection qu'on retire.
    """
    if not (utilisateur and utilisateur.is_authenticated):
        return False
    profil = getattr(utilisateur, 'profile', None)
    return bool(profil and profil.doit_changer_de_mot_de_passe)


class ChangementDeMotDePasseRequisMiddleware:
    """Renvoie vers le changement de mot de passe tant qu'il est dû."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        chemin = request.path

        if any(chemin.startswith(p) for p in CHEMINS_EXEMPTES):
            return self.get_response(request)

        if not changement_requis(getattr(request, 'user', None)):
            return self.get_response(request)

        if any(chemin.startswith(p) for p in PREFIXES_D_API):
            # 403 et un motif, pas une redirection : un client d'API lirait
            # un 302 vers du HTML comme une réponse valide.
            return JsonResponse(
                {'detail': MESSAGE,
                 'code': 'mot_de_passe_provisoire'},
                status=403)

        # Posé une seule fois par requête redirigée. Le message de Django
        # n'est pas dédoublonné : sans précaution, une page qui déclenche
        # plusieurs redirections empilerait le même bandeau.
        if not request.session.get('_avertissement_mdp_provisoire'):
            request.session['_avertissement_mdp_provisoire'] = True
            messages.warning(request, MESSAGE)

        # UN CLIENT D'ESPACE CLIENT N'EST PAS UN SALARIÉ, et l'écran de
        # l'ERP étend `erp_base.html` : il y verrait le menu de l'ERP, le
        # sélecteur d'entreprise et le fil d'ariane d'un employé. Pire, les
        # liens de ce menu le renverraient vers des pages qui le
        # redirigeraient ici — une boucle visible.
        #
        # Le test est fait par la relation `portal_account`, exactement
        # comme `_get_portal_account` côté portail : décider autrement ferait
        # divorcer les deux lectures de « qui est un client ».
        if _est_un_client_de_portail(getattr(request, 'user', None)):
            return redirect('client_portal:changer_mot_de_passe')

        return redirect('accounts:changer_mot_de_passe')
