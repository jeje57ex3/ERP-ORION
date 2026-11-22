"""Créer un compte sans mot de passe : code par courriel, changé au premier accès.

**Ce qui est demandé, et ce que cela remplace.** L'écran de création
d'utilisateur demandait un mot de passe à l'administrateur, qui devait
ensuite le transmettre au nouvel arrivant. Trois défauts superposés :
l'administrateur connaissait le mot de passe de quelqu'un d'autre, celui-ci
transitait par un canal que personne ne maîtrise, et rien n'obligeait jamais
à le changer.

Désormais : le formulaire demande tout *sauf* le mot de passe, un code
aléatoire part à l'adresse saisie, et il doit être remplacé à la première
connexion.

**Comment ces tests sont écrits, et pourquoi ainsi.** Ils passent par le
client HTTP et par `django.core.mail.outbox` : ils lisent le courriel
réellement émis, s'en servent pour se connecter pour de vrai, et vérifient
qu'une page quelconque renvoie bien vers le changement. Vérifier qu'un
drapeau existe ou qu'un middleware est déclaré n'aurait rien prouvé — c'est
la leçon des trois audits de sécurité de ce dépôt, où un contrôle juste
était à chaque fois contourné par le chemin réel.
"""

import re

import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.urls import reverse

from apps.core.models import Company


# ═══════════════════════════════════════════════════════════════════════════
#  Décors
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def entreprise(db):
    """Sans entreprise, `SetupRequiredMiddleware` renvoie tout vers /setup/.

    Un 302 vers /setup/ se lit comme un refus d'accès alors que c'en est
    l'inverse : la vue n'a pas été atteinte. Dix tests du deuxième audit
    de sécurité sont tombés dans ce piège.
    """
    from apps.core import middleware
    middleware._setup_complete_cache = None
    societe = Company.objects.create(name='Code Provisoire SA',
                                     slug='code-provisoire')
    yield societe
    middleware._setup_complete_cache = None


@pytest.fixture
def patron(db, client, entreprise):
    """Un administrateur capable d'atteindre `user_create`.

    LE PROFIL EST MODIFIÉ PAR `utilisateur.profile`, et non par une
    instance obtenue séparément. Ce n'est pas un détail de style :
    `apps/accounts/signals.py` réenregistre le profil ENTIER à chaque
    sauvegarde de `User`, depuis l'instance mise en cache sur lui —

        @receiver(post_save, sender=User)
        def save_user_profile(sender, instance, **kwargs):
            instance.profile.save()

    — et `force_login` met à jour `last_login`, donc sauvegarde `User`.
    Un rôle posé sur une autre instance était ainsi réécrit par la
    valeur périmée que portait celle du cache, et l'écran répondait
    « Accès refusé » alors que la base disait « admin ».
    """
    utilisateur = User.objects.create_user(
        username='patronne', email='patronne@cp.test',
        password='tourbillon-de-sable-91')
    utilisateur.profile.role = 'admin'
    utilisateur.profile.companies.add(entreprise)
    utilisateur.profile.current_company = entreprise
    utilisateur.profile.save()
    client.force_login(utilisateur)
    return client


def _donnees(**extra):
    base = {
        'username': 'nouvelle',
        'first_name': 'Nadia',
        'last_name': 'Arrivante',
        'email': 'nadia@cp.test',
        'role': 'user',
        'without_employee_record': 'on',
    }
    base.update(extra)
    return base


def _code_du_courriel(message):
    """Extrait le code provisoire du corps du message.

    Lu dans le courriel ÉMIS, et non renvoyé par la fonction qui l'a
    engendré : c'est la seule façon de prouver que le code qui part est
    bien celui que le compte reconnaît. Les tester séparément laisserait
    passer une erreur de transmission entre les deux.
    """
    trouve = re.search(r'Code provisoire\s*:\s*(\S+)', message.body)
    assert trouve, 'aucun code dans le corps du message :\n%s' % message.body
    return trouve.group(1)


# ═══════════════════════════════════════════════════════════════════════════
#  1. Le formulaire ne demande plus de mot de passe
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_le_formulaire_ne_porte_plus_de_champ_mot_de_passe(entreprise):
    from apps.accounts.forms import UserCreateForm

    champs = set(UserCreateForm(company=entreprise).fields)
    assert 'password1' not in champs
    assert 'password2' not in champs


