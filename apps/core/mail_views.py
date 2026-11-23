"""apps/core/mail_views.py — La page de réglage des courriels.

Montée sous /orion-admin/courriels/ (le préfixe est porté au point de
montage, dans erp_btp/urls.py).

Le contrôle de droits est importé d'apps.orion_ai.permissions, qui porte la
même fonction que apps/core/menu.py. Ce n'est pas le sens de dépendance
naturel — core ne devrait rien devoir à orion_ai — mais menu.py n'est pas
suivi par git : une page d'administration qui en dépendrait tomberait en
erreur 500 sur le serveur, où le fichier n'existe pas. Dupliquer un contrôle
de droits qui a déjà porté un défaut d'escalade serait pire que cette
inversion.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.core.models import CHIFFREMENT_MAIL_CHOIX, ReglagesMail
from apps.orion_ai.permissions import user_is_super_admin


PORT_MAXIMUM = 65535


def _entier(valeur, courant, minimum=0, maximum=None):
    """Un entier lisible et borné, sinon la valeur en place.

    Un champ vide, absent ou illisible CONSERVE ce qui est enregistré. Le
    remplacer par une valeur par défaut ferait d'un formulaire partiel une
    remise à zéro silencieuse — le défaut que la page Paramètres IA portait
    sur son fournisseur.
    """
    if valeur is None or str(valeur).strip() == '':
        return courant
    try:
        nombre = int(str(valeur).strip())
    except (TypeError, ValueError):
        return courant
    if nombre < minimum:
        return courant
    if maximum is not None and nombre > maximum:
        return courant
    return nombre


#: Les champs dont dépend le sort d'un envoi. Si l'un change, le dernier
#: diagnostic ne décrit plus les réglages affichés.
CHAMPS_QUI_DECIDENT = (
    'actif', 'hote', 'port', 'chiffrement', 'utilisateur',
    'mot_de_passe_chiffre', 'adresse_expediteur', 'delai_secondes',
)


def _empreinte(reglages):
    """Ce qui, dans ces réglages, décide qu'un envoi passe ou non."""
    return tuple(getattr(reglages, champ, None) for champ in CHAMPS_QUI_DECIDENT)


