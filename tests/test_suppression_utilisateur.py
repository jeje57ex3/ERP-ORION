"""Suppression d'un compte utilisateur depuis l'ERP.

Supprimer un utilisateur n'est pas supprimer une ligne. Mesure faite sur ce
projet : **164 relations** pointent vers `User`, dont **29 en CASCADE** —
parmi elles les heures pointées sur les chantiers (`btp.BTPTimesheet`), les
comptes de fidélité et les abonnements des clientes Lunea, les accès au
portail client. Les 135 autres sont en SET_NULL : un devis garde sa ligne et
perd seulement le nom de son auteur.

Ce fichier vérifie trois choses.

**Les garde-fous.** On ne supprime pas son propre compte (la session
disparaît avec), ni le dernier super administrateur actif (plus personne ne
peut rouvrir un accès), ni un compte d'une autre entreprise en forgeant un
numéro dans l'URL.

**L'inventaire est exact.** La page de confirmation n'affiche pas une mise
en garde générique mais ce que le collecteur de Django s'apprête réellement
à effacer. Un inventaire approximatif serait pire que pas d'inventaire :
il inspirerait une confiance imméritée.

**Le cloisonnement de `user_detail`.** Cette vue faisait un
`get_object_or_404(User, pk=pk)` sans aucun contrôle : n'importe quel compte
connecté lisait la fiche d'un utilisateur d'une autre entreprise. Y poser un
bouton « supprimer » aurait transformé une fuite de lecture en suppression à
distance.
"""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from apps.accounts.models import UserProfile
from apps.accounts.services.user_deletion_service import (
    MODELES_SENSIBLES,
    desactiver_utilisateur,
    inventaire_cascade,
    peut_supprimer,
    supprimer_utilisateur,
)

pytestmark = pytest.mark.django_db


# ── Terrain ─────────────────────────────────────────────────────────────────

def creer_compte(nom, role='user', company=None, superuser=False,
                 actif=True):
    utilisateur = User.objects.create_user(
        username=nom, password='x', email=f'{nom}@exemple.fr',
        is_superuser=superuser, is_staff=superuser, is_active=actif)
    profil, _ = UserProfile.objects.get_or_create(user=utilisateur)
    profil.role = role
    profil.save()
    if company is not None:
        profil.companies.add(company)
    # Relecture OBLIGATOIRE, et la raison merite d'etre dite : le signal qui
    # cree le UserProfile a la naissance du User met l'objet en cache dans
    # utilisateur._state.fields_cache['profile'] -- avec role='user'. Le
    # profil modifie ensuite est un AUTRE objet Python ; sans cette
    # relecture, utilisateur.profile.role rend encore 'user' et tous les
    # tests d'autorisation echouent sur un terrain fausse, pas sur un
    # defaut du code. Mesure faite : 24 echecs venaient de la.
    return User.objects.get(pk=utilisateur.pk)


def creer_chantier(company):
    """Un chantier exige un client : BTPProject.customer est obligatoire."""
    from apps.crm.models import Customer
    from apps.btp.models import BTPProject
    client = Customer.objects.create(company=company, name='Client A')
    return BTPProject.objects.create(
        company=company, name='Chantier A', customer=client)


@pytest.fixture
def entreprise(db):
    from apps.core.models import Company
    return Company.objects.create(name='Dupont SA', slug='dupont-sa')


@pytest.fixture
def autre_entreprise(db):
    from apps.core.models import Company
    return Company.objects.create(name='Martin SA', slug='martin-sa')


@pytest.fixture
def admin(entreprise):
    return creer_compte('patron', role='admin', company=entreprise)


@pytest.fixture
def salarie(entreprise):
    return creer_compte('ouvrier', role='user', company=entreprise)


# ── 1. On ne se supprime pas soi-même ───────────────────────────────────────

def test_impossible_de_supprimer_son_propre_compte(admin, entreprise):
    """La session disparaît avec le compte.

    Et si c'était le dernier administrateur, plus personne ne peut entrer :
    l'erreur ne se répare plus depuis l'interface.
    """
    autorise, raison = peut_supprimer(admin, admin, entreprise)
    assert autorise is False
    assert 'propre compte' in raison


