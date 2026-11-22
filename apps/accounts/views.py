"""
apps/accounts/views.py — Authentification, profil, gestion utilisateurs
"""
from urllib.parse import quote

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import Http404, JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.user_security.services import (
    TWO_FACTOR_PENDING_USER_KEY,
    is_trusted_device,
    user_has_2fa_enabled,
    user_requires_2fa,
)

from .forms import LoginForm, UserForm, UserProfileForm, UserCreateForm
from .models import UserProfile
from apps.accounts import anti_force_brute
from apps.core.redirections import destination_sure
from apps.core.models import Company, AuditLog
from apps.accounts.services.code_provisoire import creer_et_envoyer
from apps.accounts.services.user_employee_link_service import (
    link_user_to_employee,
    get_user_employee,
    is_user_exempt_from_employee_link,
)
from apps.accounts.services.user_deletion_service import (
    peut_supprimer,
    inventaire_cascade,
    supprimer_utilisateur,
    desactiver_utilisateur,
)


def login_view(request):
    if request.user.is_authenticated:
        return redirect('core:dashboard')

    form = LoginForm(request, data=request.POST or None)

    # LA LIMITATION DES TENTATIVES, POSEE AVANT `is_valid()`.
    #
    # `LoginForm` derive d'`AuthenticationForm` : c'est `is_valid()` qui
    # appelle `authenticate()`, donc qui hache le mot de passe propose.
    # Verifier le verrou apres reviendrait a faire ce travail a chaque
    # essai -- c'est-a-dire a offrir a l'attaquant exactement le cout
    # qu'on cherche a lui imposer.
    #
    # `UserProfile.failed_login_attempts` et `locked_until` existaient
    # depuis la premiere migration et n'etaient lus nulle part : la
    # protection etait prevue, sa place creusee, et jamais branchee.
    identifiant = (request.POST.get('username') or '').strip()

    if request.method == 'POST':
        verrouille, refus = anti_force_brute.est_verrouille(
            request, identifiant)
        if verrouille:
            messages.error(request, refus)
            return render(request, 'accounts/login.html', {'form': form})

    if request.method == 'POST' and not form.is_valid():
        # L'ECHEC EST COMPTE ICI, et le message de verrou -- s'il vient
        # de se poser -- remplace celui des identifiants incorrects :
        # dire « identifiants incorrects » a quelqu'un dont le compte
        # vient d'etre suspendu l'enverrait reessayer indefiniment.
        refus = anti_force_brute.enregistrer_un_echec(request, identifiant)
        if refus:
            messages.error(request, refus)
            return render(request, 'accounts/login.html', {'form': form})

    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        remember = form.cleaned_data.get('remember_me')

        anti_force_brute.effacer_les_echecs(request, identifiant)

        if not remember:
            request.session.set_expiry(0)

        # La 2FA s'interpose ICI, avant login() — et non apres.
        #
        # two_factor_verify_view attend un utilisateur a demi
        # authentifie, designe par orion_2fa_pending_user_id dans la
        # session ; c'est elle qui appellera login() une fois le code
        # valide. Connecter l'utilisateur des maintenant court-circuite
        # ce protocole : le middleware voit alors une session complete
        # sans clef d'attente, et sa seule issue est de deconnecter.
        # Le mot de passe est accepte, l'ecran de connexion revient, et
        # rien ne l'explique a l'utilisateur -- indefiniment. Personne
        # ne posait cette clef ; c'est tout ce qui manquait.
        #
        # L'appareil de confiance passe outre : le middleware marquera
        # la session verifiee de lui-meme au premier acces.
        if (
            user_requires_2fa(user)
            and user_has_2fa_enabled(user)
            and not is_trusted_device(request, user)
        ):
            request.session[TWO_FACTOR_PENDING_USER_KEY] = user.id
            cible = reverse('user_security:two_factor_verify')
            demande = request.GET.get('next')
            if demande:
                cible = f'{cible}?next={quote(demande)}'
            return redirect(cible)

        login(request, user)

        AuditLog.objects.create(
            user=user,
            action='login',
            description=f'Connexion utilisateur : {user.username}',
            ip_address=_get_ip(request),
        )

        # LA DESTINATION DE RETOUR EST VERIFIEE.
        #
        # `redirect()` sert telle quelle une adresse absolue :
        # `?next=https://exemple-pirate/` envoyait l'utilisateur hors du
        # site juste apres une connexion reussie -- l'instant ou il a le
        # moins de raisons de se mefier, puisque tout ce qu'on lui a
        # demande a fonctionne.
        return redirect(destination_sure(
            request, request.GET.get('next'), 'core:dashboard'))

    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    if request.user.is_authenticated:
        AuditLog.objects.create(
            user=request.user,
            action='logout',
            description=f'Déconnexion : {request.user.username}',
        )
    logout(request)
    messages.info(request, 'Vous avez été déconnecté.')
    return redirect('accounts:login')


