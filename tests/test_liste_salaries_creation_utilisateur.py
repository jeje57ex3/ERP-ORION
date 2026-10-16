"""La liste des salariés à l'écran de création d'un utilisateur.

Trois conditions filtrent cette liste, et chacune peut la vider :

    Employee.objects.filter(company=…, is_active=True, user__isnull=True)

L'entreprise courante, l'activité de la fiche, et le fait de ne pas être
DÉJÀ rattaché — `Employee.user` est un OneToOne, un salarié ne peut donc
pas porter deux comptes.

**Le défaut n'était pas le filtre, c'était le silence.** Un `<select>` vide
sans un mot d'explication envoie chercher la cause dans la base de données,
alors que les trois remèdes n'ont rien à voir : créer des fiches, changer
d'entreprise courante, ou constater que tout le monde a déjà un compte.
Chaque cas a donc son test, et le gabarit est réellement rendu — une faute
de `blocktrans` ne se voit pas autrement.

Deux fuites inter-entreprises corrigées au passage, chacune avec son test :
sans entreprise courante l'écran listait les salariés de TOUTES les
sociétés, et `?employee=<pk>` pré-sélectionnait la fiche de n'importe
laquelle.
"""

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


# ── Terrain ─────────────────────────────────────────────────────────────────

def _salarie(company, prenom='Marc', nom='Durand', **extra):
    from apps.hr.models import Employee
    return Employee.objects.create(
        company=company, first_name=prenom, last_name=nom,
        email=f'{prenom.lower()}@example.test', **extra)


@pytest.fixture
def patron(client, company, django_user_model):
    """Un administrateur de l'entreprise : seul habilité à créer un compte."""
    user = django_user_model.objects.create_user(
        username='patron', password='motdepasse-test')
    user.profile.role = 'admin'
    user.profile.companies.add(company)
    user.profile.current_company = company
    user.profile.save()
    client.force_login(user)
    return client


@pytest.fixture
def patron_sans_entreprise(client, company, django_user_model):
    """Administrateur dont le profil n'est rattaché à aucune entreprise.

    L'entreprise existe (sinon SetupRequiredMiddleware détournerait tout
    vers /setup/) mais ce compte n'y a pas accès : request.current_company
    vaut donc None.
    """
    user = django_user_model.objects.create_user(
        username='admin-orphelin', password='motdepasse-test')
    user.profile.role = 'admin'
    user.profile.save()
    client.force_login(user)
    return client


def _diagnostic(company):
    from apps.accounts.services.user_employee_link_service import (
        diagnostic_rattachement,
    )
    return diagnostic_rattachement(company)


# ═══ LA LISTE FAIT CE QU'ON ATTEND ══════════════════════════════════════════

def test_un_salarie_libre_apparait_dans_la_liste(patron, company):
    """Le cas normal. Sans ce test, tous les autres pourraient passer alors
    que la liste est vide en permanence."""
    salarie = _salarie(company, 'Marc', 'Durand')

    reponse = patron.get(reverse('accounts:user_create'))
    corps = reponse.content.decode()

    assert reponse.status_code == 200
    assert 'Durand' in corps
    assert str(salarie.pk) in corps


def test_le_formulaire_propose_bien_ce_salarie(company):
    from apps.accounts.forms import UserCreateForm

    salarie = _salarie(company, 'Marc', 'Durand')
    form = UserCreateForm(company=company)
    assert salarie in set(form.fields['employee'].queryset)


def test_quand_la_liste_est_pleine_aucun_diagnostic_ne_s_affiche(patron,
                                                                 company):
    """L'avertissement ne doit pas crier quand tout va bien, sinon on
    apprend à l'ignorer."""
    _salarie(company)

    assert _diagnostic(company)['cause'] is None
    corps = patron.get(reverse('accounts:user_create')).content.decode()
    assert 'Aucun salarié à rattacher' not in corps


# ═══ POURQUOI LA LISTE EST VIDE ═════════════════════════════════════════════

def test_aucune_fiche_salarie_le_dit_et_propose_d_en_creer(patron, company):
    infos = _diagnostic(company)
    assert infos['cause'] == 'aucun_salarie'
    assert infos['total'] == 0

    corps = patron.get(reverse('accounts:user_create')).content.decode()
    assert 'Aucune fiche' in corps
    # Le remede, et pas seulement le constat.
    assert reverse('hr:employee_create') in corps


def test_un_salarie_deja_rattache_sort_de_la_liste_et_c_est_explique(
        patron, company, django_user_model):
    """Employee.user est un OneToOne : un salarié déjà lié ne peut pas
    recevoir un second compte. C'est correct, mais l'écran ne le disait
    pas."""
    autre = django_user_model.objects.create_user(
        username='deja-la', password='motdepasse-test')
    _salarie(company, 'Marc', 'Durand', user=autre)

    infos = _diagnostic(company)
    assert infos['cause'] == 'tous_rattaches'
    assert infos['deja_rattaches'] == 1
    assert infos['rattachables'] == 0

    corps = patron.get(reverse('accounts:user_create')).content.decode()
    assert 'Durand' not in corps
    assert 'déjà un compte' in corps