def test_le_refus_resiste_a_un_post_direct(client, admin, entreprise):
    """Un contrôle fait seulement à l'affichage se contourne.

    Rejouer la requête POST sur sa propre fiche doit échouer aussi — c'est
    pourquoi peut_supprimer est appelé une seconde fois au moment d'agir.
    """
    client.force_login(admin)
    reponse = client.post(
        reverse('accounts:user_delete', args=[admin.pk]),
        {'confirmation': admin.username}, follow=True)
    assert User.objects.filter(pk=admin.pk).exists()
    assert reponse.status_code == 200


# ── 2. Le dernier super administrateur ──────────────────────────────────────

def test_le_dernier_super_admin_actif_est_protege(entreprise):
    """Le supprimer laisserait l'ERP sans compte capable d'en recréer un.

    Le rattrapage passerait par la ligne de commande du serveur — hors de
    portée de l'utilisateur, et souvent hors de portée tout court.

    CE GARDE-FOU EST INATTEIGNABLE DEPUIS L'INTERFACE, et il faut le dire
    plutôt que de l'illustrer par un scénario truqué. Un auteur qui est
    super administrateur actif reste toujours un survivant après exclusion
    de la cible ; un auteur qui ne l'est pas est déjà arrêté par le
    contrôle précédent ; et se supprimer soi-même est refusé d'entrée. Le
    contrôle « pas son propre compte » couvre donc tous les cas de
    l'interface.

    Il garde sa valeur pour un appel DIRECT au service — commande
    d'administration, shell Django, code futur — qui n'a pas de session et
    peut donc présenter n'importe quel auteur. C'est ce cas qui est joué
    ici : l'auteur est un super administrateur désactivé, comme un script
    agissant au nom d'un compte de service hors d'usage.
    """
    seul_actif = creer_compte('root', role='superadmin', company=entreprise,
                              superuser=True)
    auteur_script = creer_compte('compte-service', role='superadmin',
                                 company=entreprise, superuser=True,
                                 actif=False)
    autorise, raison = peut_supprimer(auteur_script, seul_actif, entreprise)
    assert autorise is False
    assert 'dernier super administrateur' in raison


def test_deux_super_admins_actifs_peuvent_se_supprimer_l_un_l_autre(entreprise):
    """Le pendant du test précédent, et la raison de son existence.

    Refuser ici serait un garde-fou trop zélé : il interdirait de retirer
    un super administrateur dès qu'il en existe deux, c'est-à-dire
    toujours.
    """
    patron = creer_compte('root', role='superadmin', company=entreprise,
                          superuser=True)
    autre = creer_compte('root2', role='superadmin', company=entreprise,
                         superuser=True)
    autorise, raison = peut_supprimer(autre, patron, entreprise)
    assert autorise is True, raison


def test_un_super_admin_peut_etre_supprime_s_il_en_reste_un_autre(entreprise):
    patron = creer_compte('root', role='superadmin', company=entreprise,
                          superuser=True)
    deux = creer_compte('root2', role='superadmin', company=entreprise,
                        superuser=True)
    trois = creer_compte('root3', role='superadmin', company=entreprise,
                         superuser=True)
    autorise, raison = peut_supprimer(patron, deux, entreprise)
    assert autorise is True, raison
    assert trois.pk  # il en reste bien deux hors la cible


def test_un_super_admin_desactive_ne_compte_pas_comme_recours(entreprise):
    """Un compte désactivé ne peut plus se connecter.

    Le compter parmi « il en reste un » autoriserait la suppression du seul
    accès réellement utilisable, et le recours annoncé n'en serait pas un.
    Le filtre porte donc sur is_active, et non sur is_superuser seul.
    """
    seul_actif = creer_compte('root', role='superadmin', company=entreprise,
                              superuser=True)
    # Trois super administrateurs existent, mais deux sont hors d'usage.
    creer_compte('ancien', role='superadmin', company=entreprise,
                 superuser=True, actif=False)
    auteur_script = creer_compte('compte-service', role='superadmin',
                                 company=entreprise, superuser=True,
                                 actif=False)

    autorise, raison = peut_supprimer(auteur_script, seul_actif, entreprise)
    assert autorise is False
    assert 'dernier super administrateur' in raison


