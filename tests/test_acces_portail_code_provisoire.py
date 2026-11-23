# -*- coding: utf-8 -*-
"""L'accès à l'espace client : code provisoire par courriel, changé au premier accès.

**LE DÉFAUT PRINCIPAL, ET IL ÉTAIT COMPLET.** Les deux assistants de devis
publics — `apps/btp/guided_quote_views.py` et
`apps/websites/electricite_wizard_views.py` — portaient chacun leur copie de
`_create_portal_account`, et toutes deux faisaient :

    pwd = secrets.token_urlsafe(12)
    user = User.objects.create_user(..., password=pwd, ...)

`pwd` est une variable locale, jamais envoyée nulle part et perdue à la
sortie de la fonction. Chaque prospect qui remplissait un configurateur
recevait donc un compte d'espace client **actif auquel il ne pouvait jamais
se connecter** : pas de courriel, pas de lien, pas de code. Et rien ne le
signalait — ni à lui, ni à l'entreprise.

**LE DÉFAUT SECONDAIRE.** Le chemin administrateur
(`create_portal_account_for_customer`) envoyait bien un courriel, mais par
`signup_service._send_email`, qui passe `fail_silently=True` **et** rattrape
toute exception dans un `logger.warning`. L'écran annonçait donc « Un email
d'activation a été envoyé » quand rien n'était parti.

**POURQUOI UN CODE ET NON UN LIEN.** Un lien de définition de mot de passe
est un lien de connexion : `client_views.set_password` appelle
`login(request, user)` après l'enregistrement. Transféré, laissé dans un
historique ou lu dans une boîte partagée, il donne l'accès. Un code à saisir
passe par le formulaire de connexion normal, donc par la limitation d'essais
et le verrou de compte.

Ces tests passent par `django.core.mail.outbox` et par le client HTTP : ils
lisent le courriel réellement émis, s'en servent pour se connecter pour de
vrai, et vérifient qu'une page du portail renvoie bien vers le changement.
"""
import re

import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.test import override_settings
from django.urls import reverse

from apps.core.models import Company

pytestmark = pytest.mark.django_db

HOTES = ['testserver', 's-peace.com']


# ═══════════════════════════════════════════════════════════════════════════
#  Décor
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def entreprise(db):
    """Sans entreprise, `SetupRequiredMiddleware` renvoie tout vers /setup/."""
    from apps.core import middleware
    middleware._setup_complete_cache = None
    societe = Company.objects.create(name='Sparkling Peace', slug='sp-portail')
    yield societe
    middleware._setup_complete_cache = None


def _contact(email='client@portail.test'):
    return {
        'email': email, 'first_name': 'Nadia', 'last_name': 'Cliente',
        'phone': '0600000000',
    }


def _code_du_courriel(message):
    """Le code lu dans le corps TEXTE du message réellement émis.

    Lu dans le courriel émis, et non renvoyé par la fonction qui l'a
    engendré : c'est la seule façon de prouver que le code qui part est
    bien celui que le compte reconnaît. Les tester séparément laisserait
    passer une erreur de transmission entre les deux.
    """
    trouve = re.search(r'Code provisoire\s*:\s*(\S+)', message.body)
    assert trouve, 'aucun code dans le corps :\n%s' % message.body
    return trouve.group(1)


def _compte_de_portail(entreprise, email='client@portail.test'):
    """Un compte d'espace client créé par le chemin public, code envoyé."""
    from apps.portals.services.acces_portail import (
        creer_un_compte_depuis_un_devis,
    )

    mail.outbox = []
    compte, envoye, motif = creer_un_compte_depuis_un_devis(
        entreprise, _contact(email))
    assert compte is not None, motif
    assert envoye, motif
    return compte, _code_du_courriel(mail.outbox[0])


# ═══════════════════════════════════════════════════════════════════════════
#  1. Le devis public ouvre un accès ET l'envoie
# ═══════════════════════════════════════════════════════════════════════════

def test_un_compte_cree_depuis_un_devis_recoit_son_code(entreprise):
    """LE DÉFAUT CENTRAL : le mot de passe était engendré puis jeté."""
    mail.outbox = []
    from apps.portals.services.acces_portail import (
        creer_un_compte_depuis_un_devis,
    )

    compte, envoye, motif = creer_un_compte_depuis_un_devis(
        entreprise, _contact())

    assert compte is not None
    assert envoye is True, motif
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ['client@portail.test']


