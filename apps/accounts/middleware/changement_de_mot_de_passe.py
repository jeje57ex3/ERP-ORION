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
)

PREFIXES_D_API = ('/api/',)

MESSAGE = (
    'Votre compte utilise encore le code provisoire reçu par courriel. '
    'Choisissez votre mot de passe pour continuer.'
)


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

        return redirect('accounts:changer_mot_de_passe')