@pytest.mark.django_db
def test_l_ecran_n_affiche_aucun_champ_de_mot_de_passe(patron):
    """Mesuré sur le HTML rendu, et non sur la liste des champs.

    Le gabarit pourrait très bien ajouter son propre champ hors du
    formulaire — c'est exactement le genre d'écart qu'une vérification
    côté Python ne voit pas.
    """
    corps = patron.get(reverse('accounts:user_create')).content.decode()
    assert 'type="password"' not in corps
    assert 'Aucun mot de passe à saisir' in corps


@pytest.mark.django_db
def test_l_adresse_devient_obligatoire(entreprise):
    """Elle est le seul chemin du code : sans elle, le compte est muet.

    `User.email` est `blank=True` dans Django, donc le formulaire
    l'acceptait vide — et un compte sans adresse est désormais un compte
    auquel personne ne peut se connecter. Mieux vaut le refuser à la
    saisie que le découvrir au premier appel.
    """
    from apps.accounts.forms import UserCreateForm

    form = UserCreateForm(_donnees(email=''), company=entreprise)
    assert not form.is_valid()
    assert 'email' in form.errors


@pytest.mark.django_db
def test_une_adresse_deja_utilisee_est_refusee(entreprise):
    """Deux comptes sur une adresse : à qui sert le code reçu ?

    `User.email` n'est pas unique dans Django, et c'était sans conséquence
    tant que l'adresse ne servait à rien.
    """
    from apps.accounts.forms import UserCreateForm

    User.objects.create_user(username='deja', email='nadia@cp.test',
                             password='x')
    form = UserCreateForm(_donnees(), company=entreprise)
    assert not form.is_valid()
    assert 'email' in form.errors


@pytest.mark.django_db
def test_la_casse_de_l_adresse_ne_contourne_pas_le_refus(entreprise):
    """« Nadia@ » et « nadia@ » sont la même boîte."""
    from apps.accounts.forms import UserCreateForm

    User.objects.create_user(username='deja', email='nadia@cp.test',
                             password='x')
    form = UserCreateForm(_donnees(email='Nadia@CP.test'), company=entreprise)
    assert not form.is_valid()
    assert 'email' in form.errors


@pytest.mark.django_db
def test_le_formulaire_seul_laisse_un_mot_de_passe_inutilisable(entreprise):
    """L'état sûr entre les deux écritures.

    `form.save()` n'a pas encore posé le code. Si le compte sortait de là
    avec un mot de passe vide, une erreur survenant juste après laisserait
    un compte OUVERT ; avec un mot de passe inutilisable, il reste fermé.
    """
    from apps.accounts.forms import UserCreateForm

    form = UserCreateForm(_donnees(), company=entreprise)
    assert form.is_valid(), form.errors
    utilisateur = form.save()
    assert not utilisateur.has_usable_password()


# ═══════════════════════════════════════════════════════════════════════════
#  2. Le code part par courriel, et il ouvre le compte
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_la_creation_envoie_un_courriel_a_l_adresse_saisie(patron):
    mail.outbox = []
    patron.post(reverse('accounts:user_create'), _donnees())

    assert len(mail.outbox) == 1, mail.outbox
    assert mail.outbox[0].to == ['nadia@cp.test']


@pytest.mark.django_db
def test_le_code_du_courriel_ouvre_vraiment_le_compte(patron, client):
    """LE TEST QUI COMPTE : le code émis et le code reconnu sont le même.

    Deux écritures séparées — `set_password` d'un côté, le corps du
    message de l'autre — peuvent parfaitement porter deux valeurs
    différentes. On se connecte donc pour de vrai avec ce qui est arrivé
    dans la boîte.
    """
    mail.outbox = []
    patron.post(reverse('accounts:user_create'), _donnees())
    code = _code_du_courriel(mail.outbox[0])

    frais = client.__class__()
    assert frais.login(username='nouvelle', password=code) is True


@pytest.mark.django_db
def test_le_code_n_est_montre_a_personne_d_autre(patron):
    """Le point central du dispositif.

    Si l'écran l'affichait « au cas où », il serait recopié, transmis par
    message, et le courriel ne servirait plus à rien. On vérifie donc que
    le code n'apparaît NI dans la page de retour, NI dans les messages.
    """
    mail.outbox = []
    reponse = patron.post(reverse('accounts:user_create'), _donnees(),
                          follow=True)
    code = _code_du_courriel(mail.outbox[0])

    assert code not in reponse.content.decode()