def test_le_code_du_courriel_ouvre_vraiment_le_compte(entreprise, client):
    """Le code émis et le code reconnu doivent être le même.

    Deux écritures séparées — `set_password` d'un côté, le corps du message
    de l'autre — peuvent parfaitement porter deux valeurs différentes.
    """
    compte, code = _compte_de_portail(entreprise)
    assert client.login(username=compte.user.username, password=code) is True


def test_le_compte_porte_l_obligation_de_changer(entreprise):
    compte, _code = _compte_de_portail(entreprise)
    compte.user.profile.refresh_from_db()
    assert compte.user.profile.doit_changer_de_mot_de_passe is True
    assert compte.user.profile.code_provisoire_envoye_le is not None


def test_le_courriel_porte_l_identifiant_et_un_lien_absolu(entreprise):
    """Un courriel se lit ailleurs que dans l'ERP.

    Un lien relatif n'y mène nulle part, et sans l'identifiant le client ne
    sait pas quoi taper — il essaiera son nom.
    """
    _compte, _code = _compte_de_portail(entreprise)
    corps = mail.outbox[0].body
    assert 'client@portail.test' in corps
    assert 'http' in corps


def test_le_courriel_ne_porte_aucun_lien_qui_connecte(entreprise):
    """Le lien doit mener à la CONNEXION, pas à une session ouverte.

    L'ancien message portait un lien `definir-mot-de-passe/<uid>/<token>/`,
    et la vue derrière appelle `login(request, user)`. Posséder l'URL
    suffisait donc à entrer.
    """
    _compte, _code = _compte_de_portail(entreprise)
    corps = mail.outbox[0].body + (mail.outbox[0].alternatives[0][0]
                                   if mail.outbox[0].alternatives else '')
    assert 'definir-mot-de-passe' not in corps
    assert reverse('client_portal:login') in corps


def test_le_message_porte_une_version_texte_et_une_version_html(entreprise):
    """`send_mail` avec un `html_message` seul envoie un corps vide.

    Les clients de messagerie qui refusent le HTML n'afficheraient rien, et
    certains filtres notent défavorablement un message sans alternative
    texte. Un courriel qui porte un code d'accès ne peut pas se permettre
    de finir en indésirable.
    """
    _compte, code = _compte_de_portail(entreprise)
    message = mail.outbox[0]
    assert code in message.body, 'le corps texte ne porte pas le code'
    assert message.alternatives, 'aucune version HTML'
    assert code in message.alternatives[0][0]


def test_une_adresse_deja_connue_n_ouvre_pas_un_second_compte(entreprise):
    """Conservé du code d'origine, et volontaire.

    Un prospect qui redemande un devis a déjà son accès : lui réenvoyer un
    code invaliderait celui qu'il utilise peut-être déjà.
    """
    from apps.portals.services.acces_portail import (
        creer_un_compte_depuis_un_devis,
    )

    _compte_de_portail(entreprise)
    mail.outbox = []
    compte, envoye, motif = creer_un_compte_depuis_un_devis(
        entreprise, _contact())

    assert compte is None
    assert envoye is False
    assert mail.outbox == []
    assert 'existe' in motif


def test_un_contact_sans_adresse_ne_cree_rien(entreprise):
    from apps.portals.services.acces_portail import (
        creer_un_compte_depuis_un_devis,
    )

    compte, envoye, _motif = creer_un_compte_depuis_un_devis(
        entreprise, _contact(email=''))
    assert compte is None
    assert envoye is False


def test_un_envoi_qui_echoue_laisse_le_compte_ferme(entreprise, monkeypatch):
    """L'ORDRE DES DEUX ÉCRITURES, et pourquoi il est celui-ci.

    Le code est posé AVANT d'être envoyé. Si l'envoi échoue, le compte
    porte un code que personne ne connaît — inutilisable, donc l'état sûr.
    Dans l'autre ordre, un envoi réussi suivi d'une écriture échouée
    laisserait un code valide dans une boîte et un compte qui ne le
    reconnaît pas : le pire des deux, car l'exploitant aurait vu « envoyé ».

    ET LA DEMANDE DE DEVIS NE TOMBE PAS. Ces appels surviennent au milieu
    du parcours d'un visiteur anonyme qui vient de remplir quatre écrans :
    lever ici lui afficherait une erreur 500 et perdrait sa demande.
    """
    from apps.portals.services import acces_portail

    def refuse(*args, **kwargs):
        raise OSError('serveur SMTP injoignable')

    monkeypatch.setattr(acces_portail, 'send_mail', refuse)

    compte, envoye, motif = acces_portail.creer_un_compte_depuis_un_devis(
        entreprise, _contact())

    assert compte is not None, 'la demande de devis a été perdue'
    assert envoye is False
    assert 'SMTP' in motif
    assert compte.user.profile.doit_changer_de_mot_de_passe is True


