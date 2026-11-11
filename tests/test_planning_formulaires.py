"""« J'appuie sur Ajouter et rien ne se passe, je reste sur la même page. »

LE DÉFAUT, ET POURQUOI IL ÉTAIT INVISIBLE

`EmployeeProfileForm` exige `weekly_capacity_hours`. Le champ a bien une
valeur par défaut au niveau du modèle (35,0), mais PAS `blank=True` : Django
en fait donc un champ de formulaire OBLIGATOIRE — une valeur par défaut
fournit l'initiale, elle ne rend rien facultatif.

Et le gabarit ne rendait ce champ NULLE PART. Il ne pouvait donc jamais être
rempli, la validation échouait à chaque envoi, la vue réaffichait la même
page — et le gabarit n'affichait les erreurs que de `form.user`. L'erreur
existait, personne ne pouvait la voir.

Le même défaut existait sur l'écran des tâches : le gabarit rendait
`estimated_hours` (facultatif) et omettait `estimated_minutes` (requis).

Et en MODIFICATION d'un employé, `user` restait requis alors que le gabarit
ne le rend que pour une création — donc enregistrer une fiche existante
échouait aussi, pour un champ que personne ne voyait.
"""
import re
from pathlib import Path

import pytest


GABARITS = Path('templates/work_planning')


def _paires():
    """Chaque formulaire du planning avec le gabarit qui le rend."""
    from apps.work_planning import forms

    return [
        (forms.EmployeeProfileForm, 'employee_form.html'),
        (forms.EmployeeAvailabilityConstraintForm,
         'employee_constraint_form.html'),
        (forms.WorkMissionForm, 'mission_form.html'),
        (forms.WorkTaskForm, 'task_form.html'),
        (forms.CustomerRequestForm, 'customer_request_form.html'),
        (forms.DedicatedTimeBlockForm, 'time_block_form.html'),
    ]


# ── 1. LE GARDE-FOU DE LA CLASSE ENTIÈRE ─────────────────────────────────────

@pytest.mark.django_db
@pytest.mark.parametrize('classe,gabarit', _paires(),
                         ids=[p[1] for p in _paires()])
def test_chaque_champ_requis_est_rendu_par_son_gabarit(classe, gabarit):
    """UN CHAMP REQUIS ET NON RENDU EST UN FORMULAIRE IMPOSSIBLE À ENVOYER.

    C'est ce test qui compte le plus de ce fichier : il ne corrige pas un
    défaut, il interdit toute la famille. Deux des six gabarits étaient
    fautifs, et rien ne le signalait — ni une erreur, ni un journal, ni un
    test.

    Un gabarit qui rend `{{ form }}` en bloc est accepté : tous ses champs
    y sont par construction.
    """
    texte = (GABARITS / gabarit).read_text(encoding='utf-8')
    rendu_en_bloc = bool(re.search(r'{{\s*form(\.as_\w+)?\s*}}', texte))

    form = classe()
    requis = [nom for nom, champ in form.fields.items() if champ.required]
    absents = [nom for nom in requis if f'form.{nom}' not in texte]

    assert rendu_en_bloc or not absents, (
        f'{gabarit} ne rend pas {absents}, que le formulaire exige : '
        f'le bouton d’envoi ne pourra jamais aboutir.'
    )


@pytest.mark.django_db
@pytest.mark.parametrize('classe,gabarit', _paires(),
                         ids=[p[1] for p in _paires()])
def test_chaque_gabarit_affiche_les_erreurs(classe, gabarit):
    """Un formulaire qui refuse doit DIRE pourquoi.

    Les gabarits n'affichaient les erreurs que d'un ou deux champs choisis.
    Toute erreur ailleurs restait muette, et l'utilisateur concluait que le
    bouton ne marchait pas. C'est précisément ce qui a rendu le défaut
    ci-dessus indiagnosticable.
    """
    texte = (GABARITS / gabarit).read_text(encoding='utf-8')
    affiche_tout = (
        '_erreurs_du_formulaire.html' in texte
        or 'form.non_field_errors' in texte
        or re.search(r'{{\s*form(\.as_\w+)?\s*}}', texte)
    )
    assert affiche_tout, (
        f'{gabarit} n’affiche pas l’ensemble des erreurs : une validation '
        f'qui échoue y serait silencieuse.'
    )