def _enregistrer(request, reglages):
    """Applique le formulaire aux réglages. Rend la liste des avertissements."""
    avertissements = []

    # L'ÉTAT D'AVANT, pour savoir si le dernier diagnostic reste valable.
    # Voir `_oublier_le_diagnostic` plus bas.
    avant = _empreinte(reglages)

    reglages.actif = request.POST.get('actif') == 'on'
    reglages.hote = (request.POST.get('hote') or '').strip()
    reglages.port = _entier(
        request.POST.get('port'), reglages.port, minimum=1,
        maximum=PORT_MAXIMUM)
    reglages.delai_secondes = _entier(
        request.POST.get('delai_secondes'), reglages.delai_secondes, minimum=1)

    chiffrement = (request.POST.get('chiffrement') or '').strip()
    if chiffrement in dict(CHIFFREMENT_MAIL_CHOIX):
        reglages.chiffrement = chiffrement

    reglages.utilisateur = (request.POST.get('utilisateur') or '').strip()
    reglages.adresse_expediteur = (
        request.POST.get('adresse_expediteur') or '').strip()

    # LE MOT DE PASSE N'EST JAMAIS RÉAFFICHÉ, donc un champ vide veut dire
    # « je n'y touche pas » et non « efface-le ». Sans cette règle,
    # enregistrer la page pour corriger un numéro de port effacerait
    # l'authentification SMTP, et l'envoi cesserait sans raison apparente.
    # L'effacement délibéré passe par une case à cocher.
    if request.POST.get('effacer_mot_de_passe') == 'on':
        reglages.mot_de_passe = ''
    else:
        nouveau = request.POST.get('mot_de_passe') or ''
        if nouveau:
            # Le chiffrement exige ORION_SECRET_ENCRYPTION_KEY, generee au
            # provisioning de l'appliance mais absente d'une installation
            # faite a la main. On refuse d'enregistrer en clair, et on dit
            # pourquoi : le reste du formulaire, lui, est conserve.
            try:
                reglages.mot_de_passe = nouveau
            except Exception as exc:
                avertissements.append(
                    'Le mot de passe n’a pas été enregistré : cette '
                    'installation n’a pas de clé de chiffrement '
                    f'(ORION_SECRET_ENCRYPTION_KEY). Détail : {exc}'
                )

    # ─── LE DIAGNOSTIC PÉRIMÉ, ET POURQUOI IL FALLAIT L'EFFACER ─────────
    #
    # LE DÉFAUT CONSTATÉ LE 23/11/2026. La page affiche `dernier_test_le` et
    # `derniere_erreur` tels qu'ils sont en base, et cette fonction ne les
    # touchait pas. Conséquence : après avoir corrigé l'adresse
    # d'expédition et enregistré, l'exploitant relisait LE MÊME message
    # d'échec, nommant l'ANCIENNE adresse —
    #
    #     SMTPSenderRefused: (550, ... 'no-reply@orion-erp.local')
    #
    # — alors qu'il venait d'y mettre « no.reply@s-peace.com ». Il en a
    # conclu, très logiquement, que l'ERP ignorait sa saisie. Elle était
    # pourtant bien enregistrée : c'est le diagnostic qui datait d'avant.
    #
    # Un verdict décrit les réglages sur lesquels il a été rendu. Dès que
    # l'un de ceux qui décident change, il ne décrit plus rien et le garder
    # affiché est pire que ne rien afficher : il envoie chercher une panne
    # qui vient peut-être d'être réparée.
    #
    # On l'oublie donc, et la page dit « aucune tentative depuis la
    # dernière modification », ce qui est exact et invite à tester.
    if _empreinte(reglages) != avant:
        reglages.dernier_test_le = None
        reglages.dernier_test_reussi = None
        reglages.derniere_erreur = ''

    reglages.save()

    # Avertir sans bloquer : un réglage incomplet est une étape normale de la
    # mise en route, pas une faute à refuser.
    if reglages.actif and not reglages.hote:
        avertissements.append(
            'L’envoi est activé mais aucun serveur SMTP n’est renseigné : '
            'rien ne partira.'
        )
    # L'EXPÉDITEUR EST LE CHAMP QU'ON OUBLIE, et son repli ne marche jamais
    # avec un fournisseur réel. Dit à l'enregistrement, et non seulement au
    # test : on ne teste pas toujours tout de suite, et un envoi réel peut
    # partir avant.
    if reglages.actif and reglages.hote:
        from apps.core.mail import _expediteur_inutilisable

        from django.conf import settings as reglages_django

        effectif = (reglages.adresse_expediteur
                    or getattr(reglages_django, 'DEFAULT_FROM_EMAIL', ''))
        motif = _expediteur_inutilisable(effectif, reglages.hote)
        if motif:
            avertissements.append(motif)

    if reglages.utilisateur and not reglages.mot_de_passe_enregistre:
        avertissements.append(
            'Un identifiant est renseigné sans mot de passe. La plupart des '
            'serveurs refuseront l’authentification.'
        )
    if reglages.mot_de_passe_illisible:
        avertissements.append(
            'Le mot de passe enregistré est illisible : la clé de chiffrement '
            'de cette installation a changé depuis son enregistrement. '
            'Saisissez-le à nouveau.'
        )
    if reglages.chiffrement == 'ssl' and reglages.port == 587:
        avertissements.append(
            'Le port 587 attend normalement STARTTLS, pas du SSL direct '
            '(465). La connexion risque d’expirer.'
        )
    if reglages.chiffrement == 'tls' and reglages.port == 465:
        avertissements.append(
            'Le port 465 attend normalement du SSL direct, pas STARTTLS '
            '(587). La connexion risque d’expirer.'
        )

    return avertissements


@login_required
def reglages_mail_view(request):
    if not user_is_super_admin(request.user):
        messages.error(request, 'Accès réservé au Super Admin.')
        return redirect('core:dashboard')

    reglages = ReglagesMail.get_global()

    if request.method == 'POST':
        action = request.POST.get('action') or 'enregistrer'

        for avertissement in _enregistrer(request, reglages):
            messages.warning(request, avertissement)

        if action == 'tester':
            from apps.core.mail import tester_l_envoi

            destinataire = (request.POST.get('destinataire') or '').strip()
            reussi, motif = tester_l_envoi(destinataire, reglages=reglages)
            if reussi:
                messages.success(request, motif)
            else:
                messages.error(request, f'Test en échec — {motif}')
        else:
            messages.success(request, 'Réglages des courriels enregistrés.')

        return redirect('core_mail:reglages')

    from apps.core.mail import chemin_du_repli, cle_de_chiffrement_presente

    repli = chemin_du_repli()
    return render(request, 'core/reglages_mail.html', {
        'page_title': 'Courriels',
        'reglages': reglages,
        'chiffrements': CHIFFREMENT_MAIL_CHOIX,
        'repli': repli,
        'repli_envoie_vraiment': 'smtp' in repli.lower(),
        'cle_presente': cle_de_chiffrement_presente(),
        'destinataire_propose': request.user.email or '',
    })