@login_required
def profile(request):
    """Profil et préférences de l'utilisateur connecté."""
    user_form = UserForm(request.POST or None, instance=request.user)
    profile_form = UserProfileForm(request.POST or None, request.FILES or None, instance=request.user.profile)

    if request.method == 'POST':
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Profil mis à jour avec succès.')
            return redirect('accounts:profile')

    return render(request, 'accounts/profile.html', {
        'user_form': user_form,
        'profile_form': profile_form,
        'page_title': 'Mon profil',
    })


@login_required
def changer_mot_de_passe(request):
    """Son propre mot de passe, par soi-même.

    CE QUI N'EXISTAIT PAS

    Aucune route ne permettait de changer son mot de passe. Seul un
    administrateur pouvait le réinitialiser pour quelqu'un d'autre
    (`user_reset_password`), ce qui oblige à le lui communiquer — donc à le
    faire transiter par un canal que personne ne maîtrise.

    `PasswordChangeForm` était d'ailleurs déjà importé dans forms.py, sans
    être employé nulle part.

    LE PIÈGE : CHANGER SON MOT DE PASSE DÉCONNECTE

    La session porte une empreinte du mot de passe. Dès qu'il change,
    l'empreinte ne correspond plus et Django ferme la session à la requête
    SUIVANTE. Sans `update_session_auth_hash`, l'utilisateur serait donc
    renvoyé à l'écran de connexion juste après avoir réussi son changement —
    et lirait cela comme un échec, voire comme un mot de passe qui n'aurait
    pas été pris en compte.

    L'ancien mot de passe est EXIGÉ (c'est le propre de PasswordChangeForm) :
    sans lui, un poste laissé déverrouillé suffirait à s'approprier un
    compte.

    CETTE VUE SERT AUSSI DE PASSAGE OBLIGÉ

    Un compte créé depuis `user_create` reçoit un code provisoire par
    courriel et porte `profile.doit_changer_de_mot_de_passe`. Le middleware
    `ChangementDeMotDePasseRequisMiddleware` renvoie alors ici à chaque
    requête, jusqu'à ce que le mot de passe soit changé.

    C'est bien la MÊME vue, et non une seconde écrite pour l'occasion :
    deux écrans qui changent un mot de passe finissent par ne plus le faire
    de la même manière, et c'est celui qu'on regarde le moins qui garde le
    défaut. Seul le texte diffère, selon que le changement est obligatoire
    ou choisi.

    L'ANCIEN MOT DE PASSE RESTE EXIGÉ même pour une première connexion,
    et ce n'est pas une rigidité : c'est le code reçu par courriel, donc
    son titulaire l'a sous les yeux. L'exiger prouve qu'il a bien reçu le
    courriel — une session obtenue autrement ne suffit pas à s'approprier
    le compte.
    """
    from django.contrib.auth import update_session_auth_hash

    from apps.accounts.forms import ChangementDeMotDePasseForm

    profil = getattr(request.user, 'profile', None)
    obligatoire = bool(profil and profil.doit_changer_de_mot_de_passe)

    form = ChangementDeMotDePasseForm(request.user, request.POST or None)
    # Les widgets de Django ne portent aucune classe : sans cela les champs
    # s'afficheraient nus au milieu d'un formulaire stylé.
    for champ in form.fields.values():
        champ.widget.attrs.setdefault('class', 'form-control')

    if obligatoire:
        form.fields['old_password'].label = 'Code provisoire reçu par courriel'
        form.fields['old_password'].help_text = (
            'Celui du message « Votre accès à Orion ERP ».')

    if request.method == 'POST' and form.is_valid():
        utilisateur = form.save()

        # L'OBLIGATION EST LEVÉE ICI, et seulement si le formulaire a été
        # accepté. La lever plus tôt -- à l'affichage, par exemple --
        # suffirait à s'en débarrasser en ouvrant la page et en la
        # quittant.
        if obligatoire:
            profil.doit_changer_de_mot_de_passe = False
            profil.save(update_fields=['doit_changer_de_mot_de_passe'])
            # Le marqueur qui empêche d'empiler le bandeau est retiré avec
            # l'obligation. Laissé en place, un code renvoyé des mois plus
            # tard reposerait le drapeau sans que l'avertissement
            # réapparaisse — la page expliquerait encore, mais la
            # redirection serait muette.
            request.session.pop('_avertissement_mdp_provisoire', None)

        # L'ordre compte : on rafraîchit l'empreinte APRÈS l'enregistrement.
        update_session_auth_hash(request, utilisateur)
        messages.success(
            request,
            'Votre mot de passe est enregistré. Bienvenue.' if obligatoire
            else 'Votre mot de passe a été modifié. Vous restez connecté.')
        return redirect('core:dashboard' if obligatoire else 'accounts:profile')

    return render(request, 'accounts/password_change.html', {
        'form': form,
        'obligatoire': obligatoire,
        'page_title': ('Choisissez votre mot de passe' if obligatoire
                       else 'Changer mon mot de passe'),
    })