def test_un_admin_simple_ne_supprime_pas_un_super_admin(admin, entreprise):
    patron = creer_compte('root', role='superadmin', company=entreprise,
                          superuser=True)
    creer_compte('root2', role='superadmin', company=entreprise,
                 superuser=True)
    autorise, raison = peut_supprimer(admin, patron, entreprise)
    assert autorise is False
    assert 'super' in raison.lower()


# ── 3. Qui a le droit ───────────────────────────────────────────────────────

def test_un_responsable_ne_peut_pas_supprimer(entreprise, salarie):
    """Un responsable consulte la liste des utilisateurs, il ne l'efface pas.

    Distinction volontaire : user_list autorise admin ET manager, la
    suppression seulement admin.
    """
    chef = creer_compte('chef', role='manager', company=entreprise)
    autorise, raison = peut_supprimer(chef, salarie, entreprise)
    assert autorise is False
    assert 'administrateur' in raison


def test_un_utilisateur_ordinaire_ne_peut_pas_supprimer(entreprise, salarie):
    quelconque = creer_compte('jean', role='user', company=entreprise)
    assert peut_supprimer(quelconque, salarie, entreprise)[0] is False


def test_un_compte_sans_profil_ne_fait_pas_planter(entreprise, salarie):
    """Un User sans UserProfile existe : createsuperuser, profil effacé.

    Lire .profile.role lèverait RelatedObjectDoesNotExist et casserait la
    page au lieu de refuser proprement.
    """
    nu = User.objects.create_user(username='nu', password='x')
    UserProfile.objects.filter(user=nu).delete()
    nu.refresh_from_db()
    autorise, raison = peut_supprimer(nu, salarie, entreprise)
    assert autorise is False
    assert raison


def test_un_admin_supprime_un_salarie_de_son_entreprise(admin, salarie,
                                                        entreprise):
    autorise, raison = peut_supprimer(admin, salarie, entreprise)
    assert autorise is True, raison


# ── 4. Cloisonnement par entreprise ─────────────────────────────────────────

def test_un_admin_ne_supprime_pas_un_compte_d_une_autre_entreprise(
        admin, entreprise, autre_entreprise):
    """Le cas de l'identifiant forgé dans l'URL.

    Même famille de défaut que les listes déroulantes non bornées : ce qui
    est caché à l'affichage doit aussi être refusé à l'exécution.
    """
    etranger = creer_compte('voisin', role='user', company=autre_entreprise)
    autorise, raison = peut_supprimer(admin, etranger, entreprise)
    assert autorise is False
    assert 'entreprise' in raison


def test_un_super_admin_traverse_les_entreprises(autre_entreprise, entreprise):
    patron = creer_compte('root', role='superadmin', company=entreprise,
                          superuser=True)
    etranger = creer_compte('voisin', role='user', company=autre_entreprise)
    assert peut_supprimer(patron, etranger, entreprise)[0] is True


def test_sans_entreprise_active_un_admin_ne_supprime_rien(admin, salarie):
    autorise, raison = peut_supprimer(admin, salarie, None)
    assert autorise is False
    assert 'entreprise' in raison


# ── 5. L'inventaire de la cascade ───────────────────────────────────────────

def test_l_inventaire_ne_compte_pas_le_compte_lui_meme(salarie):
    """Le compte n'est pas une perte collatérale, c'est l'objet de l'acte.

    Le compter parmi les objets liés ferait annoncer « 1 objet lié sera
    supprimé » pour un compte qui n'a rien enregistré.
    """
    inventaire = inventaire_cascade(salarie)
    labels = [ligne['label'] for ligne in inventaire['lignes']]
    assert 'auth.User' not in labels