def test_un_backend_muet_n_est_pas_lu_comme_un_succes(entreprise, monkeypatch):
    """Zéro destinataire accepté n'est pas un envoi.

    `signup_service._send_email` passe `fail_silently=True`, ce qui rend 0
    sans lever. « Les mails ne fonctionnent pas » sans le moindre message
    vient de là.
    """
    from apps.portals.services import acces_portail

    monkeypatch.setattr(acces_portail, 'send_mail', lambda *a, **k: 0)

    compte, envoye, motif = acces_portail.creer_un_compte_depuis_un_devis(
        entreprise, _contact())
    assert compte is not None
    assert envoye is False
    assert motif


# ═══════════════════════════════════════════════════════════════════════════
#  2. Le changement est obligatoire, et il a lieu DANS le portail
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def client_connecte(entreprise, client):
    """Un client d'espace client, connecté avec son code provisoire."""
    compte, code = _compte_de_portail(entreprise)
    assert client.login(username=compte.user.username, password=code)
    return {'client': client, 'compte': compte, 'code': code}


@override_settings(ALLOWED_HOSTS=HOTES)
def test_une_page_du_portail_renvoie_vers_le_changement(client_connecte):
    """Et vers CELUI DU PORTAIL, pas celui de l'ERP.

    L'écran de l'ERP étend `erp_base.html` : le client y verrait le menu de
    l'ERP, le sélecteur d'entreprise et le fil d'ariane d'un salarié. Pire,
    les liens de ce menu le renverraient vers des pages qui le
    redirigeraient ici — une boucle visible.
    """
    reponse = client_connecte['client'].get(
        reverse('client_portal:dashboard'))

    assert reponse.status_code == 302
    assert reponse['Location'] == reverse(
        'client_portal:changer_mot_de_passe'), reponse['Location']


@override_settings(ALLOWED_HOSTS=HOTES)
def test_un_salarie_va_toujours_vers_l_ecran_de_l_erp(entreprise, client):
    """La nouvelle route ne doit pas détourner les comptes de l'ERP.

    Les deux familles partagent le drapeau `doit_changer_de_mot_de_passe` ;
    seule la destination diffère, et elle est décidée par la présence d'un
    `portal_account`.
    """
    from apps.accounts.services.code_provisoire import poser_un_code

    salarie = User.objects.create_user(
        username='salarie-portail', email='s@portail.test', password='x')
    salarie.profile.companies.add(entreprise)
    salarie.profile.current_company = entreprise
    salarie.profile.save()
    code = poser_un_code(salarie)

    assert client.login(username='salarie-portail', password=code)
    reponse = client.get(reverse('accounts:profile'))

    assert reponse.status_code == 302
    assert reponse['Location'] == reverse('accounts:changer_mot_de_passe')


@override_settings(ALLOWED_HOSTS=HOTES)
def test_l_ecran_du_portail_n_est_pas_redirige_vers_lui_meme(client_connecte):
    """Sans l'exemption, la page bouclerait et le navigateur abandonnerait."""
    reponse = client_connecte['client'].get(
        reverse('client_portal:changer_mot_de_passe'))

    assert reponse.status_code == 200
    assert 'Première connexion' in reponse.content.decode()


@override_settings(ALLOWED_HOSTS=HOTES)
def test_la_deconnexion_du_portail_reste_atteignable(client_connecte):
    """La seule sortie honnête pour qui ne veut pas changer maintenant.

    Sans cette exemption, le client serait enfermé dans la page sans pouvoir
    quitter sa session — sur un poste partagé, c'est un vrai problème.
    """
    reponse = client_connecte['client'].get(reverse('client_portal:logout'))
    assert reponse.status_code in (200, 302)
    if reponse.status_code == 302:
        assert 'mot-de-passe' not in reponse['Location']