@login_required
@require_POST
def signature_save(request):
    """Enregistre la signature tracée dans le cadre.

    POST seulement : un GET qui modifie le compte se déclencherait au
    survol d'un lien, à l'indexation ou au passage d'un antivirus.

    L'ancien fichier est supprimé AVANT d'écrire le nouveau : sans cela, le
    stockage de Django renomme le nouveau (« signature-3_a8f2.png ») et les
    anciens s'accumulent indéfiniment sur le disque, un par
    réenregistrement.
    """
    from django.core.files.base import ContentFile

    from apps.accounts.signature import SignatureInvalide, decoder_signature

    try:
        octets = decoder_signature(request.POST.get('signature') or '')
    except SignatureInvalide as exc:
        # Le refus est renvoye tel quel : le cadre vide et le fichier
        # illisible n'ont pas le meme remede, et « erreur » ne le dirait pas.
        return JsonResponse({'erreur': str(exc)}, status=400)

    profil = request.user.profile
    if profil.signature:
        try:
            profil.signature.delete(save=False)
        except OSError:
            # Un fichier verrouille ou deja disparu ne doit PAS empecher
            # d'enregistrer la nouvelle signature : la consequence a
            # accepter est un fichier orphelin, bien preferable a un refus
            # d'enregistrement que l'utilisateur ne saurait pas contourner.
            # Rencontre sous Windows, ou une poignee encore ouverte fait
            # echouer os.remove (WinError 32).
            pass
    profil.signature.save(f'signature-{request.user.pk}.png',
                          ContentFile(octets), save=True)

    # L'adresse rendue est celle de la VUE, et non `profil.signature.url`.
    # `signatures/` figure dans PREFIXES_INTERDITS : l'URL /media/ brute
    # rend 404, et le script posait cette adresse dans l'aperçu juste
    # apres avoir affiche « Signature enregistree ». On annoncait donc une
    # reussite en montrant une image cassee.
    return JsonResponse({'url': reverse('accounts:signature_image'),
                         'message': 'Signature enregistrée.'})