@pytest.mark.django_db
def test_le_compte_cree_porte_l_obligation_et_sa_date(patron):
    mail.outbox = []
    patron.post(reverse('accounts:user_create'), _donnees())

    profil = User.objects.get(username='nouvelle').profile
    assert profil.doit_changer_de_mot_de_passe is True
    assert profil.code_provisoire_envoye_le is not None


@pytest.mark.django_db
def test_le_courriel_porte_l_identifiant_et_un_lien_absolu(patron):
    """Un courriel se lit ailleurs que dans l'ERP.

    Un lien relatif n'y mène nulle part, et sans l'identifiant le
    destinataire ne sait pas quoi taper dans le premier champ — il
    essaiera son adresse, qui n'est pas son nom d'utilisateur.
    """
    mail.outbox = []
    patron.post(reverse('accounts:user_create'), _donnees())
    corps = mail.outbox[0].body

    assert 'nouvelle' in corps
    assert 'http' in corps


# ═══════════════════════════════════════════════════════════════════════════
#  3. Le changement est obligatoire à la première connexion
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def compte_neuf(patron, client, entreprise):
    """Un compte créé par l'écran, connecté avec son code provisoire."""
    mail.outbox = []
    patron.post(reverse('accounts:user_create'), _donnees())
    code = _code_du_courriel(mail.outbox[0])

    utilisateur = User.objects.get(username='nouvelle')
    utilisateur.profile.companies.add(entreprise)
    utilisateur.profile.current_company = entreprise
    utilisateur.profile.save()

    frais = client.__class__()
    assert frais.login(username='nouvelle', password=code) is True
    return {'client': frais, 'code': code, 'user': utilisateur}


@pytest.mark.django_db
def test_toute_page_renvoie_vers_le_changement(compte_neuf):
    """Mesuré sur une page ordinaire, et pas seulement après la connexion.

    Rediriger depuis `login_view` ne tiendrait que le temps d'une
    requête : l'utilisateur taperait ensuite n'importe quelle adresse et
    travaillerait toute la journée avec le code reçu par courriel.
    """
    reponse = compte_neuf['client'].get(reverse('accounts:profile'))
    assert reponse.status_code == 302
    assert reverse('accounts:changer_mot_de_passe') in reponse['Location']


@pytest.mark.django_db
def test_l_ecran_de_changement_lui_meme_n_est_pas_redirige(compte_neuf):
    """Sans cette exemption, la page se redirigerait vers elle-même.

    L'utilisateur verrait une boucle de redirections, et le navigateur
    finirait par refuser d'aller plus loin.
    """
    reponse = compte_neuf['client'].get(
        reverse('accounts:changer_mot_de_passe'))
    assert reponse.status_code == 200
    assert 'Première connexion' in reponse.content.decode()


@pytest.mark.django_db
def test_la_deconnexion_reste_atteignable(compte_neuf):
    """La seule sortie honnête pour qui ne veut pas changer maintenant.

    Sans cette exemption, il serait enfermé dans la page sans pouvoir
    quitter la session — et sur un poste partagé, c'est un vrai problème.
    """
    reponse = compte_neuf['client'].get(reverse('accounts:logout'))
    assert reponse.status_code in (200, 302)
    if reponse.status_code == 302:
        assert reverse('accounts:changer_mot_de_passe') \
            not in reponse['Location']


@pytest.mark.django_db
def test_une_api_recoit_un_403_et_non_une_redirection(compte_neuf):
    """Un client d'API lirait un 302 vers du HTML comme une réponse valide.

    Et les API ne sont PAS exemptées, à la différence du middleware 2FA :
    le compte porte un mot de passe que l'administrateur a vu passer dans
    les journaux d'un serveur de courriel. Lui ouvrir l'API reviendrait à
    dire que l'obligation ne vaut que pour les écrans.
    """
    reponse = compte_neuf['client'].get('/api/v1/une-route-quelconque/')
    assert reponse.status_code == 403
    assert reponse['Content-Type'].startswith('application/json')
    assert reponse.json()['code'] == 'mot_de_passe_provisoire'


@pytest.mark.django_db
def test_un_compte_ordinaire_n_est_pas_redirige(patron):
    """La protection ne doit pas déborder sur les comptes existants.

    Le drapeau vaut faux par défaut, délibérément : à vrai, la migration
    aurait imposé un changement à TOUS les comptes, y compris celui de
    l'exploitant, sans que personne comprenne pourquoi.
    """
    reponse = patron.get(reverse('accounts:profile'))
    assert reponse.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