@override_settings(ALLOWED_HOSTS=HOTES)
def test_le_lien_d_invitation_signe_reste_atteignable(client_connecte):
    """Les invitations déjà envoyées ne doivent pas casser.

    `definir-mot-de-passe/` règle le mot de passe par un autre chemin et
    connecte lui-même : le rediriger rendrait inutilisables les liens
    expédiés avant ce changement.
    """
    from django.contrib.auth.tokens import default_token_generator
    from django.utils.encoding import force_bytes
    from django.utils.http import urlsafe_base64_encode

    utilisateur = client_connecte['compte'].user
    url = reverse('client_portal:set_password', kwargs={
        'uidb64': urlsafe_base64_encode(force_bytes(utilisateur.pk)),
        'token': default_token_generator.make_token(utilisateur),
    })
    reponse = client_connecte['client'].get(url)
    assert reponse.status_code == 200


@override_settings(ALLOWED_HOSTS=HOTES)
def test_changer_leve_l_obligation_et_garde_la_session(client_connecte):
    """Changer son mot de passe déconnecte, sauf si l'empreinte est refaite.

    La session porte une empreinte du mot de passe : dès qu'il change,
    Django ferme la session à la requête SUIVANTE. Le client serait renvoyé
    à la connexion juste après avoir réussi — et le lirait comme un échec.
    """
    reponse = client_connecte['client'].post(
        reverse('client_portal:changer_mot_de_passe'), {
            'old_password': client_connecte['code'],
            'new_password1': 'bourrasque-de-platre-74',
            'new_password2': 'bourrasque-de-platre-74',
        })
    assert reponse.status_code == 302

    compte = client_connecte['compte']
    compte.user.profile.refresh_from_db()
    assert compte.user.profile.doit_changer_de_mot_de_passe is False

    # La requête SUIVANTE est celle qui révèle une session perdue.
    suite = client_connecte['client'].get(reverse('client_portal:dashboard'))
    assert suite.status_code == 200, (
        'la session a été fermée : update_session_auth_hash manque')


@override_settings(ALLOWED_HOSTS=HOTES)
def test_reposer_le_code_recu_est_refuse(client_connecte):
    """Sans ce contrôle, l'obligation se lève sans que rien ne change.

    `PasswordChangeForm` ne compare pas le nouveau mot de passe à l'ancien :
    ressaisir le code reçu satisfaisait le formulaire et laissait en place
    un mot de passe engendré par la machine, qui dort dans une boîte de
    réception.
    """
    reponse = client_connecte['client'].post(
        reverse('client_portal:changer_mot_de_passe'), {
            'old_password': client_connecte['code'],
            'new_password1': client_connecte['code'],
            'new_password2': client_connecte['code'],
        })

    assert reponse.status_code == 200
    client_connecte['compte'].user.profile.refresh_from_db()
    assert client_connecte[
        'compte'].user.profile.doit_changer_de_mot_de_passe is True


@override_settings(ALLOWED_HOSTS=HOTES)
def test_un_mot_de_passe_faible_est_refuse(client_connecte):
    """Les validateurs de Django s'appliquent, par `PasswordChangeForm`.

    La vue `set_password` voisine se contente de « 8 caractères minimum » :
    « 12345678 » y passe. On ne reproduit pas cette règle-là.
    """
    reponse = client_connecte['client'].post(
        reverse('client_portal:changer_mot_de_passe'), {
            'old_password': client_connecte['code'],
            'new_password1': '12345678',
            'new_password2': '12345678',
        })

    assert reponse.status_code == 200
    client_connecte['compte'].user.profile.refresh_from_db()
    assert client_connecte[
        'compte'].user.profile.doit_changer_de_mot_de_passe is True


@override_settings(ALLOWED_HOSTS=HOTES)
def test_ouvrir_la_page_sans_rien_envoyer_ne_leve_rien(client_connecte):
    """Lever l'obligation à l'affichage suffirait à s'en débarrasser."""
    client_connecte['client'].get(
        reverse('client_portal:changer_mot_de_passe'))
    client_connecte['compte'].user.profile.refresh_from_db()
    assert client_connecte[
        'compte'].user.profile.doit_changer_de_mot_de_passe is True


