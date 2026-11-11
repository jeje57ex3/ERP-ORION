"""L'envoi des courriels : réglable depuis l'interface, et qui dit pourquoi
il échoue.

CE QUI NE FONCTIONNAIT PAS

1. Les réglages SMTP n'existaient que dans `/opt/orion/backend/.env`,
   modifiables par SSH puis redémarrage de gunicorn. Une fonction
   d'administration qui exige un terminal n'est pas administrable.

2. Quatre appels du dépôt passent `fail_silently=True` — dont l'invitation
   au portail client et la réinitialisation de mot de passe des boutiques.
   Django absorbait l'exception DANS son backend : aucun journal, aucune
   trace, aucun message. « Les mails ne fonctionnent pas » sans la moindre
   indication vient de là.

3. Le contrôle de santé du courriel répondait « ok » dès que le backend ne
   contenait pas « smtp » — donc un backend « console » ou « mémoire », qui
   n'envoie rien, sortait en vert.

4. La clé EMAIL_BACKEND du .env était documentée et RIEN NE LA LISAIT.
"""
import logging

import pytest
from cryptography.fernet import Fernet
from django.core.mail import EmailMessage, send_mail
from django.test import override_settings


# Une vraie clé Fernet, générée une fois pour ce module : le chiffrement du
# mot de passe doit être exercé pour de bon, pas simulé.
CLE = Fernet.generate_key().decode()

# Port fermé sur la boucle locale : le refus de connexion est immédiat, donc
# aucun test n'attend un délai réseau.
HOTE_MORT = '127.0.0.1'
PORT_MORT = 1

LOCMEM = 'django.core.mail.backends.locmem.EmailBackend'
CONSOLE = 'django.core.mail.backends.console.EmailBackend'
SMTP = 'django.core.mail.backends.smtp.EmailBackend'
NOTRE_BACKEND = 'apps.core.mail.BackendMailOrion'


@pytest.fixture
def reglages(db):
    from apps.core.models import ReglagesMail
    return ReglagesMail.get_global()


@pytest.fixture
def reglages_morts(reglages):
    """Des réglages actifs qui pointent vers un port fermé."""
    reglages.actif = True
    reglages.hote = HOTE_MORT
    reglages.port = PORT_MORT
    reglages.chiffrement = 'aucun'
    reglages.delai_secondes = 2
    reglages.save()
    return reglages


def _message(destinataire='client@exemple.fr', expediteur='no-reply@orion.fr'):
    return EmailMessage(
        subject='Essai', body='Corps', from_email=expediteur,
        to=[destinataire])


# ── 1. Le choix du chemin d'envoi ────────────────────────────────────────────

@pytest.mark.django_db
@override_settings(ORION_MAIL_BACKEND_DE_REPLI=LOCMEM)
def test_sans_reglages_actifs_le_repli_prend_la_main(reglages):
    """Comportement d'avant conservé par défaut : rien n'est activé en base,
    donc l'ERP envoie comme il envoyait."""
    from apps.core.mail import BackendMailOrion

    backend = BackendMailOrion()
    assert backend.send_messages([_message()]) == 1


@pytest.mark.django_db
@override_settings(ORION_MAIL_BACKEND_DE_REPLI=LOCMEM)
def test_des_reglages_inactifs_ne_prennent_pas_la_main(reglages_morts):
    """`actif` décoché doit vraiment désactiver, même si l'hôte est rempli.

    Sans quoi remplir le formulaire pour préparer une mise en route
    casserait l'envoi en cours.
    """
    reglages_morts.actif = False
    reglages_morts.save()

    from apps.core.mail import BackendMailOrion

    assert BackendMailOrion().send_messages([_message()]) == 1


@pytest.mark.django_db
def test_des_reglages_actifs_sont_employes(reglages_morts):
    """Et on le prouve par l'échec : le port est fermé, donc l'envoi lève.

    Si les réglages en base étaient ignorés, le repli (SMTP du .env) ou le
    backend de test auraient répondu sans erreur.
    """
    from apps.core.mail import BackendMailOrion

    with pytest.raises(Exception):
        BackendMailOrion(fail_silently=False).send_messages([_message()])


