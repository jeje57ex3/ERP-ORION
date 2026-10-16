"""Créer un compte ERP qui ne correspond à aucun salarié.

Tous les comptes ne sont pas des salariés : un prestataire, un
expert-comptable externe, un compte de service ont besoin d'entrer dans l'ERP
sans figurer au registre du personnel. Jusqu'ici c'était impossible —
`UserCreateForm.clean()` refusait tout rôle non administrateur sans fiche.

**La propriété qui compte n'est pas que ce soit permis, mais que ce soit
DÉCLARÉ.** Supprimer purement la validation rendrait indiscernables deux
situations opposées : le compte volontairement externe, et le rattachement
qu'on a oublié de faire. Le second finit par bloquer quelqu'un (congés,
pointages, documents) sans que personne sache pourquoi. D'où une case à
cocher plutôt qu'un contrôle retiré : le refus subsiste quand on n'a rien dit.
"""

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

pytestmark = pytest.mark.django_db


@pytest.fixture
def salarie(company):
    from apps.hr.models import Employee
    return Employee.objects.create(
        company=company, first_name='Marc', last_name='Durand',
        email='marc.durand@example.test',
    )


@pytest.fixture
def admin_connecte(client, company, django_user_model):
    """Un administrateur de l'entreprise : seul habilité à créer un compte."""
    user = django_user_model.objects.create_user(
        username='patron', password='motdepasse-test',
        email='patron@example.test')
    user.profile.role = 'admin'
    user.profile.companies.add(company)
    user.profile.current_company = company
    user.profile.save()
    client.force_login(user)
    return client


def _donnees(**extra):
    base = {
        'username': 'prestataire',
        'first_name': 'Claire',
        'last_name': 'Externe',
        'email': 'claire@cabinet.test',
        'password1': 'MotDePasse-Solide-9',
        'password2': 'MotDePasse-Solide-9',
        'role': 'user',
    }
    base.update(extra)
    return base


# -- Le formulaire -----------------------------------------------------------

def test_la_case_cochee_permet_un_compte_sans_salarie(company):
    """Le cas demandé : un rôle ordinaire, aucun salarié, et c'est accepté."""
    from apps.accounts.forms import UserCreateForm

    form = UserCreateForm(
        _donnees(without_employee_record='on'), company=company)
    assert form.is_valid(), form.errors


def test_sans_la_case_le_refus_subsiste(company):
    """C'est la moitié qui protège : un rattachement oublié reste une erreur,
    sinon la souplesse demandée ferait disparaître le contrôle."""
    from apps.accounts.forms import UserCreateForm

    form = UserCreateForm(_donnees(), company=company)
    assert not form.is_valid()
    assert 'employee' in form.errors


def test_le_message_dit_comment_passer_outre(company):
    """Un refus qui ne nomme pas la sortie se contourne en créant un faux
    salarié — ce qui pollue le registre du personnel."""
    from apps.accounts.forms import UserCreateForm

    form = UserCreateForm(_donnees(), company=company)
    form.is_valid()
    assert 'cochant la case' in ' '.join(form.errors['employee'])


def test_un_salarie_et_la_case_est_une_contradiction(company, salarie):
    """Choisir en silence tromperait : si la case gagnait, l'administrateur
    croirait la liaison faite alors qu'elle serait ignorée."""
    from apps.accounts.forms import UserCreateForm

    form = UserCreateForm(
        _donnees(employee=salarie.pk, without_employee_record='on'),
        company=company)
    assert not form.is_valid()
    assert 'without_employee_record' in form.errors


def test_un_salarie_seul_reste_accepte(company, salarie):
    from apps.accounts.forms import UserCreateForm

    form = UserCreateForm(_donnees(employee=salarie.pk), company=company)
    assert form.is_valid(), form.errors


def test_un_role_administrateur_n_a_toujours_rien_a_cocher(company):
    """Comportement d'avant conservé : l'exemption par rôle existait déjà."""
    from apps.accounts.forms import UserCreateForm

    form = UserCreateForm(_donnees(role='admin'), company=company)
    assert form.is_valid(), form.errors