# ── 2. Le défaut nommé, sur l'écran des employés ─────────────────────────────

def test_la_capacite_hebdomadaire_est_bien_requise():
    """Le piège qui a produit la panne : `default` ne vaut pas `blank=True`.

    Une valeur par défaut au niveau du modèle fournit l'INITIALE du champ de
    formulaire ; elle ne le rend pas facultatif. Seul `blank=True` le ferait.
    """
    from apps.work_planning.forms import EmployeeProfileForm

    form = EmployeeProfileForm()
    champ = form.fields['weekly_capacity_hours']
    assert champ.required is True
    assert champ.initial is not None


def test_le_gabarit_des_employes_rend_la_capacite_hebdomadaire():
    texte = (GABARITS / 'employee_form.html').read_text(encoding='utf-8')
    assert 'form.weekly_capacity_hours' in texte


def test_le_gabarit_des_taches_rend_les_minutes_estimees():
    """Il rendait `estimated_hours`, facultatif, et omettait
    `estimated_minutes`, requis — que le planificateur automatique
    utilise."""
    texte = (GABARITS / 'task_form.html').read_text(encoding='utf-8')
    assert 'form.estimated_minutes' in texte


# ── 3. Le parcours réel : ajouter un employé ─────────────────────────────────

@pytest.fixture
def entreprise(db):
    from apps.core.models import Company
    return Company.objects.create(name='Volt SARL', slug='volt-sarl')


@pytest.fixture
def salarie(db, entreprise, django_user_model):
    """Un utilisateur rattaché à l'entreprise.

    Le rattachement n'est pas décoratif : le formulaire borne le choix aux
    utilisateurs dont le profil porte cette entreprise.
    """
    utilisateur = django_user_model.objects.create_user(
        username='pierre', password='motdepasse-test', email='p@volt.fr')
    utilisateur.profile.companies.add(entreprise)
    return utilisateur


def _donnees_du_formulaire(**surcharges):
    """Ce que le gabarit envoie réellement, champ par champ."""
    donnees = {
        'role': 'employee',
        'color_code': '#3B82F6',
        'default_hours_per_day': '8.0',
        'weekly_capacity_hours': '35.0',
        'skills_input': 'electricite, plomberie',
        'normal_work_start': '08:00',
        'normal_work_end': '17:00',
    }
    donnees.update(surcharges)
    return donnees


@pytest.mark.django_db
def test_le_formulaire_est_valide_avec_ce_que_le_gabarit_envoie(
        entreprise, salarie):
    """LE TEST QUI AURAIT ATTRAPÉ LA PANNE.

    Il ne vérifie pas que le formulaire accepte des données complètes —
    c'était déjà vrai. Il vérifie qu'il accepte ce que LE GABARIT envoie.
    """
    from apps.work_planning.forms import EmployeeProfileForm

    form = EmployeeProfileForm(
        _donnees_du_formulaire(user=str(salarie.pk)), company=entreprise)
    assert form.is_valid(), form.errors.as_json()


@pytest.mark.django_db
def test_sans_capacite_hebdomadaire_l_erreur_porte_bien_sur_ce_champ(
        entreprise, salarie):
    """La preuve du mécanisme : c'est bien ce champ qui bloquait."""
    from apps.work_planning.forms import EmployeeProfileForm

    donnees = _donnees_du_formulaire(user=str(salarie.pk))
    donnees.pop('weekly_capacity_hours')

    form = EmployeeProfileForm(donnees, company=entreprise)
    assert form.is_valid() is False
    assert 'weekly_capacity_hours' in form.errors