@login_required
def signature_image(request):
    """Sert la signature de CELUI QUI DEMANDE, et d'elle seule.

    `signatures/` n'est pas servi par /media/ — « exposees, elles se
    recopient ». L'apercu du profil et la reponse de `signature_save`
    pointaient pourtant vers cette URL brute : le cadre restait vide au
    rechargement de la page comme juste apres l'enregistrement.

    Cette vue ne prend AUCUN identifiant, et c'est la borne : il n'y a pas
    de numero a changer dans l'adresse pour atteindre la signature d'un
    collegue. C'est plus simple et plus sur qu'un controle d'appartenance
    sur un `pk`, et ici cela suffit — personne n'a besoin de voir la
    signature d'un autre dans cet ecran.
    """
    from apps.core.media_access import servir_fichier_autorise

    profil = getattr(request.user, 'profile', None)
    if profil is None or not profil.signature:
        raise Http404('Aucune signature enregistrée.')
    return servir_fichier_autorise(
        profil.signature, 'signature.png', afficher_si_image=True)


@login_required
@require_POST
def signature_delete(request):
    """Retire la signature enregistrée.

    Le fichier est supprimé du disque, et pas seulement détaché : une
    signature manuscrite est une donnée personnelle, la laisser traîner
    après un retrait explicite serait difficile à justifier.
    """
    profil = request.user.profile
    if profil.signature:
        profil.signature.delete(save=True)
        messages.success(request, 'Signature retirée.')
    return redirect('accounts:profile')


def _utilisateurs_visibles(request):
    """Les comptes que l'utilisateur courant a le droit de voir.

    Extrait de user_list pour etre reutilise par user_detail et
    user_delete. user_detail faisait un get_object_or_404(User, pk=pk) sans
    aucun controle : n'importe quel compte connecte pouvait lire la fiche
    d'un utilisateur d'une AUTRE entreprise en changeant le numero dans
    l'URL. Ajouter un bouton « supprimer » sur une page non bornee aurait
    transforme une fuite de lecture en suppression a distance.

    Retourne None quand l'acces est refuse ; l'appelant redirige.
    """
    company = request.current_company
    if request.user.is_superuser:
        return User.objects.all()
    profil = getattr(request.user, 'profile', None)
    role = getattr(profil, 'role', '') or ''
    if company and role in ('admin', 'manager'):
        return User.objects.filter(profile__companies=company)
    return None


@login_required
def user_list(request):
    """Liste des utilisateurs (admin seulement)."""
    visibles = _utilisateurs_visibles(request)
    if visibles is None:
        messages.error(request, 'Accès refusé.')
        return redirect('core:dashboard')

    # employee_profile est charge avec le reste : sans cela, la colonne de
    # rattachement couterait une requete par ligne.
    users = list(visibles.select_related(
        'profile', 'employee_profile').order_by('username'))

    # Le droit de supprimer est calcule ligne par ligne, et non deduit dans
    # le gabarit. Les regles en jeu -- dernier super administrateur actif,
    # cloisonnement par entreprise -- ne sont pas exprimables en template,
    # et les y reecrire approximativement produirait des boutons qui menent
    # a un refus. Quelques requetes de plus sur un ecran d'administration
    # valent mieux qu'une interface dans laquelle on apprend a ne pas avoir
    # confiance.
    for compte in users:
        compte.suppression_possible = peut_supprimer(
            request.user, compte, request.current_company)[0]

    return render(request, 'accounts/user_list.html', {
        'users': users,
        'page_title': 'Gestion des utilisateurs',
    })


def _entier_ou_none(valeur):
    """Convertit un parametre d'URL en entier, ou rend None.

    Filtrer sur pk='abc' leve ValueError AVANT toute requete : .first() ne
    rattrape rien, c'est la preparation du filtre qui echoue. L'ancien code
    s'en sortait par un « except Exception » large ; en le retirant j'ai
    casse ce cas, et un test l'a attrape.
    """
    try:
        return int(valeur)
    except (TypeError, ValueError):
        return None