def test_une_fiche_desactivee_sort_de_la_liste_et_c_est_explique(patron,
                                                                 company):
    _salarie(company, 'Paul', 'Martin', is_active=False)

    infos = _diagnostic(company)
    assert infos['cause'] == 'tous_desactives'
    assert infos['desactives'] == 1

    corps = patron.get(reverse('accounts:user_create')).content.decode()
    assert 'Martin' not in corps
    assert 'désactivée' in corps or 'désactivées' in corps


def test_le_cas_mixte_donne_les_deux_nombres(patron, company,
                                             django_user_model):
    """Dire « tous rattachés » alors que la moitié est désactivée enverrait
    chercher au mauvais endroit."""
    autre = django_user_model.objects.create_user(
        username='deja-la', password='motdepasse-test')
    _salarie(company, 'Marc', 'Durand', user=autre)
    _salarie(company, 'Paul', 'Martin', is_active=False)

    infos = _diagnostic(company)
    assert infos['cause'] == 'rattaches_ou_desactives'
    assert infos['deja_rattaches'] == 1
    assert infos['desactives'] == 1
    assert infos['total'] == 2

    corps = patron.get(reverse('accounts:user_create')).content.decode()
    assert 'Aucun salarié à rattacher' in corps


def test_le_diagnostic_mentionne_la_case_sans_fiche_salarie(patron, company):
    """La sortie existe : l'écran doit la nommer, sinon on crée une fausse
    fiche salarié pour contourner le blocage."""
    corps = patron.get(reverse('accounts:user_create')).content.decode()
    assert 'sans fiche salarié' in corps


# ═══ LES DEUX FUITES INTER-ENTREPRISES ══════════════════════════════════════

def test_le_salarie_d_une_autre_entreprise_n_apparait_pas(patron, company,
                                                          company_b):
    _salarie(company, 'Marc', 'Durand')
    _salarie(company_b, 'Secret', 'Confidentiel')

    corps = patron.get(reverse('accounts:user_create')).content.decode()
    assert 'Durand' in corps
    assert 'Confidentiel' not in corps


def test_sans_entreprise_courante_la_liste_est_vide_et_non_celle_de_tous(
        patron_sans_entreprise, company, company_b):
    """L'écran listait les salariés de TOUTES les sociétés dans ce cas.
    Mieux vaut une liste vide, que le diagnostic explique."""
    _salarie(company, 'Marc', 'Durand')
    _salarie(company_b, 'Secret', 'Confidentiel')

    reponse = patron_sans_entreprise.get(reverse('accounts:user_create'))
    corps = reponse.content.decode()

    assert reponse.status_code == 200
    assert 'Durand' not in corps
    assert 'Confidentiel' not in corps
    assert "Aucune entreprise n'est active" in corps


def test_la_liste_vide_sans_entreprise_vaut_aussi_a_la_VALIDATION(company):
    """Borner le seul affichage laisserait passer un identifiant forgé."""
    from apps.accounts.forms import UserCreateForm

    salarie = _salarie(company, 'Marc', 'Durand')
    form = UserCreateForm({
        'username': 'tentative', 'first_name': 'A', 'last_name': 'B',
        'email': 'a@b.test', 'password1': 'MotDePasse-Solide-9',
        'password2': 'MotDePasse-Solide-9', 'role': 'user',
        'employee': salarie.pk,
    }, company=None)

    assert not form.is_valid()
    assert 'employee' in form.errors


def test_un_prefill_d_une_autre_entreprise_est_ignore(patron, company,
                                                      company_b):
    """« ?employee=<pk> » d'une autre société pré-sélectionnait la fiche et
    affichait son nom. La validation l'aurait refusée ensuite, mais le nom
    avait déjà fuité."""
    etranger = _salarie(company_b, 'Secret', 'Confidentiel')

    corps = patron.get(reverse('accounts:user_create'),
                       {'employee': etranger.pk}).content.decode()
    assert 'Confidentiel' not in corps


def test_un_prefill_de_la_bonne_entreprise_fonctionne_toujours(patron,
                                                               company):
    """La correction ne doit pas casser le chemin légitime, venu de la
    fiche salarié."""
    salarie = _salarie(company, 'Marc', 'Durand')

    reponse = patron.get(reverse('accounts:user_create'),
                         {'employee': salarie.pk})
    assert reponse.status_code == 200
    assert reponse.context['employee_prefill'] == salarie


def test_un_prefill_deja_rattache_est_ignore(patron, company,
                                             django_user_model):
    autre = django_user_model.objects.create_user(
        username='deja-la', password='motdepasse-test')
    salarie = _salarie(company, 'Marc', 'Durand', user=autre)

    reponse = patron.get(reverse('accounts:user_create'),
                         {'employee': salarie.pk})
    assert reponse.context['employee_prefill'] is None


