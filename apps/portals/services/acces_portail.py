"""L'accès à l'espace client : un code provisoire par courriel, changé au premier accès.

**CE QUE CE MODULE REMPLACE.** `signup_service.create_portal_account_for_customer`
créait le compte avec un mot de passe inutilisable, puis envoyait un lien de
définition de mot de passe signé par `default_token_generator`. Le montage
fonctionnait, mais portait trois défauts :

1. **L'envoi était silencieux.** `signup_service._send_email` passe
   `fail_silently=True` ET rattrape toute exception dans un `logger.warning`.
   L'écran annonçait donc « Un email d'activation a été envoyé » quand rien
   n'était parti. C'est le défaut que `apps/core/mail.py` documente déjà :
   « quatre appels du dépôt passent `fail_silently=True`, dont l'invitation
   au portail client. Les mails ne fonctionnent pas sans le moindre message
   vient de là. »

2. **Un lien de définition de mot de passe est un lien de connexion.** Il
   ouvre une session sans rien demander d'autre que de posséder l'URL : la
   vue `set_password` appelle `login(request, user)` après l'enregistrement.
   Transféré, laissé dans un historique ou récupéré dans une boîte partagée,
   il donne l'accès. Un code à saisir, lui, passe par le formulaire de
   connexion normal — donc par la limitation d'essais et le verrou de compte.

3. **Rien n'obligeait à changer ensuite**, puisque le mot de passe choisi
   par le lien était déjà celui du client. Ce n'est pas un défaut en soi,
   mais l'ERP s'est doté depuis d'une obligation de changement à la première
   connexion, et deux mécanismes différents pour deux familles de comptes
   finissent par ne plus se ressembler.

**LE CODE EST ENGENDRÉ PAR `apps.accounts.services.code_provisoire`**, et
non réécrit ici. C'est le même besoin — un mot de passe à usage unique,
lisible dans un courriel et recopié à la main — donc le même alphabet sans
`O`/`0` ni `I`/`l`/`1`, la même longueur, et la même pose du drapeau
`doit_changer_de_mot_de_passe` sur le profil. Deux implémentations
divergeraient, et c'est celle qu'on regarde le moins qui garderait le
défaut.

**POURQUOI LE DRAPEAU SUR `UserProfile` MARCHE ICI AUSSI.** Un client de
portail est un compte Django ordinaire — `_get_portal_account` ne le
reconnaît qu'une fois `request.user.is_authenticated` — et le signal
`create_user_profile` donne un profil à TOUT utilisateur. Le drapeau est
donc disponible sans rien ajouter au modèle du portail.

Ce qui change, c'est la destination : `ChangementDeMotDePasseRequisMiddleware`
renvoie un client de portail vers `client_portal:changer_mot_de_passe` et non
vers l'écran de l'ERP, où il n'a rien à faire et dont le gabarit suppose un
salarié.
"""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse

from apps.accounts.services.code_provisoire import engendrer_un_code, poser_un_code

journal = logging.getLogger('orion')

GABARIT = 'client_portal/emails/acces_portail_code.html'


def langues_proposables():
    """Les langues qu'on peut réellement servir, pour le sélecteur.

    **POURQUOI PAS `settings.LANGUAGES` TEL QUEL.** Il en déclare sept, et
    `locale/` n'en contient que cinq : le néerlandais n'a **aucun
    catalogue**. L'offrir laisserait choisir une langue qui retombe en
    silence sur le français — l'exploitant croirait avoir réglé la langue
    de son client, et le client recevrait du français sans que rien ne le
    signale. C'est exactement le piège « enveloppé n'est pas traduit »,
    déplacé dans l'interface.

    Le français n'a pas de catalogue et reste proposé : il est la LANGUE
    SOURCE, écrite dans le code, donc toujours disponible.

    Mesuré sur le disque à chaque appel, et non figé à l'import : un
    catalogue ajouté par une mise à jour apparaît alors de lui-même, sans
    qu'on retouche au code.
    """
    import os

    disponibles = {settings.LANGUAGE_CODE}
    for dossier in getattr(settings, 'LOCALE_PATHS', []):
        try:
            for code in os.listdir(dossier):
                if os.path.isfile(os.path.join(
                        dossier, code, 'LC_MESSAGES', 'django.mo')):
                    disponibles.add(code)
        except OSError:
            # Dossier absent sur une installation partielle : on ne fait pas
            # tomber un écran pour une liste de langues.
            continue

    return [(code, nom) for code, nom in settings.LANGUAGES
            if code in disponibles]