#  4. Le changement, et ce qui le ferait rater
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_changer_leve_l_obligation_et_garde_la_session(compte_neuf):
    """Changer son mot de passe déconnecte, sauf si l'empreinte est refaite.

    La session porte une empreinte du mot de passe : dès qu'il change,
    Django ferme la session à la requête SUIVANTE. L'utilisateur serait
    renvoyé à l'écran de connexion juste après avoir réussi — et lirait
    cela comme un échec.
    """
    reponse = compte_neuf['client'].post(
        reverse('accounts:changer_mot_de_passe'), {
            'old_password': compte_neuf['code'],
            'new_password1': 'bourrasque-de-platre-74',
            'new_password2': 'bourrasque-de-platre-74',
        })
    assert reponse.status_code == 302

    compte_neuf['user'].profile.refresh_from_db()
    assert compte_neuf['user'].profile.doit_changer_de_mot_de_passe is False

    # La requête SUIVANTE est celle qui révèle une session perdue.
    suite = compte_neuf['client'].get(reverse('accounts:profile'))
    assert suite.status_code == 200, (
        'la session a été fermée : update_session_auth_hash manque')


@pytest.mark.django_db
def test_reposer_le_code_recu_est_refuse(compte_neuf):
    """LE TROU QUE CECI FERME.

    `PasswordChangeForm` ne compare pas le nouveau mot de passe à
    l'ancien. Ressaisir le code reçu par courriel aurait donc satisfait le
    formulaire, levé l'obligation, et laissé en place un mot de passe
    engendré par la machine qui dort dans une boîte de réception —
    l'écran affichant « mot de passe modifié » sans que rien ne change.
    """
    reponse = compte_neuf['client'].post(
        reverse('accounts:changer_mot_de_passe'), {
            'old_password': compte_neuf['code'],
            'new_password1': compte_neuf['code'],
            'new_password2': compte_neuf['code'],
        })

    assert reponse.status_code == 200, 'le changement a été accepté'
    compte_neuf['user'].profile.refresh_from_db()
    assert compte_neuf['user'].profile.doit_changer_de_mot_de_passe is True


@pytest.mark.django_db
def test_un_mauvais_code_ne_leve_pas_l_obligation(compte_neuf):
    """L'ancien mot de passe est exigé, et c'est lui qui prouve la réception.

    Une session obtenue autrement — un poste laissé déverrouillé — ne doit
    pas suffire à s'approprier le compte.
    """
    reponse = compte_neuf['client'].post(
        reverse('accounts:changer_mot_de_passe'), {
            'old_password': 'ce-n-est-pas-le-code',
            'new_password1': 'bourrasque-de-platre-74',
            'new_password2': 'bourrasque-de-platre-74',
        })

    assert reponse.status_code == 200
    compte_neuf['user'].profile.refresh_from_db()
    assert compte_neuf['user'].profile.doit_changer_de_mot_de_passe is True


@pytest.mark.django_db
def test_ouvrir_la_page_sans_rien_envoyer_ne_leve_rien(compte_neuf):
    """Lever l'obligation à l'affichage suffirait à s'en débarrasser.

    Il suffirait d'ouvrir la page et de la quitter.
    """
    compte_neuf['client'].get(reverse('accounts:changer_mot_de_passe'))
    compte_neuf['user'].profile.refresh_from_db()
    assert compte_neuf['user'].profile.doit_changer_de_mot_de_passe is True


@pytest.mark.django_db
def test_apres_le_changement_les_pages_s_ouvrent(compte_neuf):
    compte_neuf['client'].post(
        reverse('accounts:changer_mot_de_passe'), {
            'old_password': compte_neuf['code'],
            'new_password1': 'bourrasque-de-platre-74',
            'new_password2': 'bourrasque-de-platre-74',
        })
    reponse = compte_neuf['client'].get(reverse('accounts:profile'))
    assert reponse.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
#  5. Renvoyer un code
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_renvoyer_un_code_envoie_un_nouveau_courriel(patron):
    patron.post(reverse('accounts:user_create'), _donnees())
    nouvelle = User.objects.get(username='nouvelle')

    mail.outbox = []
    patron.post(reverse('accounts:user_renvoyer_le_code',
                        args=[nouvelle.pk]))

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ['nadia@cp.test']