@pytest.mark.django_db
@override_settings(ORION_MAIL_BACKEND_DE_REPLI=LOCMEM)
def test_la_cle_email_backend_du_env_gouverne_le_repli():
    """Elle était documentée dans .env.example et rien ne la lisait."""
    from apps.core.mail import chemin_du_repli
    assert chemin_du_repli() == LOCMEM


# ── 2. Un échec ne disparaît plus en silence ─────────────────────────────────

@pytest.mark.django_db
def test_un_echec_avale_est_quand_meme_journalise(reglages_morts, caplog):
    """LE CŒUR DE LA CORRECTION.

    `fail_silently=True` doit continuer à ne pas casser l'appelant — une
    invitation au portail qui échoue ne doit pas faire échouer l'inscription
    — mais l'échec doit laisser une trace. Avant, Django l'absorbait dans son
    propre backend et rien n'en sortait.
    """
    from apps.core.mail import BackendMailOrion

    caplog.set_level(logging.WARNING, logger='orion')
    envoyes = BackendMailOrion(fail_silently=True).send_messages([_message()])

    assert envoyes == 0, 'un envoi impossible ne doit pas se déclarer réussi'
    assert any('echec' in enregistrement.message.lower()
               or 'echec' in str(enregistrement.msg).lower()
               for enregistrement in caplog.records), caplog.text


@pytest.mark.django_db
def test_un_echec_avale_laisse_son_motif_dans_l_interface(reglages_morts):
    """Le motif doit survivre à la requête : un envoi déclenché par une tâche
    de fond échoue loin de tout écran."""
    from apps.core.mail import BackendMailOrion
    from apps.core.models import ReglagesMail

    BackendMailOrion(fail_silently=True).send_messages([_message()])

    relu = ReglagesMail.objects.get(pk=reglages_morts.pk)
    assert relu.dernier_test_reussi is False
    assert relu.derniere_erreur, 'aucun motif enregistré'
    assert relu.dernier_test_le is not None


@pytest.mark.django_db
def test_sans_fail_silently_l_erreur_remonte(reglages_morts):
    """L'appelant qui veut savoir doit continuer à savoir."""
    from apps.core.mail import BackendMailOrion

    with pytest.raises(Exception):
        BackendMailOrion(fail_silently=False).send_messages([_message()])


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND=NOTRE_BACKEND)
def test_send_mail_avec_fail_silently_ne_casse_pas_l_appelant(reglages_morts):
    """Le chemin réel : `send_mail(..., fail_silently=True)` de bout en bout."""
    from apps.core.models import ReglagesMail

    envoyes = send_mail(
        'Essai', 'Corps', 'no-reply@orion.fr', ['client@exemple.fr'],
        fail_silently=True)

    assert envoyes == 0
    assert ReglagesMail.objects.get(pk=reglages_morts.pk).derniere_erreur


# ── 3. Le diagnostic reste honnête ───────────────────────────────────────────

@pytest.mark.django_db
@override_settings(ORION_MAIL_BACKEND_DE_REPLI=LOCMEM)
def test_open_delegue_vraiment(reglages):
    """apps/system_observability diagnostique en appelant open() puis close().

    L'implémentation par défaut de BaseEmailBackend ne fait RIEN : si on ne
    déléguait pas, ce contrôle serait toujours vert, donc menteur.
    """
    from apps.core.mail import BackendMailOrion

    backend = BackendMailOrion()
    backend.open()
    backend.close()