@login_required
def user_create(request):
    """Créer un utilisateur avec liaison salarié obligatoire pour les non-admins."""
    if not (request.user.is_superuser or request.user.profile.role in ['admin', 'superadmin']):
        messages.error(request, 'Accès refusé.')
        return redirect('accounts:user_list')

    company = getattr(request, 'current_company', None)

    # Pré-sélection d'un salarié depuis ?employee=<pk>
    #
    # Le filtre d'entreprise manquait : « ?employee=<pk> » désignant le
    # salarié d'une AUTRE société le pré-sélectionnait, et affichait son nom.
    # La validation l'aurait refusé ensuite, mais le nom avait déjà fuité.
    employee_prefill = None
    employee_pk = _entier_ou_none(request.GET.get('employee'))
    if employee_pk and company:
        from apps.hr.models import Employee
        employee_prefill = Employee.objects.filter(
            pk=employee_pk, company=company, user__isnull=True).first()

    form = UserCreateForm(
        request.POST or None,
        company=company,
        employee_prefill=employee_prefill,
    )

    if form.is_valid():
        user = form.save()
        # Rôle et entreprise
        profil = user.profile
        if company:
            profil.companies.add(company)
        profil.role = form.cleaned_data.get('role', 'user')
        # Enregistre AVANT la liaison : si la liaison échoue, le compte reste
        # dans un état cohérent, et un compte déclaré sans salarié n'est pas
        # signalé à tort comme un rattachement oublié.
        profil.without_employee_record = bool(
            form.cleaned_data.get('without_employee_record'))
        profil.save()

        # Liaison salarié
        employee = form.cleaned_data.get('employee')
        if employee:
            try:
                link_user_to_employee(user, employee)
                messages.success(request, f'Utilisateur "{user.username}" créé et lié à {employee.full_name}.')
            except Exception as exc:
                messages.warning(request, f'Utilisateur créé mais liaison salarié échouée : {exc}')
        elif profil.without_employee_record:
            messages.success(
                request,
                f'Utilisateur "{user.username}" créé, sans fiche salarié.')
        else:
            messages.success(request, f'Utilisateur "{user.username}" créé.')

        # ─── LE CODE PROVISOIRE ─────────────────────────────────────────
        #
        # EN DERNIER, après le rôle et la liaison salarié. Le compte sort
        # de `form.save()` avec un mot de passe INUTILISABLE : il ne peut
        # donc pas être atteint tant que cette étape n'a pas eu lieu, et
        # une erreur dans les étapes précédentes laisse un compte fermé
        # plutôt qu'un compte ouvert et à moitié configuré.
        #
        # L'ÉCHEC D'ENVOI N'ANNULE PAS LE COMPTE, et c'est un arbitrage.
        # Le défaire ferait perdre la saisie — le rôle, le salarié, la case
        # — pour un serveur de courriel momentanément muet. On le garde, on
        # le dit, et la fiche porte un bouton pour renvoyer un code.
        envoye, motif = creer_et_envoyer(user, request)
        if envoye:
            messages.info(
                request,
                f'Un code provisoire a été envoyé à {user.email}. '
                f'{user.get_full_name() or user.username} devra choisir son '
                'mot de passe à la première connexion.')
        else:
            messages.error(
                request,
                f'Le compte est créé, mais le code provisoire n’a PAS pu '
                f'être envoyé à {user.email} ({motif}). Personne ne peut '
                'donc s’y connecter pour l’instant. Vérifiez les réglages '
                'de courriel, puis utilisez « Renvoyer le code » sur la '
                'fiche ci-dessous.')

        return redirect('accounts:user_detail', pk=user.pk)

    return render(request, 'accounts/user_form.html', {
        'form': form,
        'page_title': 'Nouvel utilisateur',
        'employee_prefill': employee_prefill,
        'diagnostic_salaries': form.diagnostic_salaries,
    })