@pytest.mark.django_db
def test_le_code_precedent_cesse_de_valoir(patron, client):
    """Deux codes valides à la fois doubleraient la surface pour rien.

    Et un ancien courriel qui continuerait d'ouvrir le compte est
    exactement ce qu'on veut éviter quand on renvoie un code parce que le
    premier a fuité.
    """
    mail.outbox = []
    patron.post(reverse('accounts:user_create'), _donnees())
    premier = _code_du_courriel(mail.outbox[0])

    nouvelle = User.objects.get(username='nouvelle')
    mail.outbox = []
    patron.post(reverse('accounts:user_renvoyer_le_code',
                        args=[nouvelle.pk]))
    second = _code_du_courriel(mail.outbox[0])

    assert premier != second
    frais = client.__class__()
    assert frais.login(username='nouvelle', password=premier) is False
    assert frais.login(username='nouvelle', password=second) is True


@pytest.mark.django_db
def test_le_renvoi_refuse_en_GET(patron):
    """Un GET qui remplace un mot de passe partirait au survol d'un lien."""
    patron.post(reverse('accounts:user_create'), _donnees())
    nouvelle = User.objects.get(username='nouvelle')

    reponse = patron.get(reverse('accounts:user_renvoyer_le_code',
                                 args=[nouvelle.pk]))
    assert reponse.status_code == 405


@pytest.mark.django_db
def test_le_renvoi_sur_un_compte_sans_adresse_est_refuse(patron, entreprise):
    """Sinon on annoncerait un envoi qui ne va nulle part — et le compte
    serait refermé au passage, puisque le code précédent cesse de valoir."""
    muet = User.objects.create_user(username='muet', email='',
                                    password='ancien-mot-de-passe-12')
    muet.profile.companies.add(entreprise)
    muet.profile.save()

    mail.outbox = []
    patron.post(reverse('accounts:user_renvoyer_le_code', args=[muet.pk]))

    assert mail.outbox == []
    muet.refresh_from_db()
    assert muet.check_password('ancien-mot-de-passe-12'), (
        'le mot de passe a été remplacé alors qu’aucun code ne pouvait '
        'partir : le compte est devenu inaccessible pour rien')


@pytest.mark.django_db
def test_la_fiche_signale_l_attente_et_porte_le_bouton(patron):
    patron.post(reverse('accounts:user_create'), _donnees())
    nouvelle = User.objects.get(username='nouvelle')

    corps = patron.get(reverse('accounts:user_detail',
                               args=[nouvelle.pk])).content.decode()
    assert 'Attend sa première connexion' in corps
    assert reverse('accounts:user_renvoyer_le_code',
                   args=[nouvelle.pk]) in corps


# ═══════════════════════════════════════════════════════════════════════════
#  6. Quand le courriel ne part pas
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_un_envoi_qui_echoue_laisse_le_compte_ferme(patron, monkeypatch):
    """L'ORDRE DES DEUX ÉCRITURES, et pourquoi il est celui-ci.

    Le code est posé AVANT d'être envoyé. Si l'envoi échoue, le compte
    porte un code que personne ne connaît — donc inutilisable, ce qui est
    l'état sûr. Dans l'autre ordre, un envoi réussi suivi d'une écriture
    échouée laisserait un code valide dans une boîte et un compte qui ne
    le reconnaît pas : le pire des deux, car l'administrateur aurait vu
    « envoyé » et n'aurait aucune raison de recommencer.
    """
    from apps.accounts.services import code_provisoire

    def refuse(*args, **kwargs):
        raise OSError('serveur SMTP injoignable')

    monkeypatch.setattr(code_provisoire, 'send_mail', refuse)

    reponse = patron.post(reverse('accounts:user_create'), _donnees(),
                          follow=True)

    nouvelle = User.objects.get(username='nouvelle')
    assert nouvelle.profile.doit_changer_de_mot_de_passe is True
    assert 'n’a PAS pu' in reponse.content.decode()


@pytest.mark.django_db
def test_un_backend_muet_n_est_pas_lu_comme_un_succes(patron, monkeypatch):
    """`fail_silently` posé plus bas dans la pile rendrait 0 sans lever.

    Quatre appels de ce dépôt passent `fail_silently=True`, et « les mails
    ne fonctionnent pas » sans le moindre message vient de là. Zéro
    destinataire accepté n'est pas un envoi.
    """
    from apps.accounts.services import code_provisoire

    monkeypatch.setattr(code_provisoire, 'send_mail',
                        lambda *a, **k: 0)

    utilisateur = User.objects.create_user(
        username='silence', email='silence@cp.test', password='x')
    utilisateur.profile.save()

    envoye, motif = code_provisoire.creer_et_envoyer(utilisateur)
    assert envoye is False
    assert motif