@pytest.mark.django_db
def test_l_employe_est_vraiment_cree(client, entreprise, salarie,
                                      django_user_model):
    """De bout en bout, par la page, comme l'utilisateur."""
    from apps.access_control.models import ERPModule
    from apps.private_saas.models import CompanyModule
    from apps.work_planning.models import EmployeeProfile

    ERPModule.objects.get_or_create(
        code='work_planning', defaults={'name': 'Planning'})
    CompanyModule.objects.update_or_create(
        company=entreprise, module_code='work_planning',
        defaults={'is_enabled': True, 'module_name': 'Planning'})

    patron = django_user_model.objects.create_superuser(
        username='patron', password='motdepasse-test', email='pa@volt.fr')
    client.force_login(patron)

    reponse = client.post(
        '/erp/planning/equipe/ajouter/',
        _donnees_du_formulaire(user=str(salarie.pk)), follow=True)

    assert reponse.status_code == 200
    profils = EmployeeProfile.objects.filter(user=salarie)
    assert profils.count() == 1, (
        'le profil n’a pas été créé — on est resté sur la même page')
    assert profils.first().skills == ['electricite', 'plomberie']


@pytest.mark.django_db
def test_une_erreur_s_affiche_au_lieu_de_ne_rien_dire(client, entreprise,
                                                       django_user_model):
    """Le symptôme rapporté : rien ne se passe, aucun message.

    Désormais, un envoi qui échoue affiche la raison.
    """
    from apps.access_control.models import ERPModule
    from apps.private_saas.models import CompanyModule

    ERPModule.objects.get_or_create(
        code='work_planning', defaults={'name': 'Planning'})
    CompanyModule.objects.update_or_create(
        company=entreprise, module_code='work_planning',
        defaults={'is_enabled': True, 'module_name': 'Planning'})

    patron = django_user_model.objects.create_superuser(
        username='patron', password='motdepasse-test', email='pa@volt.fr')
    client.force_login(patron)

    # Sans « user », qui est requis : le formulaire doit refuser ET le dire.
    reponse = client.post('/erp/planning/equipe/ajouter/',
                          _donnees_du_formulaire())

    assert reponse.status_code == 200
    contenu = reponse.content.decode()
    assert 'Le formulaire n' in contenu, (
        'la page ne dit pas pourquoi l’enregistrement a échoué')


# ── 4. La modification, cassée pour la même raison ───────────────────────────

@pytest.mark.django_db
def test_modifier_une_fiche_n_exige_plus_un_champ_invisible(entreprise,
                                                             salarie):
    """Le gabarit n'affiche « user » qu'à la création, et le champ restait
    requis : chaque enregistrement d'une fiche existante échouait sur un
    champ que personne ne voyait."""
    from apps.work_planning.forms import EmployeeProfileForm
    from apps.work_planning.models import EmployeeProfile

    profil = EmployeeProfile.objects.create(
        company=entreprise, user=salarie, role='employee')

    form = EmployeeProfileForm(
        _donnees_du_formulaire(), instance=profil, company=entreprise)

    assert 'user' not in form.fields, (
        '« user » reste exigé en modification alors qu’il n’est pas rendu')
    assert form.is_valid(), form.errors.as_json()

    enregistre = form.save()
    assert enregistre.user == salarie, (
        'l’utilisateur rattaché a été perdu lors de la modification')


@pytest.mark.django_db
def test_la_creation_propose_toujours_le_choix_de_l_utilisateur(entreprise,
                                                                salarie):
    """La contrepartie : retirer le champ en modification ne doit pas le
    retirer de la création."""
    from apps.work_planning.forms import EmployeeProfileForm

    form = EmployeeProfileForm(company=entreprise)
    assert 'user' in form.fields
    assert salarie in form.fields['user'].queryset


@pytest.mark.django_db
def test_le_choix_reste_borne_a_l_entreprise(entreprise, salarie,
                                              django_user_model):
    """Un utilisateur d'une autre société ne doit pas être proposable."""
    from apps.core.models import Company
    from apps.work_planning.forms import EmployeeProfileForm

    autre = Company.objects.create(name='Autre SARL', slug='autre-sarl')
    etranger = django_user_model.objects.create_user(
        username='etranger', password='motdepasse-test', email='e@autre.fr')
    etranger.profile.companies.add(autre)

    form = EmployeeProfileForm(company=entreprise)
    assert salarie in form.fields['user'].queryset
    assert etranger not in form.fields['user'].queryset