def test_l_inventaire_voit_le_profil(salarie):
    """UserProfile est en CASCADE : il part avec le compte."""
    inventaire = inventaire_cascade(salarie)
    labels = [ligne['label'] for ligne in inventaire['lignes']]
    assert 'accounts.UserProfile' in labels
    assert inventaire['total'] >= 1


def test_l_inventaire_signale_les_donnees_sensibles(salarie, entreprise):
    """Les heures pointées ne sont pas une préférence d'affichage.

    Sans ce signalement, elles figureraient au milieu d'une liste de
    trente lignes de réglages, et personne ne les y verrait.
    """
    chantier = creer_chantier(entreprise)
    from apps.btp.models import BTPTimesheet
    BTPTimesheet.objects.create(
        company=entreprise, project=chantier, employee=salarie,
        work_date='2026-01-05', hours=8)

    inventaire = inventaire_cascade(salarie)
    sensibles = {ligne['label'] for ligne in inventaire['sensibles']}
    assert 'btp.BTPTimesheet' in sensibles

    ligne = next(l for l in inventaire['lignes']
                 if l['label'] == 'btp.BTPTimesheet')
    assert ligne['total'] == 1
    assert ligne['motif']  # une phrase, pas un nom de table


def test_les_sensibles_sont_en_tete_de_liste(salarie, entreprise):
    """C'est la seule partie de l'inventaire sur laquelle on décide."""
    chantier = creer_chantier(entreprise)
    from apps.btp.models import BTPTimesheet
    for jour in ('2026-01-05', '2026-01-06'):
        BTPTimesheet.objects.create(
            company=entreprise, project=chantier, employee=salarie,
            work_date=jour, hours=8)

    lignes = inventaire_cascade(salarie)['lignes']
    premieres = lignes[:len(inventaire_cascade(salarie)['sensibles'])]
    assert all(ligne['sensible'] for ligne in premieres)


def test_tous_les_modeles_sensibles_existent_vraiment():
    """Une faute de frappe rendrait l'avertissement silencieux.

    `MODELES_SENSIBLES` est consulté par comparaison de chaînes : un label
    mal écrit ne lève aucune erreur, il cesse simplement de correspondre, et
    les heures pointées disparaîtraient sans le bandeau rouge.
    """
    from django.apps import apps as registre
    for label in MODELES_SENSIBLES:
        registre.get_model(label)  # lève LookupError si le modèle n'existe pas


def test_les_modeles_sensibles_sont_bien_en_cascade():
    """Signaler un modèle en SET_NULL serait un mensonge dans l'autre sens.

    L'utilisateur renoncerait à une suppression inoffensive.
    """
    from django.apps import apps as registre
    from django.db.models.deletion import CASCADE
    cascades = {
        rel.related_model._meta.label
        for rel in User._meta.related_objects
        if rel.field.remote_field.on_delete is CASCADE
    }
    for label in MODELES_SENSIBLES:
        registre.get_model(label)
        assert label in cascades, (
            f'{label} est annoncé comme détruit en cascade, mais sa relation '
            f'vers User ne l\'est pas.')


def test_les_traces_conservees_sont_comptees(admin, salarie, entreprise):
    """135 relations sur 164 passent à NULL, et c'est rassurant à savoir.

    Un devis garde sa ligne ; il perd le nom de son auteur. Ne pas le dire
    laisse croire que tout part.
    """
    from apps.core.models import AuditLog
    AuditLog.objects.create(user=salarie, action='login',
                            description='connexion')
    inventaire = inventaire_cascade(salarie)
    assert inventaire['traces_conservees'] >= 1


# ── 6. La suppression elle-même ─────────────────────────────────────────────