@login_required
def user_detail(request, pk):
    visibles = _utilisateurs_visibles(request)
    if visibles is None:
        messages.error(request, 'Accès refusé.')
        return redirect('core:dashboard')
    user_obj = get_object_or_404(visibles, pk=pk)
    # Le bouton de suppression n'est affiche que si l'operation est
    # reellement permise : un bouton qui mene a un refus apprend a
    # l'utilisateur a se mefier de l'interface.
    autorise, raison = peut_supprimer(
        request.user, user_obj, request.current_company)

    # L'ETAT DU VERROU EST AFFICHE, ET PAS SEULEMENT LEVABLE.
    #
    # Un administrateur qui ne voit pas pourquoi un collegue n'entre plus
    # cherchera ailleurs, et conclura a une panne.
    profil = getattr(user_obj, 'profile', None)
    verrou = None
    if profil and profil.locked_until and profil.locked_until > timezone.now():
        verrou = {
            'jusqu_a': profil.locked_until,
            'echecs': profil.failed_login_attempts,
        }

    return render(request, 'accounts/user_detail.html', {
        'user_obj': user_obj,
        'suppression_possible': autorise,
        'suppression_refus': raison,
        'verrou': verrou,
        'echecs_de_connexion': profil.failed_login_attempts if profil else 0,
        'page_title': user_obj.get_full_name() or user_obj.username,
    })


@login_required
@require_POST
def user_unlock(request, pk):
    """Leve le verrou de connexion d'un compte.

    EN POST, parce qu'un GET qui leverait un verrou de securite partirait
    au survol d'un lien ou au passage d'un antivirus.

    POURQUOI CET ECRAN EXISTE : si la seule facon de lever un verrou est
    une requete en base, alors la facon qui sera employee le jour ou ca
    presse est la desactivation de la protection -- et c'est le genre de
    reglage qu'on ne remet jamais.
    """
    visibles = _utilisateurs_visibles(request)
    if visibles is None:
        messages.error(request, 'Accès refusé.')
        return redirect('core:dashboard')

    user_obj = get_object_or_404(visibles, pk=pk)
    profil = getattr(user_obj, 'profile', None)

    if profil is None:
        messages.error(request, 'Ce compte n’a pas de profil.')
        return redirect('accounts:user_detail', pk=pk)

    anti_force_brute.deverrouiller(profil)

    AuditLog.objects.create(
        user=request.user,
        action='update',
        description=f'Verrou de connexion levé sur « {user_obj.username} »',
        ip_address=_get_ip(request),
    )

    messages.success(
        request,
        f'Le compte « {user_obj.username} » peut à nouveau se connecter.')
    return redirect('accounts:user_detail', pk=pk)


@login_required
@require_POST
def user_renvoyer_le_code(request, pk):
    """Engendre un nouveau code provisoire et le renvoie par courriel.

    POURQUOI CET ÉCRAN EXISTE. Le code n'est montré à personne, pas même à
    l'administrateur qui crée le compte — c'est tout l'intérêt du
    dispositif. Mais trois situations laissent alors un compte muet : un
    serveur de courriel momentanément indisponible à la création, une
    adresse saisie de travers, et le courriel simplement perdu ou
    supprimé. Sans ce bouton, la seule issue serait une requête en base ou
    un `changepassword` en console.

    EN POST, parce qu'un GET qui remplace un mot de passe partirait au
    survol d'un lien ou au passage d'un antivirus.

    LE CODE PRÉCÉDENT CESSE DE VALOIR, puisque `set_password` écrase
    l'empreinte. C'est voulu : deux codes valides à la fois sur un même
    compte doublent la surface pour rien, et un ancien courriel qui
    continuerait d'ouvrir le compte est exactement ce qu'on veut éviter
    quand on renvoie un code parce que le premier a fuité.
    """
    visibles = _utilisateurs_visibles(request)
    if visibles is None:
        messages.error(request, 'Accès refusé.')
        return redirect('core:dashboard')

    user_obj = get_object_or_404(visibles, pk=pk)

    if not user_obj.email:
        messages.error(
            request,
            'Ce compte n’a pas d’adresse de courriel : renseignez-la avant '
            'de renvoyer un code, sinon il n’irait nulle part.')
        return redirect('accounts:user_detail', pk=pk)

    envoye, motif = creer_et_envoyer(user_obj, request)

    AuditLog.objects.create(
        user=request.user,
        action='update',
        description=('Code provisoire renvoyé à « %s » (%s)'
                     % (user_obj.username,
                        'envoyé' if envoye else 'échec : %s' % motif)),
        ip_address=_get_ip(request),
    )

    if envoye:
        messages.success(
            request,
            f'Un nouveau code provisoire a été envoyé à {user_obj.email}. '
            'Le précédent ne vaut plus.')
    else:
        messages.error(
            request,
            f'Le code n’a PAS pu être envoyé ({motif}). Le compte est '
            'maintenant fermé — l’ancien code ne vaut plus non plus. '
            'Corrigez les réglages de courriel, puis réessayez.')

    return redirect('accounts:user_detail', pk=pk)