def langue_valable(code, defaut=None):
    """Le code s'il est servable, sinon le défaut de l'installation.

    Posé en un seul endroit parce que trois chemins le demandent : le
    formulaire de la fiche client, la création depuis un devis, et le
    renvoi d'un code. Trois validations écrites séparément finiraient par
    ne plus accepter la même chose.
    """
    defaut = defaut or settings.LANGUAGE_CODE
    servables = {code_langue for code_langue, _nom in langues_proposables()}
    code = (code or '').strip().lower()
    return code if code in servables else defaut


def _adresse_de_connexion(request=None, base_url=''):
    """L'adresse complète de la connexion au portail.

    Un courriel se lit ailleurs que dans l'ERP : un lien relatif n'y mène
    nulle part.

    TROIS SOURCES, DANS CET ORDRE. La requête quand on l'a ; sinon le
    `base_url` que l'appelant a déjà calculé — `create_portal_account_for_customer`
    le reçoit de sa vue, et le gâcher aurait obligé à deviner l'hôte alors
    qu'il était connu ; sinon le premier hôte admis, ce qui vaut mieux qu'un
    lien cassé.
    """
    chemin = reverse('client_portal:login')
    if request is not None:
        return request.build_absolute_uri(chemin)

    base = (base_url or '').rstrip('/')
    if base:
        return '%s%s' % (base, chemin)

    hotes = [h for h in getattr(settings, 'ALLOWED_HOSTS', []) if h != '*']
    if hotes:
        return 'https://%s%s' % (hotes[0], chemin)
    return chemin


def corps_du_message(compte, code, request=None, base_url=''):
    """Le texte envoyé, en clair. Séparé pour être lisible et testable.

    Une version TEXTE est composée en plus du HTML, et ce n'est pas une
    politesse : `send_mail` appelé avec un `html_message` seul envoie un
    corps vide aux clients de messagerie qui refusent le HTML, et certains
    filtres anti-indésirables notent défavorablement un message sans
    alternative texte — un courriel qui porte un code d'accès ne peut pas
    se permettre de finir en indésirable.

    **TRADUISIBLE, et c'était le point manquant.** Ces phrases étaient
    écrites en français en dur : `override(langue_du_client)` n'avait alors
    aucune prise sur elles, et le message partait en français quelle que
    soit la langue réglée sur le compte. Le gabarit HTML, lui, portait déjà
    ses `{% trans %}` — l'une des deux moitiés était traduite et l'autre
    pas, ce qui aurait donné un message bilingue.

    **DÉCOUPÉ EN PHRASES ENTIÈRES, et non en morceaux.** Une chaîne
    « Identifiant : » séparée de sa valeur se traduit mal : plusieurs
    langues placent le deux-points autrement, et l'allemand compose
    souvent le mot différemment selon ce qui suit. Chaque `%s` reste donc
    dans sa phrase.
    """
    from django.utils.translation import gettext as _t

    nom = (compte.first_name or compte.full_name or compte.email).strip()
    entreprise = compte.company.name
    lignes = [
        _t('Bonjour %(nom)s,') % {'nom': nom},
        '',
        _t('Votre espace client %(entreprise)s est ouvert.')
        % {'entreprise': entreprise},
        '',
        _t('Identifiant : %(identifiant)s') % {'identifiant': compte.email},
        _t('Code provisoire : %(code)s') % {'code': code},
        '',
        _t('Connectez-vous ici : %(url)s')
        % {'url': _adresse_de_connexion(request, base_url)},
        '',
        _t('Ce code ne sert qu’une fois : dès votre première connexion, '
           'l’application vous demandera de choisir votre propre mot de '
           'passe. Personne d’autre que vous ne le connaît — pas même '
           '%(entreprise)s.') % {'entreprise': entreprise},
        '',
        _t('Vous y retrouverez l’avancement de vos chantiers, vos '
           'documents, vos plannings et vos échanges avec l’équipe.'),
        '',
        _t('Si vous n’attendiez pas ce message, ignorez-le et signalez-le '
           'à %(entreprise)s : le compte restera inutilisable tant que '
           'personne ne s’y connecte.') % {'entreprise': entreprise},
        '',
    ]
    return '\n'.join(lignes)