def test_la_suppression_journalise_avant_d_effacer(admin, salarie, entreprise):
    """Après la suppression, l'identité n'est plus lisible.

    AuditLog.user est en SET_NULL : il ne retiendrait qu'un NULL. Le nom
    doit donc être recopié en texte dans l'entrée, qui survit à l'objet.
    """
    from apps.core.models import AuditLog
    identifiant = salarie.username
    pk = salarie.pk

    succes, message = supprimer_utilisateur(admin, salarie, entreprise,
                                            ip='10.0.0.1')
    assert succes is True, message
    assert not User.objects.filter(pk=pk).exists()

    entree = AuditLog.objects.filter(
        action='delete', model_name='User', object_id=str(pk)).first()
    assert entree is not None
    assert entree.old_values['username'] == identifiant
    assert entree.user == admin
    assert identifiant in entree.description


def test_la_suppression_recontrole_le_droit(admin, entreprise,
                                            autre_entreprise):
    """supprimer_utilisateur ne fait pas confiance à son appelant.

    La vue vérifie déjà ; si elle oubliait, ou si un script appelait le
    service directement, le cloisonnement doit tenir quand même.
    """
    etranger = creer_compte('voisin', role='user', company=autre_entreprise)
    succes, message = supprimer_utilisateur(admin, etranger, entreprise)
    assert succes is False
    assert User.objects.filter(pk=etranger.pk).exists()
    assert 'entreprise' in message


def test_les_donnees_en_set_null_survivent(admin, salarie, entreprise):
    """Le journal d'audit du compte supprimé reste, orphelin mais lisible."""
    from apps.core.models import AuditLog
    AuditLog.objects.create(user=salarie, action='login', description='trace')
    supprimer_utilisateur(admin, salarie, entreprise)
    trace = AuditLog.objects.filter(description='trace').first()
    assert trace is not None
    assert trace.user is None


# ── 7. La désactivation, qu'il faut préférer ────────────────────────────────

def test_la_desactivation_ne_detruit_rien(admin, salarie, entreprise):
    from apps.core.models import AuditLog
    AuditLog.objects.create(user=salarie, action='login', description='trace')
    succes, message = desactiver_utilisateur(admin, salarie, entreprise)
    assert succes is True, message

    salarie.refresh_from_db()
    assert salarie.is_active is False
    assert AuditLog.objects.filter(description='trace').exists()
    assert 'aucune donnée' in message


def test_la_desactivation_obeit_aux_memes_regles(admin, entreprise):
    """Se désactiver soi-même revient à se verrouiller dehors."""
    autorise, _ = peut_supprimer(admin, admin, entreprise)
    assert autorise is False
    succes, _ = desactiver_utilisateur(admin, admin, entreprise)
    assert succes is False
    admin.refresh_from_db()
    assert admin.is_active is True


def test_desactiver_deux_fois_est_sans_effet(admin, entreprise):
    cible = creer_compte('parti', role='user', company=entreprise,
                         actif=False)
    succes, message = desactiver_utilisateur(admin, cible, entreprise)
    assert succes is True
    assert 'déjà' in message


# ── 8. Les vues ─────────────────────────────────────────────────────────────

def test_la_page_de_confirmation_affiche_l_inventaire(client, admin, salarie):
    client.force_login(admin)
    reponse = client.get(reverse('accounts:user_delete', args=[salarie.pk]))
    assert reponse.status_code == 200
    corps = reponse.content.decode()
    assert salarie.username in corps
    # L'inventaire, pas une mise en garde générique.
    assert 'accounts.UserProfile' in corps


def test_la_confirmation_exige_l_identifiant_recopie(client, admin, salarie):
    """« Êtes-vous sûr ? » se clique par réflexe ; recopier demande de lire."""
    client.force_login(admin)
    reponse = client.post(
        reverse('accounts:user_delete', args=[salarie.pk]),
        {'confirmation': 'nimportequoi'})
    assert reponse.status_code == 200
    assert User.objects.filter(pk=salarie.pk).exists()
    assert 'Saisie incorrecte' in reponse.content.decode()


def test_une_confirmation_vide_ne_supprime_pas(client, admin, salarie):
    client.force_login(admin)
    client.post(reverse('accounts:user_delete', args=[salarie.pk]),
                {'confirmation': ''})
    assert User.objects.filter(pk=salarie.pk).exists()