@login_required
def user_delete(request, pk):
    """Supprime un compte, apres confirmation de ce qui sera detruit.

    La page de confirmation n'affiche pas une mise en garde generique :
    elle dresse l'inventaire reel, obtenu du collecteur de Django. Sur ce
    projet, 29 relations vers User sont en CASCADE -- dont les heures
    pointees sur les chantiers et les comptes de fidelite des clientes.
    Confirmer sans voir ces nombres reviendrait a signer a l'aveugle.

    L'identifiant doit etre RECOPIE pour que la suppression se fasse. Un
    simple « Etes-vous sur ? » se clique par reflexe ; recopier un nom
    demande de l'avoir lu.
    """
    visibles = _utilisateurs_visibles(request)
    if visibles is None:
        messages.error(request, 'Accès refusé.')
        return redirect('core:dashboard')
    cible = get_object_or_404(visibles, pk=pk)
    company = request.current_company

    autorise, raison = peut_supprimer(request.user, cible, company)
    if not autorise:
        messages.error(request, raison)
        return redirect('accounts:user_detail', pk=cible.pk)

    erreur_confirmation = ''
    if request.method == 'POST':
        saisie = (request.POST.get('confirmation') or '').strip()
        if saisie == cible.username:
            succes, message = supprimer_utilisateur(
                request.user, cible, company, _get_ip(request))
            if succes:
                messages.success(request, message)
                return redirect('accounts:user_list')
            messages.error(request, message)
            return redirect('accounts:user_detail', pk=cible.pk)
        erreur_confirmation = (
            f'Saisie incorrecte. Recopiez exactement « {cible.username} » '
            f'pour confirmer la suppression.')

    return render(request, 'accounts/user_confirm_delete.html', {
        'user_obj': cible,
        'inventaire': inventaire_cascade(cible),
        'erreur_confirmation': erreur_confirmation,
        'page_title': f'Supprimer {cible.get_full_name() or cible.username}',
    })


@login_required
@require_POST
def user_deactivate(request, pk):
    """Ferme l'acces sans rien detruire.

    Propose a cote de la suppression, et volontairement aussi accessible :
    dans la quasi-totalite des cas c'est ce qu'il faut faire. Un salarie
    parti garde ses heures pointees ; une cliente partie garde ses points.
    """
    visibles = _utilisateurs_visibles(request)
    if visibles is None:
        messages.error(request, 'Accès refusé.')
        return redirect('core:dashboard')
    cible = get_object_or_404(visibles, pk=pk)

    succes, message = desactiver_utilisateur(
        request.user, cible, request.current_company, _get_ip(request))
    if succes:
        messages.success(request, message)
    else:
        messages.error(request, message)
    return redirect('accounts:user_detail', pk=cible.pk)


@login_required
def missing_employee(request):
    """Page affichée quand un utilisateur non-admin n'a pas de fiche salarié."""
    return render(request, 'accounts/missing_employee.html', {
        'page_title': 'Compte non lié à un salarié',
    })


def _get_ip(request):
    """Déléguée : `X-Forwarded-For[0]` est écrit par le client."""
    from apps.core.client_ip import ip_du_client

    return ip_du_client(request)