def envoyer_le_code(compte, code, request=None, base_url=''):
    """Envoie le code au client. Rend (envoyé, motif de l'échec).

    **`fail_silently=False`, ET C'EST TOUT L'INTÉRÊT.**
    `signup_service._send_email` passe `True` et rattrape en plus toute
    exception : l'appelant reçoit `None` quoi qu'il arrive, et l'écran
    annonce un envoi qui n'a pas eu lieu. Un compte reste alors muet, son
    titulaire n'a rien reçu, et aucune page ne dit pourquoi.

    On veut donc le motif, pour l'afficher à l'exploitant et lui permettre
    de renvoyer un code.

    **COMPOSÉ DANS LA LANGUE DU CLIENT, ET C'EST LE POINT DÉLICAT.** Ce
    message est fabriqué pendant la requête d'un SALARIÉ de l'ERP : la
    langue active est la sienne. Sans `override`, un exploitant français
    qui ouvre l'accès d'un client portugais lui envoie du français — et
    l'écran lui dit « envoyé », donc rien ne le signale.

    L'`override` enveloppe le sujet, le texte ET le gabarit HTML. En
    omettre un donnerait un message bilingue, ce qui est pire que pas de
    traduction du tout : le client y verrait une erreur de l'entreprise.
    """
    from django.utils.translation import gettext, override

    if not compte.email:
        return False, 'aucune adresse de courriel sur ce compte'

    langue = langue_valable(getattr(compte, 'langue', ''))

    with override(langue):
        sujet = gettext('Votre espace client — %(entreprise)s') % {
            'entreprise': compte.company.name}
        texte = corps_du_message(compte, code, request, base_url)
        try:
            html = render_to_string(GABARIT, {
                'compte': compte,
                'prenom': compte.first_name or compte.full_name,
                'company': compte.company,
                'code': code,
                'url_connexion': _adresse_de_connexion(request, base_url),
            })
        except Exception as exc:
            # Un gabarit absent ou cassé ne doit pas empêcher la remise : le
            # texte porte déjà tout ce qu'il faut pour se connecter.
            journal.warning('Gabarit %s illisible (%s) : envoi en texte seul.',
                            GABARIT, exc)
            html = None

    try:
        envoyes = send_mail(
            subject=sujet,
            message=texte,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
            recipient_list=[compte.email],
            html_message=html,
            fail_silently=False,
        )
    except Exception as exc:
        journal.warning('Code portail non envoyé à %s (compte %s) : %s',
                        compte.email, compte.pk, exc)
        return False, str(exc)

    if not envoyes:
        # Le backend n'a levé aucune erreur et n'a rien envoyé. On refuse de
        # le lire comme un succès.
        journal.warning('Code portail : aucun destinataire accepté pour %s.',
                        compte.email)
        return False, 'le serveur de courriel n’a accepté aucun destinataire'

    return True, ''


def fixer_la_langue(compte, langue):
    """Enregistre la langue du compte si elle est servable.

    Appelée avant tout envoi : la langue doit être sur l'objet au moment où
    `envoyer_le_code` la lit, sinon le courriel part dans l'ancienne et
    l'écran annonce la nouvelle.

    `update_fields` plutôt qu'un `save()` complet : ce compte vient parfois
    d'une instance chargée ailleurs, et réécrire tous ses champs pourrait
    défaire une modification concurrente — c'est le défaut que
    `apps/accounts/signals.py` porte sur `UserProfile`.
    """
    valable = langue_valable(langue, defaut=getattr(compte, 'langue', ''))
    if valable != getattr(compte, 'langue', None):
        compte.langue = valable
        compte.save(update_fields=['langue'])
    return valable


def creer_et_envoyer(compte, request=None, base_url='', langue=None):
    """Engendre un code pour ce compte de portail, le pose, l'envoie.

    L'ORDRE COMPTE, et il est délibérément celui-ci : le code est posé AVANT
    d'être envoyé. Si l'envoi échoue, le compte porte un code que personne ne
    connaît — donc inutilisable, ce qui est l'état sûr. Dans l'autre ordre,
    un envoi réussi suivi d'une écriture échouée laisserait un code valide
    dans une boîte de courriel et un compte qui ne le reconnaît pas : le pire
    des deux, car l'exploitant aurait vu « envoyé » et n'aurait aucune raison
    de recommencer.

    `langue` à None NE TOUCHE À RIEN : un renvoi de code ne doit pas
    réinitialiser la langue d'un client qu'on avait réglée à l'ouverture du
    compte. Seul un choix explicite la change.
    """
    if langue:
        fixer_la_langue(compte, langue)
    code = poser_un_code(compte.user)
    return envoyer_le_code(compte, code, request, base_url)


def _identifiant_libre(email):
    """Un nom d'utilisateur disponible, dérivé de l'adresse.

    Repris des deux assistants de devis, qui en portaient chacun une copie.
    La boucle n'est pas une élégance : `User.username` est unique, et deux
    prospects chez « @gmail.com » partagent très souvent la partie gauche.
    """
    from django.contrib.auth.models import User

    base = (email or '').split('@')[0] or 'client'
    identifiant, index = base, 1
    while User.objects.filter(username=identifiant).exists():
        identifiant = '%s%d' % (base, index)
        index += 1
    return identifiant