@pytest.mark.django_db
def test_open_echoue_quand_le_serveur_est_injoignable(reglages_morts):
    """La contrepartie : sans elle, le test précédent pourrait passer grâce à
    un open() qui ne fait rien."""
    from apps.core.mail import BackendMailOrion

    with pytest.raises(Exception):
        BackendMailOrion(fail_silently=False).open()


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND=CONSOLE)
def test_le_controle_de_sante_n_est_plus_vert_sans_envoi(reglages):
    """Il répondait « ok » pour tout backend sans « smtp » dans son nom.

    Un ERP qui écrit ses courriels dans un journal se déclarait donc en
    bonne santé — exactement le cas où l'utilisateur dit « les mails ne
    fonctionnent pas ».
    """
    from apps.core.models import Company
    from apps.system_observability.services import check_email

    entreprise = Company.objects.create(name='Volt SARL', slug='volt-sarl')
    resultat = check_email(entreprise)

    assert resultat.status == 'warning', (
        f'statut {resultat.status} pour un backend qui n’envoie rien')
    assert 'courriels' in resultat.message.lower() \
        or 'envoi' in resultat.message.lower()


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND=NOTRE_BACKEND, EMAIL_HOST='')
def test_le_controle_de_sante_signale_un_smtp_sans_serveur(reglages):
    """SMTP déclaré mais aucun serveur : rien ne part, et il faut le dire."""
    from apps.core.models import Company
    from apps.system_observability.services import check_email

    entreprise = Company.objects.create(name='Volt SARL', slug='volt-sarl')
    with override_settings(ORION_MAIL_BACKEND_DE_REPLI=SMTP):
        resultat = check_email(entreprise)

    assert resultat.status == 'warning'


# ── 4. L'expéditeur par marque n'est pas écrasé ──────────────────────────────

@pytest.mark.django_db
def test_l_expediteur_choisi_par_une_boutique_est_respecte(reglages_morts):
    """apps/ecommerce compose « no-reply@siecle.fr » et « no-reply@lunea.fr ».

    Les remplacer par une adresse unique mettrait toutes les marques sous le
    même expéditeur — une régression invisible dans le code et très visible
    dans la boîte du client.
    """
    from apps.core.mail import BackendMailOrion

    reglages_morts.adresse_expediteur = 'no-reply@orion.fr'
    reglages_morts.save()

    message = _message(expediteur='no-reply@siecle.fr')
    BackendMailOrion(fail_silently=True).send_messages([message])

    assert message.from_email == 'no-reply@siecle.fr'


@pytest.mark.django_db
@override_settings(DEFAULT_FROM_EMAIL='no-reply@orion-erp.local')
def test_l_expediteur_par_defaut_est_remplace(reglages_morts):
    """Le chemin qui aboutit : un message qui n'a rien choisi reçoit bien
    l'adresse configurée, sinon le champ ne servirait à rien."""
    from apps.core.mail import BackendMailOrion

    reglages_morts.adresse_expediteur = 'contact@volt.fr'
    reglages_morts.save()

    message = _message(expediteur='no-reply@orion-erp.local')
    BackendMailOrion(fail_silently=True).send_messages([message])

    assert message.from_email == 'contact@volt.fr'


# ── 5. Le mot de passe ───────────────────────────────────────────────────────

@pytest.mark.django_db
@override_settings(ORION_SECRET_ENCRYPTION_KEY=CLE)
def test_le_mot_de_passe_est_chiffre_en_base(reglages):
    """Il ne doit jamais se lire en clair dans la colonne."""
    reglages.mot_de_passe = 'secret-smtp-de-test'
    reglages.save()

    assert reglages.mot_de_passe_chiffre
    assert 'secret-smtp-de-test' not in reglages.mot_de_passe_chiffre
    assert reglages.mot_de_passe == 'secret-smtp-de-test'
    assert reglages.mot_de_passe_enregistre is True
    assert reglages.mot_de_passe_illisible is False


@pytest.mark.django_db
@override_settings(ORION_SECRET_ENCRYPTION_KEY=CLE)
def test_un_mot_de_passe_illisible_se_distingue_d_un_mot_de_passe_absent(
        reglages):
    """`decrypt_secret` rend '' pour « rien enregistré » ET pour « clé
    changée ». Confondre les deux affiche un champ vide et laisse chercher
    une faute de frappe là où la base a été restaurée sur une autre clé.
    """
    reglages.mot_de_passe = 'secret-smtp-de-test'
    reglages.save()

    with override_settings(ORION_SECRET_ENCRYPTION_KEY=Fernet.generate_key().decode()):
        assert reglages.mot_de_passe == ''
        assert reglages.mot_de_passe_enregistre is True
        assert reglages.mot_de_passe_illisible is True