# -- La création depuis l'écran ----------------------------------------------

def test_l_ecran_cree_le_compte_et_retient_la_declaration(admin_connecte,
                                                          company,
                                                          django_user_model):
    """Retenir la déclaration est ce qui évite que le compte apparaisse
    ensuite comme un oubli à réparer."""
    reponse = admin_connecte.post(
        reverse('accounts:user_create'),
        _donnees(without_employee_record='on'), follow=True)

    assert reponse.status_code == 200
    cree = django_user_model.objects.get(username='prestataire')
    assert cree.profile.without_employee_record is True


def test_aucune_fiche_salarie_n_est_creee_en_douce(admin_connecte, company):
    """Le signal auto_create_employee_for_non_admin fabrique une fiche
    minimale pour les comptes non exemptés : un compte déclaré externe ne doit
    pas en recevoir une, sinon la demande est contournée par le bas."""
    from apps.hr.models import Employee

    admin_connecte.post(reverse('accounts:user_create'),
                        _donnees(without_employee_record='on'))

    assert not Employee.objects.filter(email='claire@cabinet.test').exists()


def test_l_ecran_affiche_la_case(admin_connecte, company):
    reponse = admin_connecte.get(reverse('accounts:user_create'))
    assert reponse.status_code == 200
    assert 'without_employee_record' in reponse.content.decode()


# -- L'exemption des contrôles -----------------------------------------------

def test_le_compte_declare_est_exempte(company, django_user_model):
    """Sans cela, EmployeeLinkRequiredMiddleware — s'il est activé un jour —
    enfermerait ces comptes sur la page « compte non lié »."""
    from apps.accounts.services.user_employee_link_service import (
        is_user_exempt_from_employee_link,
    )

    user = django_user_model.objects.create_user(
        username='compta-externe', password='motdepasse-test')
    assert is_user_exempt_from_employee_link(user) is False

    user.profile.without_employee_record = True
    user.profile.save()
    assert is_user_exempt_from_employee_link(user) is True


def test_la_validation_de_liaison_laisse_passer_le_compte_declare(
        company, django_user_model):
    from apps.accounts.services.user_employee_link_service import (
        validate_user_employee_link,
    )

    user = django_user_model.objects.create_user(
        username='service-sauvegarde', password='motdepasse-test')
    with pytest.raises(ValidationError):
        validate_user_employee_link(user)

    user.profile.without_employee_record = True
    user.profile.save()
    assert validate_user_employee_link(user) is True


def test_le_middleware_ne_detourne_pas_le_compte_declare(client, company,
                                                         django_user_model,
                                                         settings):
    """L'intergiciel n'est pas dans MIDDLEWARE aujourd'hui. Il est ajouté ici
    pour vérifier qu'il ne se retourne pas contre ces comptes si on l'active.

    Le détournement d'un compte NON déclaré est vérifié d'abord : sans lui, un
    intergiciel inactif — ou mal nommé dans la liste — ferait passer ce test
    sans rien prouver.
    """
    settings.MIDDLEWARE = list(settings.MIDDLEWARE) + [
        'apps.accounts.middleware.employee_link_required'
        '.EmployeeLinkRequiredMiddleware',
    ]

    def ouvrir(nom, declare):
        user = django_user_model.objects.create_user(
            username=nom, password='motdepasse-test')
        user.profile.without_employee_record = declare
        user.profile.companies.add(company)
        user.profile.current_company = company
        user.profile.save()
        client.force_login(user)
        return client.get(reverse('accounts:profile'))

    temoin = ouvrir('presta-non-declare', False)
    assert temoin.status_code == 302
    assert 'missing-employee' in temoin['Location']

    declare = ouvrir('presta-declare', True)
    assert declare.status_code == 200


# -- Le retour en arrière ----------------------------------------------------