def test_l_identifiant_exact_supprime(client, admin, salarie):
    client.force_login(admin)
    pk = salarie.pk
    reponse = client.post(
        reverse('accounts:user_delete', args=[pk]),
        {'confirmation': salarie.username}, follow=True)
    assert reponse.status_code == 200
    assert not User.objects.filter(pk=pk).exists()


def test_la_vue_refuse_un_compte_d_une_autre_entreprise(
        client, admin, autre_entreprise):
    """404, et non 403 : l'existence du compte ne doit pas se déduire."""
    etranger = creer_compte('voisin', role='user', company=autre_entreprise)
    client.force_login(admin)
    reponse = client.get(reverse('accounts:user_delete', args=[etranger.pk]))
    assert reponse.status_code == 404
    assert User.objects.filter(pk=etranger.pk).exists()


def test_user_detail_est_cloisonne(client, admin, autre_entreprise):
    """Le défaut que ce travail a mis au jour.

    user_detail faisait get_object_or_404(User, pk=pk) sans contrôle :
    n'importe quel compte connecté lisait la fiche d'un utilisateur d'une
    autre entreprise en changeant le numéro dans l'URL.
    """
    etranger = creer_compte('voisin', role='user', company=autre_entreprise)
    client.force_login(admin)
    reponse = client.get(reverse('accounts:user_detail', args=[etranger.pk]))
    assert reponse.status_code == 404


def test_un_responsable_n_a_pas_le_bouton(client, entreprise, salarie):
    """Un bouton qui mène à un refus apprend à se méfier de l'interface."""
    chef = creer_compte('chef', role='manager', company=entreprise)
    client.force_login(chef)
    reponse = client.get(reverse('accounts:user_detail', args=[salarie.pk]))
    assert reponse.status_code == 200
    assert reponse.context['suppression_possible'] is False
    corps = reponse.content.decode()
    assert reverse('accounts:user_delete', args=[salarie.pk]) not in corps


def test_la_fiche_d_un_admin_porte_le_bouton(client, admin, salarie):
    client.force_login(admin)
    reponse = client.get(reverse('accounts:user_detail', args=[salarie.pk]))
    assert reponse.context['suppression_possible'] is True
    assert reverse('accounts:user_delete',
                   args=[salarie.pk]) in reponse.content.decode()


def test_sa_propre_fiche_explique_le_refus(client, admin):
    """Pas seulement un bouton absent : la raison est écrite.

    Sinon l'utilisateur cherche une permission manquante alors que la
    raison est « c'est votre propre compte ».
    """
    client.force_login(admin)
    reponse = client.get(reverse('accounts:user_detail', args=[admin.pk]))
    assert reponse.context['suppression_possible'] is False
    assert 'propre compte' in reponse.context['suppression_refus']


def test_la_liste_calcule_le_droit_par_ligne(client, admin, salarie):
    client.force_login(admin)
    reponse = client.get(reverse('accounts:user_list'))
    assert reponse.status_code == 200
    par_nom = {compte.username: compte for compte in reponse.context['users']}
    assert par_nom['ouvrier'].suppression_possible is True
    assert par_nom['patron'].suppression_possible is False


def test_la_desactivation_par_la_vue_exige_un_post(client, admin, salarie):
    """Un GET qui modifie l'état se déclenche au survol ou à l'indexation."""
    client.force_login(admin)
    reponse = client.get(
        reverse('accounts:user_deactivate', args=[salarie.pk]))
    assert reponse.status_code == 405
    salarie.refresh_from_db()
    assert salarie.is_active is True


def test_la_desactivation_par_la_vue(client, admin, salarie):
    client.force_login(admin)
    client.post(reverse('accounts:user_deactivate', args=[salarie.pk]))
    salarie.refresh_from_db()
    assert salarie.is_active is False


def test_un_anonyme_ne_peut_rien(client, salarie):
    reponse = client.get(reverse('accounts:user_delete', args=[salarie.pk]))
    assert reponse.status_code in (301, 302)
    assert User.objects.filter(pk=salarie.pk).exists()