def creer_un_compte_depuis_un_devis(company, contact, origine_devis=True,
                                    request=None):
    """Crée un compte d'espace client pour un prospect, et LUI ENVOIE SON CODE.

    **LE DÉFAUT QUE CECI CORRIGE, et il était complet.** Les deux
    assistants de devis publics — `apps/btp/guided_quote_views.py` et
    `apps/websites/electricite_wizard_views.py` — portaient chacun leur
    copie de cette fonction, et toutes deux faisaient :

        pwd = secrets.token_urlsafe(12)
        user = User.objects.create_user(..., password=pwd, ...)

    `pwd` est une variable locale, jamais envoyée nulle part et perdue à la
    sortie de la fonction. Chaque prospect qui remplissait un configurateur
    recevait donc un compte d'espace client ACTIF auquel il ne pouvait
    JAMAIS se connecter : pas de courriel, pas de lien, pas de code. Et rien
    ne le signalait — ni à lui, ni à l'entreprise.

    **UN SEUL EXEMPLAIRE, ICI.** Les deux copies étaient identiques à
    l'espacement près ; corriger l'une aurait laissé l'autre. C'est le même
    motif que les trois audits de sécurité de ce dépôt.

    **L'ÉCHEC D'ENVOI NE FAIT PAS TOMBER LA DEMANDE DE DEVIS.** Ces deux
    appels surviennent au milieu du parcours d'un visiteur anonyme qui vient
    de remplir quatre écrans. Lever ici lui afficherait une erreur 500 et
    perdrait sa demande, pour un serveur de courriel momentanément muet — on
    journalise, et la demande de devis aboutit. L'entreprise peut renvoyer
    un code depuis l'ERP.

    Rend (compte, envoyé, motif). `compte` vaut None si rien n'a été créé.
    """
    from django.contrib.auth.models import User

    from apps.portals.models import ClientPortalAccount

    email = (contact.get('email') or '').strip()
    if not email:
        return None, False, 'aucune adresse de courriel'

    # Conservé des deux originaux : une adresse déjà connue n'ouvre pas un
    # second compte. Un prospect qui redemande un devis ne reçoit donc rien,
    # ce qui est volontaire — il a déjà son accès.
    if User.objects.filter(email=email).exists():
        return None, False, 'un compte existe déjà pour cette adresse'

    user = User.objects.create_user(
        username=_identifiant_libre(email),
        email=email,
        first_name=contact.get('first_name', ''),
        last_name=contact.get('last_name', ''),
    )
    # `create_user` sans mot de passe en pose un inutilisable : le compte
    # est donc fermé jusqu'à ce que `creer_et_envoyer` pose le code. C'est
    # l'état sûr si la suite échoue.

    # LA LANGUE DU VISITEUR EST LA MEILLEURE VALEUR DONT ON DISPOSE ICI.
    #
    # Personne ne la choisit pour lui sur ce chemin : il vient de remplir
    # quatre écrans dans une langue, et c'est celle qu'il lit. La prendre
    # évite de lui envoyer son code d'accès en français parce que
    # l'installation est française.
    #
    # `get_language()` rend la langue active, celle que
    # `OrionLanguageMiddleware` a retenue pour cette requête — donc celle du
    # site vitrine visité, avec ses propres règles.
    from django.utils.translation import get_language

    compte = ClientPortalAccount.objects.create(
        company=company, user=user, email=email,
        first_name=contact.get('first_name', ''),
        last_name=contact.get('last_name', ''),
        phone=contact.get('phone', ''),
        langue=langue_valable(get_language()),
        created_from_guided_quote=origine_devis,
    )

    try:
        envoye, motif = creer_et_envoyer(compte, request)
    except Exception as exc:
        journal.warning('Code portail : echec inattendu pour %s : %s',
                        email, exc)
        return compte, False, str(exc)

    if not envoye:
        journal.warning(
            'Compte portail %s cree depuis un devis, code NON envoye : %s',
            email, motif)
    return compte, envoye, motif


def est_un_client_de_portail(utilisateur):
    """Vrai si ce compte est un client d'espace client et non un salarié.

    Décide la destination du passage obligé de changement de mot de passe.
    Lu par l'attribut de relation (`portal_account`, un OneToOne) plutôt que
    par une requête : c'est la même vérification que `_get_portal_account`
    du portail, et la faire autrement ferait divorcer les deux.
    """
    if not (utilisateur and getattr(utilisateur, 'is_authenticated', False)):
        return False
    return getattr(utilisateur, 'portal_account', None) is not None


__all__ = [
    'GABARIT', 'corps_du_message', 'creer_et_envoyer',
    'creer_un_compte_depuis_un_devis', 'engendrer_un_code', 'envoyer_le_code',
    'est_un_client_de_portail', 'poser_un_code',
]