# ── 6. Le bouton de test ─────────────────────────────────────────────────────

@pytest.mark.django_db
def test_tester_sans_serveur_le_dit_clairement(reglages):
    from apps.core.mail import tester_l_envoi

    reussi, motif = tester_l_envoi('moi@exemple.fr', reglages=reglages)
    assert reussi is False
    assert 'serveur' in motif.lower()


@pytest.mark.django_db
def test_tester_sans_destinataire_le_dit_clairement(reglages_morts):
    from apps.core.mail import tester_l_envoi

    reussi, motif = tester_l_envoi('', reglages=reglages_morts)
    assert reussi is False
    assert 'adresse' in motif.lower()


@pytest.mark.django_db
def test_tester_rend_l_erreur_du_serveur_mot_pour_mot(reglages_morts):
    """« Échec de connexion » sans le texte du serveur est inutilisable.

    C'est toute la différence entre « ça ne marche pas » et
    « authentification refusée » ou « nom de serveur introuvable ».
    """
    from apps.core.mail import tester_l_envoi

    reussi, motif = tester_l_envoi('moi@exemple.fr', reglages=reglages_morts)

    assert reussi is False
    # Le type de l'exception est conservé : c'est lui qui nomme la panne.
    assert ':' in motif
    assert len(motif) > 10


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND=LOCMEM)
def test_le_test_ne_passe_pas_par_le_backend_configure(reglages_morts):
    """Sinon le mode de repli ferait passer le test pour réussi.

    EMAIL_BACKEND vaut ici « mémoire », qui accepte tout. Le test doit
    pourtant échouer, puisque le serveur configuré est injoignable : c'est
    bien les réglages de la page qui sont essayés.
    """
    from apps.core.mail import tester_l_envoi

    reussi, _ = tester_l_envoi('moi@exemple.fr', reglages=reglages_morts)
    assert reussi is False


# ── 7. La page ───────────────────────────────────────────────────────────────

def _super_admin(client, django_user_model):
    """Un Super Admin connecté, avec une entreprise.

    La Company n'est pas décorative : SetupRequiredMiddleware redirige TOUTE
    adresse vers /setup/ tant qu'aucune n'existe.
    """
    from apps.core.models import Company

    Company.objects.get_or_create(
        slug='volt-sarl', defaults={'name': 'Volt SARL'})
    utilisateur = django_user_model.objects.create_superuser(
        username='patron', password='motdepasse-test', email='p@volt.fr')
    client.force_login(utilisateur)
    return utilisateur


@pytest.mark.django_db
def test_la_page_s_affiche_pour_un_super_admin(client, django_user_model):
    _super_admin(client, django_user_model)

    reponse = client.get('/orion-admin/courriels/')
    assert reponse.status_code == 200
    contenu = reponse.content.decode()
    assert 'Serveur SMTP' in contenu
    assert 'Enregistrer et envoyer un test' in contenu


@pytest.mark.django_db
def test_la_page_est_refusee_a_un_salarie(client, django_user_model):
    """Les réglages SMTP portent un mot de passe : la page n'est pas publique."""
    from apps.core.models import Company

    Company.objects.get_or_create(
        slug='volt-sarl', defaults={'name': 'Volt SARL'})
    salarie = django_user_model.objects.create_user(
        username='salarie', password='motdepasse-test', email='s@volt.fr')
    client.force_login(salarie)

    reponse = client.get('/orion-admin/courriels/')
    assert reponse.status_code == 302
    assert '/orion-admin/courriels/' not in reponse['Location']