def test_rattacher_un_salarie_retire_la_declaration(company, salarie,
                                                    django_user_model):
    """La déclaration devient fausse dès que la fiche existe. La laisser
    exempterait pour toujours des contrôles un compte pourtant rattaché."""
    from apps.accounts.services.user_employee_link_service import (
        link_user_to_employee,
    )

    user = django_user_model.objects.create_user(
        username='devenu-salarie', password='motdepasse-test')
    user.profile.without_employee_record = True
    user.profile.save()

    link_user_to_employee(user, salarie)

    user.profile.refresh_from_db()
    assert user.profile.without_employee_record is False


def test_le_formulaire_rh_retire_aussi_la_declaration(company, salarie,
                                                      django_user_model):
    """L'écran RH écrit Employee.user directement, sans passer par le
    service : le signal sur Employee est le seul point qui couvre ce chemin."""
    user = django_user_model.objects.create_user(
        username='embauche', password='motdepasse-test')
    user.profile.without_employee_record = True
    user.profile.save()

    salarie.user = user
    salarie.save()

    user.profile.refresh_from_db()
    assert user.profile.without_employee_record is False


def test_detacher_un_salarie_reste_interdit_sans_declaration(
        company, salarie, django_user_model):
    """Le compte retomberait dans l'état invalide que tout ceci évite."""
    from apps.accounts.services.user_employee_link_service import (
        link_user_to_employee, unlink_user_from_employee,
    )

    user = django_user_model.objects.create_user(
        username='toujours-salarie', password='motdepasse-test')
    link_user_to_employee(user, salarie)

    with pytest.raises(ValidationError):
        unlink_user_from_employee(user)


def test_declarer_le_compte_permet_de_detacher_le_salarie(
        company, salarie, django_user_model):
    """Le chemin de sortie : on déclare d'abord, on détache ensuite."""
    from apps.accounts.services.user_employee_link_service import (
        link_user_to_employee, unlink_user_from_employee,
    )

    user = django_user_model.objects.create_user(
        username='parti-en-presta', password='motdepasse-test')
    link_user_to_employee(user, salarie)

    user.profile.refresh_from_db()
    user.profile.without_employee_record = True
    user.profile.save()

    unlink_user_from_employee(user)
    salarie.refresh_from_db()
    assert salarie.user_id is None


# -- Ce que les écrans montrent ----------------------------------------------

def test_la_liste_distingue_le_declare_de_l_oubli(admin_connecte, company,
                                                  django_user_model):
    """Les deux en rouge, ou les deux en gris, et le signal ne sert plus à
    rien : c'est toute la raison de la case."""
    declare = django_user_model.objects.create_user(
        username='externe', password='motdepasse-test')
    declare.profile.without_employee_record = True
    declare.profile.companies.add(company)
    declare.profile.save()

    oubli = django_user_model.objects.create_user(
        username='oubli', password='motdepasse-test')
    oubli.profile.companies.add(company)
    oubli.profile.save()

    corps = admin_connecte.get(reverse('accounts:user_list')).content.decode()
    # La pastille d'avertissement n'existe que pour l'oubli, et le libelle
    # discret que pour la declaration : chercher le mot seul passerait aussi
    # si les deux lignes portaient la meme chose.
    assert 'Sans fiche salari' in corps
    assert 'status-badge status-warning' in corps
    assert 'rattacher' in corps


def test_la_fiche_du_compte_ne_crie_pas_a_l_erreur(admin_connecte, company,
                                                   django_user_model):
    """Afficher « doit être lié à une fiche salarié » sur un compte
    volontairement externe apprend à ignorer l'avertissement."""
    declare = django_user_model.objects.create_user(
        username='externe-fiche', password='motdepasse-test')
    declare.profile.without_employee_record = True
    declare.profile.save()

    corps = admin_connecte.get(
        reverse('accounts:user_detail', args=[declare.pk])).content.decode()
    assert 'doit être lié à une fiche salarié' not in corps
    assert "C'est volontaire" in corps


def test_l_admin_django_ne_signale_pas_le_compte_declare(company,
                                                         django_user_model):
    from apps.accounts.admin import get_employee_link

    user = django_user_model.objects.create_user(
        username='externe-admin', password='motdepasse-test')
    assert '⚠' in get_employee_link(user)

    user.profile.without_employee_record = True
    user.profile.save()
    assert '⚠' not in get_employee_link(user)