def test_un_prefill_absurde_ne_casse_pas_l_ecran(patron, company):
    """Un .get() nu levait DoesNotExist, un pk non entier lève ValueError :
    le .filter().first() ne fait ni l'un ni l'autre."""
    for valeur in ('999999', 'abc', '', '0'):
        reponse = patron.get(reverse('accounts:user_create'),
                             {'employee': valeur})
        assert reponse.status_code == 200, valeur


# ═══ LA LISTE ET SON EXPLICATION NE PEUVENT PAS DIVERGER ════════════════════

def test_la_liste_et_le_diagnostic_viennent_de_la_meme_source(company,
                                                              django_user_model):
    """Deux filtres écrits séparément finissent par ne plus dire la même
    chose, et l'écran expliquerait alors une liste qui n'est pas celle
    qu'il affiche."""
    from apps.accounts.forms import UserCreateForm

    autre = django_user_model.objects.create_user(
        username='deja-la', password='motdepasse-test')
    _salarie(company, 'Marc', 'Durand')
    _salarie(company, 'Paul', 'Martin', user=autre)
    _salarie(company, 'Luc', 'Bernard', is_active=False)

    form = UserCreateForm(company=company)
    assert (form.fields['employee'].queryset.count()
            == form.diagnostic_salaries['rattachables'] == 1)


def test_le_diagnostic_porte_toujours_les_memes_cles(company):
    """Le gabarit n'a pas à tester l'existence de chaque clé."""
    attendues = {'cause', 'rattachables', 'deja_rattaches', 'desactives',
                 'total', 'company'}
    assert set(_diagnostic(company)) == attendues
    assert set(_diagnostic(None)) == attendues


# ═══ LE GABARIT REND VRAIMENT ═══════════════════════════════════════════════

@pytest.mark.parametrize('cas', [
    'aucun_salarie', 'tous_rattaches', 'tous_desactives',
    'rattaches_ou_desactives', 'plein',
])
def test_chaque_cas_rend_sans_erreur_de_gabarit(patron, company,
                                                django_user_model, cas):
    """Une faute de blocktrans ne se voit pas autrement qu'en rendant la
    page : elle lève TemplateSyntaxError à l'exécution, pas à l'import."""
    if cas == 'tous_rattaches':
        u = django_user_model.objects.create_user(username='u1',
                                                  password='motdepasse-test')
        _salarie(company, 'Marc', 'Durand', user=u)
    elif cas == 'tous_desactives':
        _salarie(company, 'Paul', 'Martin', is_active=False)
    elif cas == 'rattaches_ou_desactives':
        u = django_user_model.objects.create_user(username='u2',
                                                  password='motdepasse-test')
        _salarie(company, 'Marc', 'Durand', user=u)
        _salarie(company, 'Paul', 'Martin', is_active=False)
    elif cas == 'plein':
        _salarie(company, 'Jean', 'Petit')

    reponse = patron.get(reverse('accounts:user_create'))
    assert reponse.status_code == 200
    assert reponse.context['diagnostic_salaries'] is not None


def test_le_pluriel_du_diagnostic_est_correct(patron, company,
                                              django_user_model):
    """blocktrans count / plural : au singulier comme au pluriel, la phrase
    doit rester lisible."""
    u1 = django_user_model.objects.create_user(username='u1',
                                               password='motdepasse-test')
    _salarie(company, 'Marc', 'Durand', user=u1)

    corps = patron.get(reverse('accounts:user_create')).content.decode()
    assert 'Le seul' in corps or 'seul salarié' in corps

    u2 = django_user_model.objects.create_user(username='u2',
                                               password='motdepasse-test')
    _salarie(company, 'Paul', 'Martin', user=u2)

    corps = patron.get(reverse('accounts:user_create')).content.decode()
    assert '2 salariés' in corps


# ═══ LA CRÉATION FONCTIONNE TOUJOURS ════════════════════════════════════════

def test_rattacher_un_salarie_cree_bien_le_compte(patron, company,
                                                  django_user_model):
    """Le chemin complet, pour que les corrections ci-dessus ne se
    contentent pas d'expliquer un écran devenu inutilisable."""
    salarie = _salarie(company, 'Marc', 'Durand')

    patron.post(reverse('accounts:user_create'), {
        'username': 'mdurand', 'first_name': 'Marc', 'last_name': 'Durand',
        'email': 'marc@example.test', 'password1': 'MotDePasse-Solide-9',
        'password2': 'MotDePasse-Solide-9', 'role': 'user',
        'employee': salarie.pk,
    })

    cree = django_user_model.objects.get(username='mdurand')
    salarie.refresh_from_db()
    assert salarie.user == cree
    assert cree.profile.without_employee_record is False