@pytest.mark.django_db
@override_settings(ORION_SECRET_ENCRYPTION_KEY=CLE)
def test_enregistrer_la_page_ne_detruit_pas_le_mot_de_passe(
        client, django_user_model):
    """LE PIÈGE DE CE FORMULAIRE.

    Le mot de passe n'est jamais réaffiché. Si un champ vide valait
    « efface-le », corriger un numéro de port couperait l'authentification
    SMTP, et l'envoi cesserait sans raison apparente.
    """
    from apps.core.models import ReglagesMail

    _super_admin(client, django_user_model)

    reglages = ReglagesMail.get_global()
    reglages.mot_de_passe = 'secret-smtp-de-test'
    reglages.hote = 'smtp.exemple.fr'
    reglages.save()

    client.post('/orion-admin/courriels/', {
        'action': 'enregistrer',
        'hote': 'smtp.exemple.fr',
        'port': '465',
        'chiffrement': 'ssl',
        'utilisateur': 'envoi@volt.fr',
        'mot_de_passe': '',
        'adresse_expediteur': 'contact@volt.fr',
        'delai_secondes': '15',
    })

    relu = ReglagesMail.get_global()
    assert relu.port == 465
    assert relu.mot_de_passe == 'secret-smtp-de-test', \
        'le mot de passe a été effacé par un enregistrement ordinaire'


@pytest.mark.django_db
@override_settings(ORION_SECRET_ENCRYPTION_KEY=CLE)
def test_la_case_prevue_efface_le_mot_de_passe(client, django_user_model):
    """L'effacement doit rester possible, mais délibéré."""
    from apps.core.models import ReglagesMail

    _super_admin(client, django_user_model)

    reglages = ReglagesMail.get_global()
    reglages.mot_de_passe = 'secret-smtp-de-test'
    reglages.save()

    client.post('/orion-admin/courriels/', {
        'action': 'enregistrer',
        'hote': 'smtp.exemple.fr',
        'port': '587',
        'chiffrement': 'tls',
        'delai_secondes': '10',
        'effacer_mot_de_passe': 'on',
    })

    assert ReglagesMail.get_global().mot_de_passe_enregistre is False


@pytest.mark.django_db
def test_un_port_illisible_conserve_la_valeur_en_place(
        client, django_user_model):
    """Un champ illisible ne doit pas devenir une remise à zéro silencieuse."""
    from apps.core.models import ReglagesMail

    _super_admin(client, django_user_model)

    reglages = ReglagesMail.get_global()
    reglages.port = 465
    reglages.save()

    client.post('/orion-admin/courriels/', {
        'action': 'enregistrer',
        'hote': 'smtp.exemple.fr',
        'port': 'quatre-cent-soixante-cinq',
        'chiffrement': 'ssl',
        'delai_secondes': '10',
    })

    assert ReglagesMail.get_global().port == 465


@pytest.mark.django_db
def test_activer_sans_serveur_avertit_sans_bloquer(client, django_user_model):
    """Un réglage incomplet est une étape de la mise en route, pas une faute.

    On avertit, on enregistre quand même : refuser obligerait à tout remplir
    d'un coup.
    """
    from apps.core.models import ReglagesMail

    _super_admin(client, django_user_model)

    reponse = client.post('/orion-admin/courriels/', {
        'action': 'enregistrer',
        'actif': 'on',
        'hote': '',
        'port': '587',
        'chiffrement': 'tls',
        'delai_secondes': '10',
    }, follow=True)

    assert ReglagesMail.get_global().actif is True
    textes = [str(m) for m in reponse.context['messages']]
    assert any('aucun serveur' in t.lower() for t in textes), textes


@pytest.mark.django_db
def test_le_port_et_le_chiffrement_incoherents_sont_signales(
        client, django_user_model):
    """465 avec STARTTLS expire sans message utile côté serveur."""
    _super_admin(client, django_user_model)

    reponse = client.post('/orion-admin/courriels/', {
        'action': 'enregistrer',
        'hote': 'smtp.exemple.fr',
        'port': '465',
        'chiffrement': 'tls',
        'delai_secondes': '10',
    }, follow=True)

    textes = [str(m) for m in reponse.context['messages']]
    assert any('465' in t for t in textes), textes