@override_settings(ALLOWED_HOSTS=HOTES)
def test_le_changement_vaut_verification_de_l_adresse(client_connecte):
    """Avoir saisi le code reçu PROUVE que l'adresse fonctionne.

    C'est ce que fait déjà `set_password` pour le lien d'invitation : ne pas
    le faire ici laisserait des comptes marqués « adresse non vérifiée »
    alors que leur titulaire a lu un courriel envoyé à cette adresse.
    """
    compte = client_connecte['compte']
    assert compte.is_email_verified is False

    client_connecte['client'].post(
        reverse('client_portal:changer_mot_de_passe'), {
            'old_password': client_connecte['code'],
            'new_password1': 'bourrasque-de-platre-74',
            'new_password2': 'bourrasque-de-platre-74',
        })

    compte.refresh_from_db()
    assert compte.is_email_verified is True


# ═══════════════════════════════════════════════════════════════════════════
#  3. Gardes de régression
# ═══════════════════════════════════════════════════════════════════════════

def _code_executable(module):
    """La source du module SANS ses commentaires ni ses docstrings.

    POURQUOI CE DÉTOUR. Une première version de ces deux gardes lisait
    `inspect.getsource` tel quel, et échouait sur mes propres docstrings :
    elles CITENT le code fautif pour expliquer ce qui a été corrigé. Une
    garde qui confond « le code fait ceci » et « le commentaire parle de
    ceci » ne garde rien — et pousse à retirer l'explication pour la faire
    taire, c'est-à-dire exactement le contraire du but.

    `ast.unparse` reconstruit depuis l'arbre : les commentaires ont déjà
    disparu au parsing, et on retire les docstrings à la main.
    """
    import ast
    import inspect

    arbre = ast.parse(inspect.getsource(module))
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, (ast.Module, ast.FunctionDef,
                                  ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        corps = noeud.body
        if (corps and isinstance(corps[0], ast.Expr)
                and isinstance(corps[0].value, ast.Constant)
                and isinstance(corps[0].value.value, str)):
            # Remplacé par `pass` et non supprimé : un corps vide est
            # invalide, et `ast.unparse` lèverait.
            noeud.body = corps[1:] or [ast.Pass()]
    return ast.unparse(arbre)


def test_les_deux_assistants_ne_jettent_plus_de_mot_de_passe():
    """Mesuré sur la SOURCE : c'est le défaut exact qu'on vient de fermer.

    Un `secrets.token_urlsafe` posé comme mot de passe sans être envoyé
    recréerait des comptes inaccessibles, en silence. Les deux fichiers
    sont vérifiés, parce qu'ils portaient la MÊME faute en deux
    exemplaires — corriger l'un aurait laissé l'autre.
    """
    from apps.btp import guided_quote_views
    from apps.websites import electricite_wizard_views

    for module in (guided_quote_views, electricite_wizard_views):
        source = _code_executable(module)
        assert 'token_urlsafe' not in source, (
            '%s engendre encore un mot de passe sans l’envoyer'
            % module.__name__)
        assert 'creer_un_compte_depuis_un_devis' in source, (
            '%s n’appelle pas le service d’accès au portail'
            % module.__name__)


def test_le_service_refuse_l_envoi_silencieux():
    """`fail_silently=True` est précisément ce qu'on a retiré.

    `signup_service._send_email` le passe, et rattrape en plus toute
    exception : l'appelant ne peut pas savoir si le courriel est parti.
    Ce module-ci doit rendre le motif.
    """
    from apps.portals.services import acces_portail

    source = _code_executable(acces_portail)
    assert 'fail_silently=False' in source
    assert 'fail_silently=True' not in source


def test_le_code_est_engendre_par_le_module_de_l_erp():
    """Un seul alphabet, une seule longueur, un seul drapeau.

    Deux implémentations du même code provisoire divergeraient, et c'est
    celle qu'on regarde le moins qui garderait le défaut.
    """
    from apps.accounts.services import code_provisoire
    from apps.portals.services import acces_portail

    assert acces_portail.engendrer_un_code is code_provisoire.engendrer_un_code
    assert acces_portail.poser_un_code is code_provisoire.poser_un_code


def test_un_compte_sans_portail_n_est_pas_pris_pour_un_client(entreprise):
    from apps.portals.services.acces_portail import est_un_client_de_portail

    salarie = User.objects.create_user(username='pas-client', password='x')
    assert est_un_client_de_portail(salarie) is False
    assert est_un_client_de_portail(None) is False
