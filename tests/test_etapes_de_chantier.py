"""Étapes de chantier et points à remplir.

Un chantier naissait nu. `ProjectPlanStep` existait depuis le début — treize
types d'étapes, dates, avancement, visibilité client — mais **rien ne le
remplissait** : `project_create` enregistrait le chantier et s'arrêtait là,
et seul le portail client savait lire ces étapes. Aucun écran de l'ERP ne
permettait d'en créer une. Et il manquait l'essentiel : les points à relever
sur place, pour ne pas découvrir le jour de la pose qu'il faut une nacelle.

Ce fichier tient les quatre propriétés sur lesquelles tout repose.

**1. La copie est un INSTANTANÉ.** Retoucher un modèle ne doit pas réécrire
un chantier en cours. Une question à laquelle on a répondu ne peut pas
changer de sens après coup : la réponse resterait, la question aurait changé.

**2. `False` est une RÉPONSE.** « Nacelle nécessaire : non » n'est pas un
oubli. C'est le piège classique de ce genre de propriété — un
`if not self.answer_boolean` compterait cette réponse comme manquante, et
l'avertissement crierait au loup sur tous les chantiers correctement
renseignés jusqu'à ce que plus personne ne le lise.

**3. On AVERTIT, on ne bloque pas.** Décision explicite. Un formulaire qui
refuse d'enregistrer parce qu'un champ manque fait inventer des réponses, et
une réponse inventée est pire qu'une case vide : la case vide se voit.

**4. Les réponses sont dans des colonnes TYPÉES.** C'est ce qui rend
« quels chantiers demandent une nacelle ? » répondable en SQL. Un JSON
opaque ne se filtre pas.

S'y ajoute l'isolation multi-entreprises, vérifiée sur chacune des quinze
vues : un objet ne s'atteint qu'en remontant jusqu'à `company`, jamais par
sa seule clé primaire.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


# ── Terrain ─────────────────────────────────────────────────────────────────

@pytest.fixture
def entreprise(db):
    from apps.core.models import Company
    return Company.objects.create(name='Volt SARL', slug='volt-sarl')


@pytest.fixture
def autre_entreprise(db):
    from apps.core.models import Company
    return Company.objects.create(name='Ampere SA', slug='ampere-sa')


@pytest.fixture
def client_crm(entreprise):
    from apps.crm.models import Customer
    return Customer.objects.create(company=entreprise, name='Mme Martin')


@pytest.fixture
def connecte(client, entreprise, django_user_model):
    user = django_user_model.objects.create_user(
        username='chef', password='motdepasse-test')
    user.profile.companies.add(entreprise)
    user.profile.current_company = entreprise
    user.profile.save()
    client.force_login(user)
    client.user = user
    return client


@pytest.fixture
def chantier(entreprise, client_crm):
    from apps.btp.models import BTPProject
    return BTPProject.objects.create(
        company=entreprise, name='Rénovation Martin', customer=client_crm,
        start_date=date(2026, 3, 2))


@pytest.fixture
def modele(entreprise):
    """Deux étapes, quatre points, tous les types de réponse représentés."""
    from apps.btp.models import (
        ProjectTemplate, ProjectTemplateItem, ProjectTemplateStep)

    gabarit = ProjectTemplate.objects.create(
        company=entreprise, name='Électricité', is_default=True)

    visite = ProjectTemplateStep.objects.create(
        template=gabarit, name='Analyse sur place', step_type='technical_visit',
        order=1, offset_days=-7)
    ProjectTemplateItem.objects.create(
        step=visite, label='Nacelle nécessaire ?', answer_type='yes_no',
        is_required=True, order=1)
    ProjectTemplateItem.objects.create(
        step=visite, label='Hauteur sous plafond', answer_type='number',
        unit='m', is_required=True, order=2)
    ProjectTemplateItem.objects.create(
        step=visite, label='Nature des murs', answer_type='choice',
        options=['Placo', 'Béton'], order=3)

    commande = ProjectTemplateStep.objects.create(
        template=gabarit, name='Commande du matériel',
        step_type='material_prep', order=2, offset_days=-2)
    ProjectTemplateItem.objects.create(
        step=commande, label='Date de livraison annoncée',
        answer_type='date', is_required=True, order=1)

    return gabarit


@pytest.fixture
def chantier_avec_etapes(chantier, modele):
    from apps.btp import services_etapes as svc
    svc.appliquer_le_modele(chantier, modele)
    return chantier


# ── 1. L'application d'un modèle ────────────────────────────────────────────

def test_appliquer_un_modele_cree_les_etapes_et_les_points(chantier, modele):
    from apps.btp import services_etapes as svc
    from apps.btp.models import ProjectPlanStep, ProjectStepItem

    assert svc.appliquer_le_modele(chantier, modele) == 2

    etapes = list(ProjectPlanStep.objects.filter(project=chantier)
                  .order_by('order'))
    assert [e.name for e in etapes] == ['Analyse sur place',
                                        'Commande du matériel']
    assert etapes[0].step_type == 'technical_visit'
    assert ProjectStepItem.objects.filter(step__project=chantier).count() == 4


def test_les_dates_sont_calculees_depuis_le_debut_du_chantier(chantier,
                                                              modele):
    """J-7 et J-2 comptés depuis `start_date`."""
    from apps.btp import services_etapes as svc
    from apps.btp.models import ProjectPlanStep

    svc.appliquer_le_modele(chantier, modele)
    etapes = list(ProjectPlanStep.objects.filter(project=chantier)
                  .order_by('order'))
    assert etapes[0].planned_date == date(2026, 3, 2) - timedelta(days=7)
    assert etapes[1].planned_date == date(2026, 3, 2) - timedelta(days=2)


def test_sans_date_de_debut_les_etapes_restent_sans_date(entreprise,
                                                         client_crm, modele):
    """Mieux une étape sans date qu'une date fausse.

    Un décalage en jours ne désigne rien s'il n'y a pas d'origine. Prendre
    « aujourd'hui » par défaut produirait des dates que personne n'a
    choisies, et qu'on prendrait pour des engagements.
    """
    from apps.btp import services_etapes as svc
    from apps.btp.models import BTPProject, ProjectPlanStep

    nu = BTPProject.objects.create(
        company=entreprise, name='Sans date', customer=client_crm)
    svc.appliquer_le_modele(nu, modele)
    assert all(e.planned_date is None
               for e in ProjectPlanStep.objects.filter(project=nu))


def test_appliquer_deux_fois_ne_double_pas_les_etapes(chantier, modele):
    """Le second passage ne fait RIEN plutôt que de dupliquer.

    Doubler les étapes noierait les réponses déjà saisies dans une seconde
    copie vide des mêmes questions, sans qu'on sache laquelle est la bonne.
    """
    from apps.btp import services_etapes as svc
    from apps.btp.models import ProjectPlanStep

    svc.appliquer_le_modele(chantier, modele)
    assert svc.appliquer_le_modele(chantier, modele) == 0
    assert ProjectPlanStep.objects.filter(project=chantier).count() == 2


def test_remplacer_repart_de_zero(chantier, modele):
    from apps.btp import services_etapes as svc
    from apps.btp.models import ProjectPlanStep

    svc.appliquer_le_modele(chantier, modele)
    premier = list(ProjectPlanStep.objects.filter(project=chantier)
                   .values_list('pk', flat=True))

    assert svc.appliquer_le_modele(chantier, modele, remplacer=True) == 2
    second = list(ProjectPlanStep.objects.filter(project=chantier)
                  .values_list('pk', flat=True))
    assert ProjectPlanStep.objects.filter(project=chantier).count() == 2
    assert set(premier) & set(second) == set()


def test_appliquer_aucun_modele_ne_leve_pas(chantier):
    from apps.btp import services_etapes as svc
    assert svc.appliquer_le_modele(chantier, None) == 0


# ── 2. La copie est un instantané ───────────────────────────────────────────

def test_modifier_le_modele_ne_touche_pas_le_chantier(chantier_avec_etapes,
                                                      modele):
    """LA propriété du fichier.

    Si les points de chantier lisaient le modèle à travers une clé, cette
    retouche réécrirait une question déjà répondue — la réponse resterait,
    la question aurait changé.
    """
    from apps.btp.models import ProjectStepItem, ProjectTemplateItem

    point_modele = ProjectTemplateItem.objects.get(
        label='Nacelle nécessaire ?')
    point_modele.label = 'Échafaudage nécessaire ?'
    point_modele.is_required = False
    point_modele.save()

    copie = ProjectStepItem.objects.get(step__project=chantier_avec_etapes,
                                        label='Nacelle nécessaire ?')
    assert copie.is_required is True


def test_supprimer_le_modele_ne_touche_pas_le_chantier(chantier_avec_etapes,
                                                       modele):
    from apps.btp.models import ProjectPlanStep, ProjectStepItem

    modele.delete()
    assert ProjectPlanStep.objects.filter(
        project=chantier_avec_etapes).count() == 2
    assert ProjectStepItem.objects.filter(
        step__project=chantier_avec_etapes).count() == 4


def test_les_options_ne_sont_pas_partagees_avec_le_modele(
        chantier_avec_etapes):
    """Une liste JSON rendue telle quelle serait le MÊME objet Python.

    `options=point.options` sans copie ferait qu'ajouter un choix au modèle
    le ferait apparaître dans la copie en mémoire — et l'inverse.
    """
    from apps.btp.models import ProjectStepItem, ProjectTemplateItem

    source = ProjectTemplateItem.objects.get(label='Nature des murs')
    copie = ProjectStepItem.objects.get(
        step__project=chantier_avec_etapes, label='Nature des murs')
    assert copie.options == ['Placo', 'Béton']
    assert copie.options is not source.options


# ── 3. « False » est une réponse ────────────────────────────────────────────

def test_non_compte_comme_une_reponse(chantier_avec_etapes):
    """« Nacelle nécessaire : non » n'est pas un oubli."""
    from apps.btp.models import ProjectStepItem

    point = ProjectStepItem.objects.get(
        step__project=chantier_avec_etapes, label='Nacelle nécessaire ?')
    assert point.is_answered is False

    point.answer_boolean = False
    point.save()
    assert point.is_answered is True
    assert point.reponse_affichable == 'Non'


def test_zero_compte_comme_une_reponse(chantier_avec_etapes):
    """Une hauteur de 0 est absurde, mais c'est une SAISIE.

    `if not self.answer_number` la compterait comme manquante : même piège
    que le booléen, sur un autre type.
    """
    from apps.btp.models import ProjectStepItem

    point = ProjectStepItem.objects.get(
        step__project=chantier_avec_etapes, label='Hauteur sous plafond')
    point.answer_number = Decimal('0')
    point.save()
    assert point.is_answered is True


def test_un_texte_d_espaces_ne_compte_pas(chantier_avec_etapes):
    from apps.btp.models import ProjectStepItem

    point = ProjectStepItem.objects.create(
        step_id=ProjectStepItem.objects.filter(
            step__project=chantier_avec_etapes).first().step_id,
        label='Remarques', answer_type='text', order=99)
    point.answer_text = '   \n  '
    point.save()
    assert point.is_answered is False


def test_la_reponse_affichable_porte_l_unite(chantier_avec_etapes):
    from apps.btp.models import ProjectStepItem

    point = ProjectStepItem.objects.get(
        step__project=chantier_avec_etapes, label='Hauteur sous plafond')
    point.answer_number = Decimal('2.500')
    point.save()
    # 2.5 et non 2.500 : `normalize()` retire les zéros de queue, qui
    # viennent de `decimal_places=3` et non de la saisie.
    assert point.reponse_affichable == '2.5 m'


# ── 4. Avertir sans bloquer ─────────────────────────────────────────────────

def test_les_points_manquants_sont_listes(chantier_avec_etapes):
    from apps.btp import services_etapes as svc

    # Trois points obligatoires dans ce modèle.
    assert svc.compter_les_points_manquants(chantier_avec_etapes) == 3

    blocs = svc.points_manquants(chantier_avec_etapes)
    assert [b['etape'].name for b in blocs] == ['Analyse sur place',
                                                'Commande du matériel']


def test_un_point_facultatif_vide_n_est_pas_signale(chantier_avec_etapes):
    """« Nature des murs » n'est pas obligatoire : son absence est muette."""
    from apps.btp import services_etapes as svc

    manquants = []
    for bloc in svc.points_manquants(chantier_avec_etapes):
        manquants += [p.label for p in bloc['points']]
    assert 'Nature des murs' not in manquants


def test_enregistrer_une_etape_incomplete_reussit(connecte,
                                                  chantier_avec_etapes):
    """Le formulaire ENREGISTRE et avertit. Il ne refuse pas.

    C'est la décision prise : refuser ferait perdre le reste de la saisie et
    ferait inventer les réponses manquantes.
    """
    from apps.btp.models import ProjectPlanStep, ProjectStepItem

    etape = ProjectPlanStep.objects.get(
        project=chantier_avec_etapes, name='Analyse sur place')
    nacelle = ProjectStepItem.objects.get(step=etape,
                                          label='Nacelle nécessaire ?')

    donnees = {
        'name': etape.name, 'step_type': etape.step_type,
        'order': etape.order, 'status': 'in_progress',
        'progress_percent': 30,
        f'point_{nacelle.pk}': 'true',
        # « Hauteur sous plafond », obligatoire, laissée vide exprès.
    }
    reponse = connecte.post(reverse('btp:step_detail', args=[etape.pk]),
                            donnees)
    assert reponse.status_code == 302

    nacelle.refresh_from_db()
    etape.refresh_from_db()
    assert nacelle.answer_boolean is True
    assert etape.status == 'in_progress'


def test_l_avertissement_est_affiche_apres_enregistrement(
        connecte, chantier_avec_etapes):
    from apps.btp.models import ProjectPlanStep

    etape = ProjectPlanStep.objects.get(
        project=chantier_avec_etapes, name='Analyse sur place')
    reponse = connecte.post(
        reverse('btp:step_detail', args=[etape.pk]),
        {'name': etape.name, 'step_type': etape.step_type, 'order': 1,
         'status': 'pending', 'progress_percent': 0},
        follow=True)
    corps = reponse.content.decode('utf-8', 'replace')
    assert 'restent à' in corps or 'restent a' in corps


def test_le_compteur_d_oublis_est_sur_la_fiche_du_chantier(
        connecte, chantier_avec_etapes):
    """L'oubli se voit depuis la fiche, pas seulement dans la sous-page."""
    reponse = connecte.get(
        reverse('btp:project_detail', args=[chantier_avec_etapes.pk]))
    assert reponse.status_code == 200
    assert reponse.context['etapes_manquantes'] == 3


# ── 5. Les réponses typées, et ce qu'elles permettent ───────────────────────

def test_chaque_type_va_dans_sa_colonne(connecte, chantier_avec_etapes):
    from apps.btp.models import ProjectPlanStep, ProjectStepItem

    etape = ProjectPlanStep.objects.get(
        project=chantier_avec_etapes, name='Analyse sur place')
    points = {p.label: p for p in ProjectStepItem.objects.filter(step=etape)}

    connecte.post(reverse('btp:step_detail', args=[etape.pk]), {
        'name': etape.name, 'step_type': etape.step_type, 'order': 1,
        'status': 'pending', 'progress_percent': 0,
        f'point_{points["Nacelle nécessaire ?"].pk}': 'false',
        f'point_{points["Hauteur sous plafond"].pk}': '3.15',
        f'point_{points["Nature des murs"].pk}': 'Béton',
    })

    for point in points.values():
        point.refresh_from_db()
    assert points['Nacelle nécessaire ?'].answer_boolean is False
    assert points['Hauteur sous plafond'].answer_number == Decimal('3.150')
    assert points['Nature des murs'].answer_choice == 'Béton'
    # Les colonnes des autres types restent vides : aucune valeur ne traîne.
    assert points['Nacelle nécessaire ?'].answer_text == ''
    assert points['Hauteur sous plafond'].answer_boolean is None


def test_un_nombre_invalide_est_refuse(connecte, chantier_avec_etapes):
    """Le gain des colonnes typées : l'erreur est vue à la SAISIE."""
    from apps.btp.models import ProjectPlanStep, ProjectStepItem

    etape = ProjectPlanStep.objects.get(
        project=chantier_avec_etapes, name='Analyse sur place')
    hauteur = ProjectStepItem.objects.get(step=etape,
                                          label='Hauteur sous plafond')
    reponse = connecte.post(reverse('btp:step_detail', args=[etape.pk]), {
        'name': etape.name, 'step_type': etape.step_type, 'order': 1,
        'status': 'pending', 'progress_percent': 0,
        f'point_{hauteur.pk}': 'deux mètres et demi',
    })
    assert reponse.status_code == 200          # on reste sur le formulaire
    hauteur.refresh_from_db()
    assert hauteur.answer_number is None


def test_un_choix_hors_liste_est_refuse(connecte, chantier_avec_etapes):
    from apps.btp.models import ProjectPlanStep, ProjectStepItem

    etape = ProjectPlanStep.objects.get(
        project=chantier_avec_etapes, name='Analyse sur place')
    murs = ProjectStepItem.objects.get(step=etape, label='Nature des murs')
    reponse = connecte.post(reverse('btp:step_detail', args=[etape.pk]), {
        'name': etape.name, 'step_type': etape.step_type, 'order': 1,
        'status': 'pending', 'progress_percent': 0,
        f'point_{murs.pk}': 'Carton-pâte',
    })
    assert reponse.status_code == 200
    murs.refresh_from_db()
    assert murs.answer_choice == ''


def test_on_retrouve_les_chantiers_qui_demandent_une_nacelle(
        connecte, chantier_avec_etapes):
    """La raison d'être des colonnes typées, vérifiée en SQL."""
    from apps.btp.models import ProjectStepItem

    point = ProjectStepItem.objects.get(
        step__project=chantier_avec_etapes, label='Nacelle nécessaire ?')
    point.answer_boolean = True
    point.save()

    trouves = ProjectStepItem.objects.filter(
        label__icontains='nacelle', answer_boolean=True)
    assert [p.step.project.pk for p in trouves] == [chantier_avec_etapes.pk]

    reponse = connecte.get(reverse('btp:points_search'),
                           {'q': 'nacelle', 'reponse': 'oui'})
    assert reponse.status_code == 200
    assert chantier_avec_etapes.name in reponse.content.decode('utf-8',
                                                               'replace')


def test_la_recherche_vide_ne_renvoie_rien(connecte, chantier_avec_etapes):
    reponse = connecte.get(reverse('btp:points_search'))
    assert reponse.status_code == 200
    assert list(reponse.context['points']) == []


# ── 6. La création d'un chantier applique le modèle ─────────────────────────

def test_creer_un_chantier_avec_un_modele_cree_ses_etapes(connecte, modele,
                                                          client_crm):
    from apps.btp.models import BTPProject, ProjectPlanStep

    reponse = connecte.post(reverse('btp:project_create'), {
        'name': 'Chantier neuf', 'customer': client_crm.pk,
        'status': 'study', 'start_date': '2026-04-01',
        'estimated_budget': '0', 'retention_rate': '5',
        'template': modele.pk,
    })
    assert reponse.status_code == 302
    chantier = BTPProject.objects.get(name='Chantier neuf')
    assert ProjectPlanStep.objects.filter(project=chantier).count() == 2
    # On est renvoyé sur les étapes et non sur la fiche : c'est là que le
    # travail commence.
    assert reponse['Location'] == reverse('btp:project_planning',
                                          args=[chantier.pk])


def test_le_modele_par_defaut_est_preselectionne(connecte, modele):
    reponse = connecte.get(reverse('btp:project_create'))
    assert reponse.context['form'].initial.get('template') == modele.pk


def test_creer_un_chantier_sans_modele_marche_comme_avant(connecte,
                                                          client_crm):
    """La fonctionnalité est facultative : rien n'est cassé sans modèle."""
    from apps.btp.models import BTPProject, ProjectPlanStep

    reponse = connecte.post(reverse('btp:project_create'), {
        'name': 'Chantier nu', 'customer': client_crm.pk, 'status': 'study',
        'estimated_budget': '0', 'retention_rate': '5',
    })
    assert reponse.status_code == 302
    chantier = BTPProject.objects.get(name='Chantier nu')
    assert ProjectPlanStep.objects.filter(project=chantier).count() == 0


def test_le_champ_modele_disparait_en_modification(connecte, chantier,
                                                   modele):
    """Réappliquer un modèle sur un chantier en cours ne doit pas se faire
    par mégarde depuis le formulaire de modification."""
    reponse = connecte.get(reverse('btp:project_edit', args=[chantier.pk]))
    assert 'template' not in reponse.context['form'].fields


def test_un_modele_d_une_autre_entreprise_est_refuse(connecte,
                                                     autre_entreprise,
                                                     client_crm):
    """Le queryset est borné dans __init__, donc à la VALIDATION.

    Borné seulement à l'affichage, un identifiant recopié passerait — et
    les étapes d'une autre société se retrouveraient sur ce chantier.
    """
    from apps.btp.models import BTPProject, ProjectTemplate

    etranger = ProjectTemplate.objects.create(
        company=autre_entreprise, name='Modèle voisin')
    reponse = connecte.post(reverse('btp:project_create'), {
        'name': 'Chantier espion', 'customer': client_crm.pk,
        'status': 'study', 'estimated_budget': '0', 'retention_rate': '5',
        'template': etranger.pk,
    })
    assert reponse.status_code == 200
    assert 'template' in reponse.context['form'].errors
    assert not BTPProject.objects.filter(name='Chantier espion').exists()


def test_un_client_d_une_autre_entreprise_est_refuse(connecte,
                                                     autre_entreprise):
    """Même défaut, sur le champ qui existait déjà.

    Le queryset de `customer` n'était posé que dans la branche GET de la
    vue : au POST le formulaire était reconstruit sans filtre, et le
    chantier s'enregistrait sous l'entreprise courante au nom du client
    d'une autre société.
    """
    from apps.btp.models import BTPProject
    from apps.crm.models import Customer

    etranger = Customer.objects.create(company=autre_entreprise,
                                       name='Client du voisin')
    reponse = connecte.post(reverse('btp:project_create'), {
        'name': 'Chantier emprunte', 'customer': etranger.pk,
        'status': 'study', 'estimated_budget': '0', 'retention_rate': '5',
    })
    assert reponse.status_code == 200
    assert 'customer' in reponse.context['form'].errors
    assert not BTPProject.objects.filter(name='Chantier emprunte').exists()


# ── 7. Les écrans ───────────────────────────────────────────────────────────

@pytest.mark.parametrize('nom', [
    'btp:template_list', 'btp:template_create', 'btp:points_search',
])
def test_les_pages_sans_argument_repondent(connecte, nom):
    assert connecte.get(reverse(nom)).status_code == 200


def test_les_pages_du_modele_repondent(connecte, modele):
    from apps.btp.models import ProjectTemplateItem, ProjectTemplateStep

    etape = ProjectTemplateStep.objects.filter(template=modele).first()
    point = ProjectTemplateItem.objects.filter(step=etape).first()
    for nom, args in [
        ('btp:template_detail', [modele.pk]),
        ('btp:template_edit', [modele.pk]),
        ('btp:template_delete', [modele.pk]),
        ('btp:template_duplicate', [modele.pk]),
        ('btp:template_step_create', [modele.pk]),
        ('btp:template_step_edit', [etape.pk]),
        ('btp:template_item_create', [etape.pk]),
        ('btp:template_item_edit', [point.pk]),
    ]:
        reponse = connecte.get(reverse(nom, args=args))
        assert reponse.status_code == 200, f'{nom} → {reponse.status_code}'


def test_les_pages_du_chantier_repondent(connecte, chantier_avec_etapes):
    from apps.btp.models import ProjectPlanStep

    etape = ProjectPlanStep.objects.filter(
        project=chantier_avec_etapes).first()
    for nom, args in [
        ('btp:project_planning', [chantier_avec_etapes.pk]),
        ('btp:project_apply_template', [chantier_avec_etapes.pk]),
        ('btp:step_create', [chantier_avec_etapes.pk]),
        ('btp:step_detail', [etape.pk]),
    ]:
        reponse = connecte.get(reverse(nom, args=args))
        assert reponse.status_code == 200, f'{nom} → {reponse.status_code}'


def test_un_chantier_sans_etapes_affiche_l_invitation(connecte, chantier):
    reponse = connecte.get(reverse('btp:project_planning',
                                   args=[chantier.pk]))
    corps = reponse.content.decode('utf-8', 'replace')
    assert 'pas encore d' in corps


def test_une_etape_sans_point_ne_divise_pas_par_zero(connecte, chantier):
    """`pourcentage` sur une étape vide : 100 et non une ZeroDivisionError."""
    from apps.btp.models import ProjectPlanStep

    ProjectPlanStep.objects.create(project=chantier, name='Étape nue',
                                   order=1)
    reponse = connecte.get(reverse('btp:project_planning',
                                   args=[chantier.pk]))
    assert reponse.status_code == 200
    assert reponse.context['lignes'][0]['pourcentage'] == 100


# ── 8. Écrire un modèle depuis l'interface ──────────────────────────────────

def test_creer_un_modele(connecte, entreprise):
    from apps.btp.models import ProjectTemplate

    reponse = connecte.post(reverse('btp:template_create'), {
        'name': 'Plomberie', 'description': 'Essai', 'is_active': 'on'})
    assert reponse.status_code == 302
    assert ProjectTemplate.objects.filter(company=entreprise,
                                          name='Plomberie').exists()


def test_un_nom_en_double_est_refuse_proprement(connecte, modele):
    """Et non en IntegrityError : `company` n'est pas un champ du formulaire,
    donc Django ne peut pas valider `unique_together` lui-même."""
    reponse = connecte.post(reverse('btp:template_create'),
                            {'name': 'Électricité', 'is_active': 'on'})
    assert reponse.status_code == 200
    assert 'name' in reponse.context['form'].errors


def test_la_casse_ne_suffit_pas_a_distinguer_deux_modeles(connecte,
                                                          entreprise):
    """« Plomberie » et « PLOMBERIE » sont le même modèle pour un humain.

    Le test porte sur un nom purement ASCII, et c'est délibéré : `iexact`
    sur SQLite n'est insensible à la casse que pour l'ASCII — « É » et
    « é » y restent distincts. Affirmer le contraire ferait un test qui
    passe sur PostgreSQL et échoue ici, ou l'inverse.
    """
    from apps.btp.models import ProjectTemplate

    ProjectTemplate.objects.create(company=entreprise, name='Plomberie')
    reponse = connecte.post(reverse('btp:template_create'),
                            {'name': 'PLOMBERIE', 'is_active': 'on'})
    assert reponse.status_code == 200
    assert 'name' in reponse.context['form'].errors


def test_un_seul_modele_par_defaut_par_entreprise(connecte, entreprise,
                                                  modele):
    from apps.btp.models import ProjectTemplate

    connecte.post(reverse('btp:template_create'),
                  {'name': 'Plomberie', 'is_active': 'on',
                   'is_default': 'on'})
    defauts = ProjectTemplate.objects.filter(company=entreprise,
                                             is_default=True)
    assert defauts.count() == 1
    assert defauts.first().name == 'Plomberie'


def test_les_options_se_saisissent_en_lignes(connecte, modele):
    """Et non en JSON : on ne demande pas d'écrire `["Oui", "Non"]`."""
    from apps.btp.models import ProjectTemplateItem, ProjectTemplateStep

    etape = ProjectTemplateStep.objects.filter(template=modele).first()
    connecte.post(reverse('btp:template_item_create', args=[etape.pk]), {
        'label': 'État du sol', 'answer_type': 'choice', 'order': 9,
        'options_saisies': 'Carrelage\nParquet\n\n  Béton brut  \n'})
    point = ProjectTemplateItem.objects.get(label='État du sol')
    assert point.options == ['Carrelage', 'Parquet', 'Béton brut']


def test_une_liste_a_un_seul_choix_est_refusee(connecte, modele):
    from apps.btp.models import ProjectTemplateStep

    etape = ProjectTemplateStep.objects.filter(template=modele).first()
    reponse = connecte.post(
        reverse('btp:template_item_create', args=[etape.pk]),
        {'label': 'Unique', 'answer_type': 'choice', 'order': 9,
         'options_saisies': 'Seul choix'})
    assert reponse.status_code == 200
    assert 'options_saisies' in reponse.context['form'].errors


def test_monter_une_etape_change_son_rang(connecte, modele):
    from apps.btp.models import ProjectTemplateStep

    seconde = ProjectTemplateStep.objects.get(template=modele,
                                              name='Commande du matériel')
    connecte.post(reverse('btp:template_step_move', args=[seconde.pk]),
                  {'sens': 'haut'})
    ordres = list(ProjectTemplateStep.objects.filter(template=modele)
                  .order_by('order', 'pk').values_list('name', flat=True))
    assert ordres[0] == 'Commande du matériel'


def test_monter_la_premiere_etape_ne_casse_rien(connecte, modele):
    from apps.btp.models import ProjectTemplateStep

    premiere = ProjectTemplateStep.objects.get(template=modele,
                                               name='Analyse sur place')
    reponse = connecte.post(
        reverse('btp:template_step_move', args=[premiere.pk]),
        {'sens': 'haut'})
    assert reponse.status_code == 302
    ordres = list(ProjectTemplateStep.objects.filter(template=modele)
                  .order_by('order', 'pk').values_list('name', flat=True))
    assert ordres[0] == 'Analyse sur place'


def test_dupliquer_un_modele_recopie_tout(connecte, entreprise, modele):
    from apps.btp.models import ProjectTemplate, ProjectTemplateItem

    connecte.post(reverse('btp:template_duplicate', args=[modele.pk]))
    copie = ProjectTemplate.objects.get(company=entreprise,
                                        name='Copie de Électricité')
    assert copie.steps.count() == 2
    assert ProjectTemplateItem.objects.filter(step__template=copie).count() == 4
    # La copie n'usurpe pas le statut « par défaut » de l'original.
    assert copie.is_default is False


def test_dupliquer_deux_fois_ne_leve_pas(connecte, entreprise, modele):
    """`unique_together ['company', 'name']` refuserait « Copie de X » deux
    fois : le nom est rendu libre."""
    from apps.btp.models import ProjectTemplate

    connecte.post(reverse('btp:template_duplicate', args=[modele.pk]))
    reponse = connecte.post(reverse('btp:template_duplicate',
                                    args=[modele.pk]))
    assert reponse.status_code == 302
    assert ProjectTemplate.objects.filter(
        company=entreprise, name__startswith='Copie de').count() == 2


def test_supprimer_un_modele(connecte, modele):
    from apps.btp.models import ProjectTemplate

    reponse = connecte.post(reverse('btp:template_delete', args=[modele.pk]))
    assert reponse.status_code == 302
    assert not ProjectTemplate.objects.filter(pk=modele.pk).exists()


# ── 9. Le modèle prêt à l'emploi, installé d'un bouton ──────────────────────

def test_installer_le_modele_electricite(connecte, entreprise):
    """Pas de commande à taper : la contrainte du projet est que tout se
    pilote depuis l'interface."""
    from apps.btp.models import ProjectTemplate, ProjectTemplateItem

    reponse = connecte.post(reverse('btp:template_install_starter'),
                            {'cle': 'electricite'})
    assert reponse.status_code == 302
    modele = ProjectTemplate.objects.get(company=entreprise)
    assert modele.steps.count() == 11
    assert ProjectTemplateItem.objects.filter(
        step__template=modele).count() > 40
    assert modele.is_default is True


def test_le_modele_pret_contient_les_questions_qui_comptent(connecte,
                                                            entreprise):
    """Celles que l'on découvre trop tard : accès, nacelle, hauteur."""
    from apps.btp.models import ProjectTemplateItem

    connecte.post(reverse('btp:template_install_starter'),
                  {'cle': 'electricite'})
    libelles = ' | '.join(
        ProjectTemplateItem.objects.filter(
            step__template__company=entreprise).values_list('label',
                                                            flat=True))
    for attendu in ['camionnette', 'nacelle', 'Hauteur sous plafond',
                    'amiante', 'livraison']:
        assert attendu in libelles, attendu


def test_installer_deux_fois_n_ecrase_pas_le_premier(connecte, entreprise):
    """Le travail de l'utilisateur compte plus que notre version d'origine."""
    from apps.btp.models import ProjectTemplate

    connecte.post(reverse('btp:template_install_starter'),
                  {'cle': 'electricite'})
    premier = ProjectTemplate.objects.get(company=entreprise)
    premier.name = 'Électricité — à ma sauce'
    premier.save()

    connecte.post(reverse('btp:template_install_starter'),
                  {'cle': 'electricite'})
    assert ProjectTemplate.objects.filter(company=entreprise).count() == 2
    premier.refresh_from_db()
    assert premier.name == 'Électricité — à ma sauce'
    # Et le second n'usurpe pas le « par défaut » du premier.
    assert ProjectTemplate.objects.filter(company=entreprise,
                                          is_default=True).count() == 1


def test_une_cle_inconnue_est_refusee(connecte, entreprise):
    from apps.btp.models import ProjectTemplate

    reponse = connecte.post(reverse('btp:template_install_starter'),
                            {'cle': '../../etc/passwd'})
    assert reponse.status_code == 302
    assert not ProjectTemplate.objects.filter(company=entreprise).exists()


def test_tous_les_types_du_catalogue_sont_connus():
    """Une faute de frappe dans `modeles_prets` donnerait un point
    inutilisable, sans que rien ne le signale."""
    from apps.btp.models import ANSWER_TYPE_CHOICES, ProjectPlanStep
    from apps.btp.modeles_prets import CATALOGUE_DES_MODELES

    types_reponse = {code for code, _ in ANSWER_TYPE_CHOICES}
    types_etape = {code for code, _ in ProjectPlanStep.STEP_TYPE_CHOICES}

    for modele in CATALOGUE_DES_MODELES.values():
        for etape in modele['etapes']:
            assert etape['type'] in types_etape, etape['type']
            for point in etape['points']:
                libelle, type_reponse, _, _, options, _ = point
                assert type_reponse in types_reponse, libelle
                if type_reponse == 'choice':
                    assert len(options) >= 2, libelle
                else:
                    assert options == [], libelle


# ── 10. Isolation multi-entreprises ─────────────────────────────────────────

@pytest.fixture
def objets_du_voisin(autre_entreprise):
    """Un modèle, une étape, un point et un chantier chez le voisin."""
    from apps.btp.models import (
        BTPProject, ProjectPlanStep, ProjectStepItem, ProjectTemplate,
        ProjectTemplateItem, ProjectTemplateStep)
    from apps.crm.models import Customer

    gabarit = ProjectTemplate.objects.create(company=autre_entreprise,
                                             name='Chez le voisin')
    etape_modele = ProjectTemplateStep.objects.create(
        template=gabarit, name='Étape voisine', order=1)
    point_modele = ProjectTemplateItem.objects.create(
        step=etape_modele, label='Question voisine', order=1)

    acheteur = Customer.objects.create(company=autre_entreprise,
                                       name='Client voisin')
    projet = BTPProject.objects.create(company=autre_entreprise,
                                       name='Chantier voisin',
                                       customer=acheteur)
    etape = ProjectPlanStep.objects.create(project=projet,
                                           name='Étape de chantier voisine',
                                           order=1)
    point = ProjectStepItem.objects.create(step=etape, label='Point voisin',
                                           order=1)

    return {'modele': gabarit, 'etape_modele': etape_modele,
            'point_modele': point_modele, 'projet': projet, 'etape': etape,
            'point': point}


@pytest.mark.parametrize('nom,cle', [
    ('btp:template_detail', 'modele'),
    ('btp:template_edit', 'modele'),
    ('btp:template_delete', 'modele'),
    ('btp:template_duplicate', 'modele'),
    ('btp:template_step_create', 'modele'),
    ('btp:template_step_edit', 'etape_modele'),
    ('btp:template_item_create', 'etape_modele'),
    ('btp:template_item_edit', 'point_modele'),
    ('btp:project_planning', 'projet'),
    ('btp:project_apply_template', 'projet'),
    ('btp:step_create', 'projet'),
    ('btp:step_detail', 'etape'),
    ('btp:step_item_photo', 'point'),
])
def test_les_objets_du_voisin_sont_introuvables(connecte, objets_du_voisin,
                                                nom, cle):
    reponse = connecte.get(reverse(nom, args=[objets_du_voisin[cle].pk]))
    assert reponse.status_code == 404, f'{nom} → {reponse.status_code}'


@pytest.mark.parametrize('nom,cle', [
    ('btp:template_step_delete', 'etape_modele'),
    ('btp:template_step_move', 'etape_modele'),
    ('btp:template_item_delete', 'point_modele'),
    ('btp:step_delete', 'etape'),
])
def test_les_suppressions_chez_le_voisin_sont_refusees(connecte,
                                                       objets_du_voisin,
                                                       nom, cle):
    reponse = connecte.post(reverse(nom, args=[objets_du_voisin[cle].pk]),
                            {'sens': 'haut'})
    assert reponse.status_code == 404, f'{nom} → {reponse.status_code}'


def test_la_recherche_ne_voit_pas_les_points_du_voisin(connecte,
                                                       objets_du_voisin):
    reponse = connecte.get(reverse('btp:points_search'), {'q': 'voisin'})
    assert list(reponse.context['points']) == []


def test_les_modeles_du_voisin_ne_sont_pas_proposes(connecte,
                                                    objets_du_voisin,
                                                    chantier):
    reponse = connecte.get(reverse('btp:project_apply_template',
                                   args=[chantier.pk]))
    choix = reponse.context['form'].fields['template'].queryset
    assert objets_du_voisin['modele'] not in choix


def test_appliquer_un_modele_du_voisin_est_refuse(connecte, objets_du_voisin,
                                                  chantier):
    from apps.btp.models import ProjectPlanStep

    reponse = connecte.post(
        reverse('btp:project_apply_template', args=[chantier.pk]),
        {'template': objets_du_voisin['modele'].pk})
    assert reponse.status_code == 200
    assert 'template' in reponse.context['form'].errors
    assert ProjectPlanStep.objects.filter(project=chantier).count() == 0


# ── 11. Les photos ne passent pas par /media/ ───────────────────────────────

def test_le_prefixe_des_photos_est_refuse_par_media():
    """Une photo de local technique montre l'intérieur de chez un client, et
    son chemin est devinable. Le refus est explicite et non implicite."""
    from apps.core.media_access import (
        PREFIXES_INTERDITS, niveau_requis, peut_lire, raison_du_refus)

    assert 'btp/checklists/' in PREFIXES_INTERDITS
    assert 'step_item_photo' in raison_du_refus('btp/checklists/photo.jpg')

    # Et le refus PORTE : pas seulement une entrée dans un dictionnaire.
    # Même pour un salarié connecté — c'est tout l'intérêt, le contrôle
    # appartient à une vue qui sait remonter jusqu'à l'entreprise.
    assert niveau_requis('btp/checklists/photo.jpg') == 'interdit'

    class Connecte:
        is_authenticated = True

    assert peut_lire(Connecte(), 'btp/checklists/photo.jpg') is False


def test_un_point_sans_photo_rend_404(connecte, chantier_avec_etapes):
    from apps.btp.models import ProjectStepItem

    point = ProjectStepItem.objects.filter(
        step__project=chantier_avec_etapes).first()
    reponse = connecte.get(reverse('btp:step_item_photo', args=[point.pk]))
    assert reponse.status_code == 404


def test_deposer_une_photo_puis_la_relire(connecte, chantier_avec_etapes,
                                          tmp_path, settings):
    from io import BytesIO

    from django.core.files.uploadedfile import SimpleUploadedFile

    from apps.btp.models import (
        ProjectPlanStep, ProjectStepItem, ProjectTemplateItem)

    settings.MEDIA_ROOT = str(tmp_path)

    etape = ProjectPlanStep.objects.get(
        project=chantier_avec_etapes, name='Analyse sur place')
    point = ProjectStepItem.objects.create(
        step=etape, label='Photo du tableau', answer_type='photo', order=50)

    # Un PNG 1×1 réel : ImageField ouvre le fichier avec Pillow, et refuse
    # des octets qui ne sont pas une image.
    from PIL import Image
    tampon = BytesIO()
    Image.new('RGB', (1, 1), 'white').save(tampon, format='PNG')
    fichier = SimpleUploadedFile('tableau.png', tampon.getvalue(),
                                 content_type='image/png')

    reponse = connecte.post(reverse('btp:step_detail', args=[etape.pk]), {
        'name': etape.name, 'step_type': etape.step_type, 'order': 1,
        'status': 'pending', 'progress_percent': 0,
        f'point_{point.pk}': fichier,
    })
    assert reponse.status_code == 302

    point.refresh_from_db()
    assert point.answer_photo
    assert point.answer_photo.name.startswith('btp/checklists/')
    assert point.is_answered is True

    lecture = connecte.get(reverse('btp:step_item_photo', args=[point.pk]))
    assert lecture.status_code == 200
    # Une image peut s'afficher dans la page ; un SVG repartirait en
    # téléchargement, il n'est pas dans TYPES_AFFICHABLES.
    assert lecture['Content-Type'] == 'image/png'
    assert lecture['Content-Disposition'].startswith('inline')


# ── 12. Traçabilité de la saisie ────────────────────────────────────────────

def test_qui_a_repondu_et_quand(connecte, chantier_avec_etapes):
    from apps.btp.models import ProjectPlanStep, ProjectStepItem

    etape = ProjectPlanStep.objects.get(
        project=chantier_avec_etapes, name='Analyse sur place')
    point = ProjectStepItem.objects.get(step=etape,
                                        label='Nacelle nécessaire ?')
    connecte.post(reverse('btp:step_detail', args=[etape.pk]), {
        'name': etape.name, 'step_type': etape.step_type, 'order': 1,
        'status': 'pending', 'progress_percent': 0,
        f'point_{point.pk}': 'true',
        f'commentaire_{point.pk}': 'Toit à 6 m, pas d’accès par l’intérieur.',
    })
    point.refresh_from_db()
    assert point.filled_by == connecte.user
    assert point.filled_at is not None
    assert 'Toit à 6 m' in point.comment


def test_effacer_une_reponse_efface_sa_tracabilite(connecte,
                                                   chantier_avec_etapes):
    """Sinon « rempli le 3 mars par Untel » reste affiché sur une case vide."""
    from apps.btp.models import ProjectPlanStep, ProjectStepItem

    etape = ProjectPlanStep.objects.get(
        project=chantier_avec_etapes, name='Analyse sur place')
    point = ProjectStepItem.objects.get(step=etape,
                                        label='Nacelle nécessaire ?')
    base = {'name': etape.name, 'step_type': etape.step_type, 'order': 1,
            'status': 'pending', 'progress_percent': 0}

    connecte.post(reverse('btp:step_detail', args=[etape.pk]),
                  {**base, f'point_{point.pk}': 'true'})
    connecte.post(reverse('btp:step_detail', args=[etape.pk]),
                  {**base, f'point_{point.pk}': ''})

    point.refresh_from_db()
    assert point.answer_boolean is None
    assert point.filled_by is None
    assert point.filled_at is None


def test_les_pages_exigent_une_connexion(client, chantier_avec_etapes):
    reponse = client.get(reverse('btp:project_planning',
                                 args=[chantier_avec_etapes.pk]))
    assert reponse.status_code == 302
    assert '/login' in reponse['Location'] or 'connexion' in reponse['Location']


def test_effacer_une_photo_la_retire(connecte, chantier_avec_etapes,
                                     tmp_path, settings):
    """La case « effacer » du champ fichier doit effacer.

    `ClearableFileInput` rend TROIS valeurs : None (rien envoye, on garde),
    False (case cochee, on retire) et un fichier. Un `if valeur:` traite
    False comme None et la case n'efface rien -- sans message, donc sans
    qu'on comprenne pourquoi.
    """
    from io import BytesIO

    from django.core.files.uploadedfile import SimpleUploadedFile
    from PIL import Image

    from apps.btp.models import ProjectPlanStep, ProjectStepItem

    settings.MEDIA_ROOT = str(tmp_path)

    etape = ProjectPlanStep.objects.get(
        project=chantier_avec_etapes, name='Analyse sur place')
    point = ProjectStepItem.objects.create(
        step=etape, label='Photo a effacer', answer_type='photo', order=51)

    tampon = BytesIO()
    Image.new('RGB', (1, 1), 'white').save(tampon, format='PNG')
    base = {'name': etape.name, 'step_type': etape.step_type, 'order': 1,
            'status': 'pending', 'progress_percent': 0}

    connecte.post(reverse('btp:step_detail', args=[etape.pk]), {
        **base,
        f'point_{point.pk}': SimpleUploadedFile(
            'avant.png', tampon.getvalue(), content_type='image/png'),
    })
    point.refresh_from_db()
    assert point.answer_photo

    # Un POST sans le fichier ne doit RIEN changer : c'est le cas courant,
    # on revient corriger une autre reponse de la meme etape.
    connecte.post(reverse('btp:step_detail', args=[etape.pk]), base)
    point.refresh_from_db()
    assert point.answer_photo, 'un POST sans fichier a efface la photo'

    # La case « effacer », elle, efface.
    connecte.post(reverse('btp:step_detail', args=[etape.pk]),
                  {**base, f'point_{point.pk}-clear': 'on'})
    point.refresh_from_db()
    assert not point.answer_photo
    assert point.is_answered is False
    assert point.filled_at is None


def test_descendre_une_etape_quand_les_rangs_sont_egaux(connecte, modele):
    """Deux etapes de meme rang : descendre doit quand meme descendre.

    Rien n'interdit deux `order` identiques -- un modele importe ou
    duplique en produit -- et le tri retombe alors sur « pk ».
    `max(0, voisine.order - 1)` vaut 0 quand les deux valent 0 : l'etape ne
    descendait jamais.
    """
    from apps.btp.models import ProjectTemplateStep

    ProjectTemplateStep.objects.filter(template=modele).update(order=0)
    premiere = ProjectTemplateStep.objects.filter(
        template=modele).order_by('order', 'pk').first()

    connecte.post(reverse('btp:template_step_move', args=[premiere.pk]),
                  {'sens': 'bas'})
    ordre = list(ProjectTemplateStep.objects.filter(template=modele)
                 .order_by('order', 'pk').values_list('pk', flat=True))
    assert ordre[-1] == premiere.pk


def test_le_selecteur_de_modele_est_visible_a_la_creation(connecte, modele):
    """Le gabarit nomme ses champs un par un.

    Un champ ajoute au formulaire et pas au gabarit n'apparait NULLE PART a
    l'ecran : le formulaire l'accepte au POST, et aucun utilisateur ne peut
    s'en servir. Verifie donc sur le HTML rendu, et non sur `form.fields`.
    """
    corps = connecte.get(reverse('btp:project_create')).content.decode(
        'utf-8', 'replace')
    assert 'name="template"' in corps
    assert modele.name in corps


def test_le_selecteur_de_modele_est_absent_en_modification(connecte,
                                                           chantier, modele):
    corps = connecte.get(
        reverse('btp:project_edit', args=[chantier.pk])).content.decode(
            'utf-8', 'replace')
    assert 'name="template"' not in corps


def test_la_date_de_saisie_ne_bouge_pas_sans_changement(connecte,
                                                        chantier_avec_etapes):
    """« Rempli le » doit dire quand l'information a ete relevee.

    Le formulaire poste les cinquante points de l'etape a chaque
    enregistrement, touches ou non. Horodater sans comparer ferait dire
    « rempli aujourd'hui » a une reponse de mars des qu'on revient corriger
    un autre point.
    """
    from apps.btp.models import ProjectPlanStep, ProjectStepItem

    etape = ProjectPlanStep.objects.get(
        project=chantier_avec_etapes, name='Analyse sur place')
    nacelle = ProjectStepItem.objects.get(step=etape,
                                          label='Nacelle nécessaire ?')
    hauteur = ProjectStepItem.objects.get(step=etape,
                                          label='Hauteur sous plafond')
    base = {'name': etape.name, 'step_type': etape.step_type, 'order': 1,
            'status': 'pending', 'progress_percent': 0}

    connecte.post(reverse('btp:step_detail', args=[etape.pk]),
                  {**base, f'point_{nacelle.pk}': 'true'})
    nacelle.refresh_from_db()
    premiere_saisie = nacelle.filled_at
    assert premiere_saisie is not None

    # On revient renseigner la HAUTEUR, sans toucher a la nacelle.
    connecte.post(reverse('btp:step_detail', args=[etape.pk]),
                  {**base, f'point_{nacelle.pk}': 'true',
                   f'point_{hauteur.pk}': '2.4'})
    nacelle.refresh_from_db()
    hauteur.refresh_from_db()
    assert nacelle.filled_at == premiere_saisie, (
        'la date de la nacelle a bouge alors que sa reponse n a pas change')
    assert hauteur.filled_at is not None

    # Et changer vraiment la reponse, lui, horodate.
    connecte.post(reverse('btp:step_detail', args=[etape.pk]),
                  {**base, f'point_{nacelle.pk}': 'false',
                   f'point_{hauteur.pk}': '2.4'})
    nacelle.refresh_from_db()
    assert nacelle.filled_at > premiere_saisie


# ── 13. Le modèle Étanchéité ────────────────────────────────────────────────
#
# Le métier où la surprise coûte le plus cher : ce qu'il y a SOUS l'ancienne
# étanchéité ne se voit qu'au sondage. Découvert une fois le toit ouvert, il
# se paie en travaux supplémentaires qu'on n'a pas annoncés — ou qu'on ne
# facture pas.
#
# Ces tests ne vérifient pas « un modèle existe ». Ils vérifient que les
# questions SANS LESQUELLES le chantier dérape y sont, nommément. Une
# refonte du catalogue qui en perdrait une doit échouer ici.

def test_installer_le_modele_etancheite(connecte, entreprise):
    from apps.btp.models import ProjectTemplate, ProjectTemplateItem

    reponse = connecte.post(reverse('btp:template_install_starter'),
                            {'cle': 'etancheite'})
    assert reponse.status_code == 302

    modele = ProjectTemplate.objects.get(company=entreprise)
    assert modele.steps.count() == 12
    points = ProjectTemplateItem.objects.filter(step__template=modele)
    assert points.count() > 100
    # Il est fait pour « combler tous les potentiels problèmes » : la
    # majorite des points doit etre marquee importante, sinon
    # l'avertissement ne porte sur rien.
    assert points.filter(is_required=True).count() > 80


@pytest.mark.parametrize('attendu', [
    # Ce qui ne se sait qu'avant d'ouvrir le toit
    'sondage ou carottage',
    'Amiante suspect',
    'Diagnostic amiante fourni',
    'étanchéité existante',
    'Nombre de couches en place',
    'isolation existante',
    # La pente et l'eau
    'Pente du toit',
    'zones de stagnation',
    'vacuations d',
    'trop-pleins',
    # Les relevés, premier poste de fuite
    'Hauteur des rel',
    'acrot',
    'travers',
    # L'accès et la logistique
    'Monte-mat',
    'Nacelle n',
    'Accès camion',
    'Benne possible',
    # La sécurité et le feu
    'point chaud',
    'Permis de feu',
    'Ronde de surveillance',
    # Ce qui sauve le logement du dessous
    'hes de secours',
    'trois jours à venir',
    'a-t-il sous la toiture',
    # Le support, moment de vérité
    'support est-il SEC',
    'tat du support apr',
    'Travaux suppl',
    # La preuve
    'Mise en eau r',
    'sultat de la mise en eau',
    # L'après
    'Carnet d',
    'Attestation de garantie',
])
def test_le_modele_etancheite_couvre_les_pieges_du_metier(connecte,
                                                          entreprise,
                                                          attendu):
    """Chaque libelle manquant est une surprise de chantier en puissance."""
    from apps.btp.models import ProjectTemplateItem

    connecte.post(reverse('btp:template_install_starter'),
                  {'cle': 'etancheite'})
    libelles = ' | '.join(
        ProjectTemplateItem.objects.filter(
            step__template__company=entreprise).values_list('label',
                                                            flat=True))
    aides = ' | '.join(
        ProjectTemplateItem.objects.filter(
            step__template__company=entreprise).values_list('help_text',
                                                            flat=True))
    assert attendu in libelles or attendu in aides, attendu


def test_l_etancheite_prepare_tout_avant_le_debut_des_travaux(connecte,
                                                              entreprise):
    """Le createur du chantier doit pouvoir TOUT remplir avant le demarrage.

    Les etapes de preparation portent donc un decalage NEGATIF -- analyse,
    autorisations, devis, commande -- et le gros des points importants est
    dans celles-la. Un modele qui mettrait ces questions apres le debut des
    travaux les ferait decouvrir trop tard, ce qui est exactement le
    probleme a resoudre.
    """
    from apps.btp.models import ProjectTemplateItem, ProjectTemplateStep

    connecte.post(reverse('btp:template_install_starter'),
                  {'cle': 'etancheite'})

    avant = ProjectTemplateStep.objects.filter(
        template__company=entreprise, offset_days__lt=0)
    assert avant.count() >= 6

    importants_avant = ProjectTemplateItem.objects.filter(
        step__in=avant, is_required=True).count()
    importants_total = ProjectTemplateItem.objects.filter(
        step__template__company=entreprise, is_required=True).count()
    assert importants_avant > importants_total / 2, (
        'le gros des points importants doit se remplir AVANT le demarrage')


def test_les_etapes_de_preparation_sont_datees_avant_le_debut(connecte,
                                                              client_crm):
    """Un decalage negatif doit donner une date ANTERIEURE au debut."""
    from apps.btp.models import BTPProject, ProjectPlanStep, ProjectTemplate

    connecte.post(reverse('btp:template_install_starter'),
                  {'cle': 'etancheite'})
    modele = ProjectTemplate.objects.get()

    connecte.post(reverse('btp:project_create'), {
        'name': 'Toiture Durand', 'customer': client_crm.pk,
        'status': 'study', 'start_date': '2026-06-15',
        'estimated_budget': '0', 'retention_rate': '5',
        'template': modele.pk,
    })
    chantier = BTPProject.objects.get(name='Toiture Durand')

    analyse = ProjectPlanStep.objects.filter(
        project=chantier, step_type='technical_visit').order_by('order').first()
    assert analyse.planned_date == date(2026, 5, 25)   # 15 juin moins 21 j

    demarrage = ProjectPlanStep.objects.get(project=chantier,
                                            step_type='work_start')
    assert demarrage.planned_date == date(2026, 6, 15)
    assert analyse.planned_date < demarrage.planned_date


# ── 14. Les modèles prêts restent atteignables ──────────────────────────────

def test_les_deux_modeles_prets_sont_proposes(connecte):
    """Et pas seulement quand la page est vide.

    Reserves a l'etat vide, ils devenaient inatteignables des le premier
    modele cree : on installe l'electricite en janvier et l'etancheite en
    mars. Verifie sur le HTML rendu.
    """
    corps = connecte.get(reverse('btp:template_list')).content.decode(
        'utf-8', 'replace')
    assert 'value="electricite"' in corps
    assert 'value="etancheite"' in corps


def test_ils_restent_proposes_quand_un_modele_existe_deja(connecte, modele):
    corps = connecte.get(reverse('btp:template_list')).content.decode(
        'utf-8', 'replace')
    assert 'value="etancheite"' in corps
    assert modele.name in corps


def test_installer_les_deux_metiers(connecte, entreprise):
    """Une entreprise fait les deux : les modeles cohabitent."""
    from apps.btp.models import ProjectTemplate

    connecte.post(reverse('btp:template_install_starter'),
                  {'cle': 'electricite'})
    connecte.post(reverse('btp:template_install_starter'),
                  {'cle': 'etancheite'})

    modeles = ProjectTemplate.objects.filter(company=entreprise)
    assert modeles.count() == 2
    # Un seul par defaut : le second ne demet pas le premier.
    assert modeles.filter(is_default=True).count() == 1


def test_les_compteurs_affiches_viennent_du_catalogue(connecte):
    """Ecrits a la main, ils vieilliraient en silence."""
    from apps.btp.modeles_prets import (
        CATALOGUE_DES_MODELES, catalogue_pour_affichage)

    affiche = {ligne['cle']: ligne for ligne in catalogue_pour_affichage()}
    assert set(affiche) == set(CATALOGUE_DES_MODELES)

    for cle, modele in CATALOGUE_DES_MODELES.items():
        etapes = modele['etapes']
        points = [p for e in etapes for p in e['points']]
        assert affiche[cle]['nombre_d_etapes'] == len(etapes)
        assert affiche[cle]['nombre_de_points'] == len(points)
        assert affiche[cle]['nombre_d_importants'] == sum(
            1 for p in points if p[2])

    reponse = connecte.get(reverse('btp:template_list'))
    assert reponse.status_code == 200
    assert len(reponse.context['catalogue']) == len(CATALOGUE_DES_MODELES)


def test_aucun_libelle_du_catalogue_ne_depasse_sa_colonne():
    """Un libelle trop long leverait a l'installation, pas a l'ecriture.

    Les colonnes sont a 250, 250 et 20 caracteres. Une question redigee un
    peu longuement passe la relecture et casse le bouton d'installation.
    """
    from apps.btp.modeles_prets import CATALOGUE_DES_MODELES

    for cle, modele in CATALOGUE_DES_MODELES.items():
        assert len(modele['nom']) <= 150, cle
        for etape in modele['etapes']:
            assert len(etape['nom']) <= 200, etape['nom']
            for libelle, _, _, unite, options, aide in etape['points']:
                assert len(libelle) <= 250, libelle
                assert len(aide) <= 250, libelle
                assert len(unite) <= 20, libelle
                for option in options:
                    assert len(option) <= 250, option


# ── 15. Tout remplir en une page ────────────────────────────────────────────
#
# Le créateur du chantier remplit les détails AVANT le démarrage : c'est la
# façon de travailler voulue. Le modèle Étanchéité compte 143 points sur
# douze étapes, et lui faire ouvrir douze pages travaille contre lui — on
# abandonne à la cinquième, et les questions qui restent sont justement
# celles qu'on voulait ne pas oublier.

def test_la_page_tout_remplir_montre_tous_les_points(connecte,
                                                     chantier_avec_etapes):
    reponse = connecte.get(reverse('btp:project_fill_all',
                                   args=[chantier_avec_etapes.pk]))
    assert reponse.status_code == 200
    # Les deux étapes du modèle, et leurs quatre points.
    assert len(reponse.context['blocs']) == 2
    assert reponse.context['total'] == 4
    assert reponse.context['remplis'] == 0

    corps = reponse.content.decode('utf-8', 'replace')
    for libelle in ['Nacelle nécessaire ?', 'Hauteur sous plafond',
                    'Nature des murs', 'Date de livraison annoncée']:
        assert libelle in corps, libelle


def test_un_seul_envoi_remplit_toutes_les_etapes(connecte,
                                                 chantier_avec_etapes):
    """Le point du fichier : une étape 1 et une étape 2 dans le même POST.

    C'est possible parce que les champs sont nommés « point_<pk> » : la clé
    primaire est unique sur toute la base, donc deux étapes ne peuvent pas
    se marcher dessus.
    """
    from apps.btp.models import ProjectStepItem

    points = {p.label: p for p in ProjectStepItem.objects.filter(
        step__project=chantier_avec_etapes)}

    reponse = connecte.post(
        reverse('btp:project_fill_all', args=[chantier_avec_etapes.pk]), {
            f'point_{points["Nacelle nécessaire ?"].pk}': 'true',
            f'point_{points["Hauteur sous plafond"].pk}': '2.8',
            f'point_{points["Nature des murs"].pk}': 'Placo',
            f'point_{points["Date de livraison annoncée"].pk}': '2026-03-01',
        })
    assert reponse.status_code == 302

    for point in points.values():
        point.refresh_from_db()
    assert points['Nacelle nécessaire ?'].answer_boolean is True
    assert str(points['Hauteur sous plafond'].answer_number) == '2.800'
    assert points['Nature des murs'].answer_choice == 'Placo'
    assert points['Date de livraison annoncée'].answer_date == date(2026, 3, 1)

    # Les deux étapes sont touchées, pas seulement la première.
    assert all(p.is_answered for p in points.values())


def test_une_erreur_n_ecrit_rien_du_tout(connecte, chantier_avec_etapes):
    """Tous validés avant qu'un seul soit écrit.

    Enregistrer les étapes 1 à 8 puis échouer à la 9 laisserait
    l'utilisateur sans savoir ce qui est passé — et il resaisirait tout,
    ou rien.
    """
    from apps.btp.models import ProjectStepItem

    points = {p.label: p for p in ProjectStepItem.objects.filter(
        step__project=chantier_avec_etapes)}

    reponse = connecte.post(
        reverse('btp:project_fill_all', args=[chantier_avec_etapes.pk]), {
            # Valide, dans la PREMIÈRE étape.
            f'point_{points["Nacelle nécessaire ?"].pk}': 'true',
            # Invalide, dans la SECONDE.
            f'point_{points["Date de livraison annoncée"].pk}': 'bientôt',
        })
    assert reponse.status_code == 200

    for point in points.values():
        point.refresh_from_db()
    assert points['Nacelle nécessaire ?'].answer_boolean is None, (
        'la reponse valide a ete ecrite alors qu une autre etape echouait')
    assert points['Date de livraison annoncée'].answer_date is None


def test_enregistrer_a_moitie_rempli_reussit(connecte, chantier_avec_etapes):
    """« Avertir sans bloquer » vaut aussi sur cette page."""
    from apps.btp.models import ProjectStepItem

    nacelle = ProjectStepItem.objects.get(
        step__project=chantier_avec_etapes, label='Nacelle nécessaire ?')
    reponse = connecte.post(
        reverse('btp:project_fill_all', args=[chantier_avec_etapes.pk]),
        {f'point_{nacelle.pk}': 'false'}, follow=True)
    assert reponse.status_code == 200
    nacelle.refresh_from_db()
    assert nacelle.answer_boolean is False

    corps = reponse.content.decode('utf-8', 'replace')
    assert 'restent à renseigner' in corps


def test_quand_tout_est_rempli_on_le_dit(connecte, chantier_avec_etapes):
    """Le contraire de l'avertissement : savoir qu'on peut démarrer."""
    from apps.btp.models import ProjectStepItem

    points = {p.label: p for p in ProjectStepItem.objects.filter(
        step__project=chantier_avec_etapes)}
    reponse = connecte.post(
        reverse('btp:project_fill_all', args=[chantier_avec_etapes.pk]), {
            f'point_{points["Nacelle nécessaire ?"].pk}': 'false',
            f'point_{points["Hauteur sous plafond"].pk}': '2.5',
            f'point_{points["Date de livraison annoncée"].pk}': '2026-03-01',
        }, follow=True)
    corps = reponse.content.decode('utf-8', 'replace')
    assert 'sans angle mort' in corps


def test_les_etapes_sans_point_ne_sont_pas_affichees(connecte,
                                                     chantier_avec_etapes):
    """Une étape vide affichée donnerait l'impression d'un bug."""
    from apps.btp.models import ProjectPlanStep

    ProjectPlanStep.objects.create(project=chantier_avec_etapes,
                                   name='Étape nue', order=99)
    reponse = connecte.get(reverse('btp:project_fill_all',
                                   args=[chantier_avec_etapes.pk]))
    assert len(reponse.context['blocs']) == 2
    assert 'Étape nue' not in reponse.content.decode('utf-8', 'replace')


def test_un_chantier_sans_point_invite_a_appliquer_un_modele(connecte,
                                                             chantier):
    reponse = connecte.get(reverse('btp:project_fill_all',
                                   args=[chantier.pk]))
    assert reponse.status_code == 200
    assert reponse.context['blocs'] == []
    assert 'Appliquer un mod' in reponse.content.decode('utf-8', 'replace')


def test_le_lien_tout_remplir_est_sur_la_page_des_etapes(connecte,
                                                         chantier_avec_etapes):
    """Une page qu'aucun lien ne désigne n'existe pas pour l'utilisateur."""
    corps = connecte.get(reverse('btp:project_planning',
                                 args=[chantier_avec_etapes.pk])).content.decode(
                                     'utf-8', 'replace')
    assert reverse('btp:project_fill_all',
                   args=[chantier_avec_etapes.pk]) in corps


def test_tout_remplir_chez_le_voisin_est_refuse(connecte, objets_du_voisin):
    reponse = connecte.get(reverse('btp:project_fill_all',
                                   args=[objets_du_voisin['projet'].pk]))
    assert reponse.status_code == 404


def test_tout_remplir_tient_les_143_points_de_l_etancheite(connecte,
                                                            client_crm):
    """La page doit encaisser le vrai volume, pas deux points de test."""
    from apps.btp.models import (
        BTPProject, ProjectStepItem, ProjectTemplate)

    connecte.post(reverse('btp:template_install_starter'),
                  {'cle': 'etancheite'})
    modele = ProjectTemplate.objects.get()
    connecte.post(reverse('btp:project_create'), {
        'name': 'Toiture Legrand', 'customer': client_crm.pk,
        'status': 'study', 'start_date': '2026-09-01',
        'estimated_budget': '0', 'retention_rate': '5',
        'template': modele.pk,
    })
    chantier = BTPProject.objects.get(name='Toiture Legrand')

    reponse = connecte.get(reverse('btp:project_fill_all',
                                   args=[chantier.pk]))
    assert reponse.status_code == 200
    en_base = ProjectStepItem.objects.filter(step__project=chantier).count()
    assert en_base > 100
    assert reponse.context['total'] == en_base
    assert len(reponse.context['blocs']) == 12

    # Et un envoi partiel sur ce volume passe.
    sondage = ProjectStepItem.objects.get(
        step__project=chantier,
        label='Un sondage ou carottage a-t-il été réalisé ?')
    envoi = connecte.post(reverse('btp:project_fill_all',
                                  args=[chantier.pk]),
                          {f'point_{sondage.pk}': 'true'})
    assert envoi.status_code == 302
    sondage.refresh_from_db()
    assert sondage.answer_boolean is True


# ── 16. Désigner un devis et une fiche fournisseur ──────────────────────────
#
# Deux types de réponse qui ne demandent pas de SAISIR une référence mais de
# DÉSIGNER une fiche de l'ERP. La différence n'est pas cosmétique :
#
#   * un numéro recopié se trompe d'un chiffre, et personne ne le voit ;
#   * il ne se clique pas — il faut aller rechercher le devis à la main ;
#   * il ne survit pas à une renumérotation ;
#   * il ne se filtre pas : « quels chantiers chez ce fournisseur ? » reste
#     sans réponse.
#
# D'où deux colonnes FK, et non deux CharField.

@pytest.fixture
def devis(entreprise, client_crm, chantier):
    from decimal import Decimal

    from apps.btp.models import BTPQuote
    return BTPQuote.objects.create(
        company=entreprise, project=chantier, customer=client_crm,
        number='DEV-0042', subject='Rénovation complète',
        total_ht=Decimal('12500.00'))


@pytest.fixture
def fournisseur(entreprise):
    from apps.purchases.models import Supplier
    return Supplier.objects.create(
        company=entreprise, name='Négoce Rexel', phone='0387000000',
        lead_time_days=5)


@pytest.fixture
def etape_avec_fiches(chantier_avec_etapes):
    """Ajoute un point « devis » et un point « fournisseur » à l'étape 1."""
    from apps.btp.models import ProjectPlanStep, ProjectStepItem

    etape = ProjectPlanStep.objects.get(
        project=chantier_avec_etapes, name='Analyse sur place')
    ProjectStepItem.objects.create(
        step=etape, label='Devis concerné', answer_type='quote',
        is_required=True, order=80)
    ProjectStepItem.objects.create(
        step=etape, label='Fournisseur retenu', answer_type='supplier',
        is_required=True, order=81)
    return etape


def _envoi_de_base(etape):
    return {'name': etape.name, 'step_type': etape.step_type, 'order': 1,
            'status': 'pending', 'progress_percent': 0}


def test_designer_un_devis_et_un_fournisseur(connecte, etape_avec_fiches,
                                             devis, fournisseur):
    from apps.btp.models import ProjectStepItem

    point_devis = ProjectStepItem.objects.get(step=etape_avec_fiches,
                                              answer_type='quote')
    point_fournisseur = ProjectStepItem.objects.get(step=etape_avec_fiches,
                                                    answer_type='supplier')

    reponse = connecte.post(
        reverse('btp:step_detail', args=[etape_avec_fiches.pk]), {
            **_envoi_de_base(etape_avec_fiches),
            f'point_{point_devis.pk}': devis.pk,
            f'point_{point_fournisseur.pk}': fournisseur.pk,
        })
    assert reponse.status_code == 302

    point_devis.refresh_from_db()
    point_fournisseur.refresh_from_db()
    assert point_devis.answer_quote == devis
    assert point_fournisseur.answer_supplier == fournisseur
    assert point_devis.is_answered is True
    assert point_fournisseur.is_answered is True


def test_la_reponse_affichee_porte_le_numero_et_le_montant(
        connecte, etape_avec_fiches, devis, fournisseur):
    """Le numéro seul ne dit pas si c'est le bon devis."""
    from apps.btp.models import ProjectStepItem

    point_devis = ProjectStepItem.objects.get(step=etape_avec_fiches,
                                              answer_type='quote')
    point_devis.answer_quote = devis
    point_devis.save()
    assert point_devis.reponse_affichable == 'DEV-0042 — 12500.00 € HT'

    point_fournisseur = ProjectStepItem.objects.get(step=etape_avec_fiches,
                                                    answer_type='supplier')
    point_fournisseur.answer_supplier = fournisseur
    point_fournisseur.save()
    assert point_fournisseur.reponse_affichable == 'Négoce Rexel'


def test_un_devis_sans_numero_ne_rend_pas_une_chaine_vide(connecte,
                                                          etape_avec_fiches,
                                                          entreprise,
                                                          client_crm):
    """`number` est `blank=True` : un devis peut n'en avoir aucun."""
    from decimal import Decimal

    from apps.btp.models import BTPQuote, ProjectStepItem

    anonyme = BTPQuote.objects.create(
        company=entreprise, customer=client_crm, total_ht=Decimal('100'))
    point = ProjectStepItem.objects.get(step=etape_avec_fiches,
                                        answer_type='quote')
    point.answer_quote = anonyme
    point.save()
    assert point.reponse_affichable.startswith('Devis sans numéro')


def test_les_liens_vers_les_fiches_sont_affiches(connecte, etape_avec_fiches,
                                                 devis, fournisseur):
    """Tout l'intérêt de désigner une fiche : on l'ouvre d'un clic."""
    from apps.btp.models import ProjectStepItem

    ProjectStepItem.objects.filter(
        step=etape_avec_fiches, answer_type='quote').update(
            answer_quote=devis)
    ProjectStepItem.objects.filter(
        step=etape_avec_fiches, answer_type='supplier').update(
            answer_supplier=fournisseur)

    corps = connecte.get(reverse('btp:step_detail',
                                 args=[etape_avec_fiches.pk])).content.decode(
                                     'utf-8', 'replace')
    assert reverse('btp:quote_detail', args=[devis.pk]) in corps
    assert reverse('purchases:supplier_detail',
                   args=[fournisseur.pk]) in corps
    assert 'DEV-0042' in corps
    assert 'Négoce Rexel' in corps


def test_l_etiquette_du_devis_distingue_deux_devis_du_meme_client(
        connecte, etape_avec_fiches, devis, entreprise, client_crm):
    """Deux devis du même client sont indiscernables sans le montant.

    `BTPQuote.__str__` ne donne que « numéro — client ». La liste
    déroulante ajoute donc le montant et le chantier.
    """
    from decimal import Decimal

    from apps.btp.models import BTPQuote

    BTPQuote.objects.create(
        company=entreprise, customer=client_crm, number='DEV-0043',
        total_ht=Decimal('980.00'))

    corps = connecte.get(reverse('btp:step_detail',
                                 args=[etape_avec_fiches.pk])).content.decode(
                                     'utf-8', 'replace')
    assert 'DEV-0042 — Mme Martin — 12500.00 € HT' in corps
    assert 'DEV-0043 — Mme Martin — 980.00 € HT' in corps


def test_les_devis_du_chantier_viennent_en_tete(connecte, etape_avec_fiches,
                                                devis, entreprise,
                                                client_crm):
    """Neuf fois sur dix c'est celui du chantier qu'on cherche."""
    from decimal import Decimal

    from apps.btp.forms_etapes import PointsDeLEtapeForm
    from apps.btp.models import BTPQuote, ProjectStepItem

    # Plus récent, donc premier dans l'ordre par défaut — mais d'un autre
    # chantier.
    BTPQuote.objects.create(
        company=entreprise, customer=client_crm, number='DEV-0099',
        issue_date=date(2030, 1, 1), total_ht=Decimal('1'))

    points = list(ProjectStepItem.objects.filter(step=etape_avec_fiches))
    form = PointsDeLEtapeForm(points=points, company=entreprise,
                              project=etape_avec_fiches.project)
    choix = list(form._devis)
    assert choix[0] == devis


def test_un_devis_d_une_autre_entreprise_est_refuse(connecte,
                                                    etape_avec_fiches,
                                                    autre_entreprise):
    """Borné dans __init__, donc à la VALIDATION et pas qu'à l'affichage."""
    from decimal import Decimal

    from apps.btp.models import BTPQuote, ProjectStepItem
    from apps.crm.models import Customer

    acheteur = Customer.objects.create(company=autre_entreprise,
                                       name='Client voisin')
    etranger = BTPQuote.objects.create(
        company=autre_entreprise, customer=acheteur, number='DEV-VOISIN',
        total_ht=Decimal('99999'))

    point = ProjectStepItem.objects.get(step=etape_avec_fiches,
                                        answer_type='quote')
    reponse = connecte.post(
        reverse('btp:step_detail', args=[etape_avec_fiches.pk]), {
            **_envoi_de_base(etape_avec_fiches),
            f'point_{point.pk}': etranger.pk,
        })
    assert reponse.status_code == 200
    assert f'point_{point.pk}' in reponse.context['form_points'].errors
    point.refresh_from_db()
    assert point.answer_quote_id is None


def test_un_fournisseur_d_une_autre_entreprise_est_refuse(connecte,
                                                          etape_avec_fiches,
                                                          autre_entreprise):
    from apps.btp.models import ProjectStepItem
    from apps.purchases.models import Supplier

    etranger = Supplier.objects.create(company=autre_entreprise,
                                       name='Fournisseur du voisin')
    point = ProjectStepItem.objects.get(step=etape_avec_fiches,
                                        answer_type='supplier')
    reponse = connecte.post(
        reverse('btp:step_detail', args=[etape_avec_fiches.pk]), {
            **_envoi_de_base(etape_avec_fiches),
            f'point_{point.pk}': etranger.pk,
        })
    assert reponse.status_code == 200
    point.refresh_from_db()
    assert point.answer_supplier_id is None


def test_un_fournisseur_inactif_n_est_pas_propose(connecte, etape_avec_fiches,
                                                  entreprise):
    from apps.btp.models import ProjectStepItem
    from apps.purchases.models import Supplier

    ferme = Supplier.objects.create(company=entreprise,
                                    name='Négoce fermé', is_active=False)
    point = ProjectStepItem.objects.get(step=etape_avec_fiches,
                                        answer_type='supplier')
    reponse = connecte.post(
        reverse('btp:step_detail', args=[etape_avec_fiches.pk]), {
            **_envoi_de_base(etape_avec_fiches),
            f'point_{point.pk}': ferme.pk,
        })
    assert reponse.status_code == 200
    point.refresh_from_db()
    assert point.answer_supplier_id is None


def test_supprimer_le_devis_vide_la_case(connecte, etape_avec_fiches, devis):
    """SET_NULL et non PROTECT : supprimer un devis ne doit pas être bloqué
    parce qu'une case de chantier le cite. La case redevient « non
    renseignée », donc signalée — ce qui est juste : le devis n'existe plus.
    """
    from apps.btp.models import ProjectStepItem

    point = ProjectStepItem.objects.get(step=etape_avec_fiches,
                                        answer_type='quote')
    point.answer_quote = devis
    point.save()
    assert point.is_answered is True

    devis.delete()

    point.refresh_from_db()
    assert point.answer_quote_id is None
    assert point.is_answered is False
    assert point.reponse_affichable == ''


def test_effacer_la_designation_efface_la_tracabilite(connecte,
                                                      etape_avec_fiches,
                                                      devis):
    from apps.btp.models import ProjectStepItem

    point = ProjectStepItem.objects.get(step=etape_avec_fiches,
                                        answer_type='quote')
    base = _envoi_de_base(etape_avec_fiches)

    connecte.post(reverse('btp:step_detail', args=[etape_avec_fiches.pk]),
                  {**base, f'point_{point.pk}': devis.pk})
    point.refresh_from_db()
    assert point.filled_at is not None

    connecte.post(reverse('btp:step_detail', args=[etape_avec_fiches.pk]),
                  {**base, f'point_{point.pk}': ''})
    point.refresh_from_db()
    assert point.answer_quote_id is None
    assert point.filled_at is None


def test_redesigner_le_meme_devis_ne_bouge_pas_la_date(connecte,
                                                       etape_avec_fiches,
                                                       devis):
    """`_valeur_de_la_reponse` compare les clés, pas les objets.

    Deux instances distinctes du même devis ne sont pas égales dans tous
    les cas : comparer les objets ferait croire à un changement et
    réhorodaterait à chaque enregistrement.
    """
    from apps.btp.models import ProjectStepItem

    point = ProjectStepItem.objects.get(step=etape_avec_fiches,
                                        answer_type='quote')
    base = _envoi_de_base(etape_avec_fiches)

    connecte.post(reverse('btp:step_detail', args=[etape_avec_fiches.pk]),
                  {**base, f'point_{point.pk}': devis.pk})
    point.refresh_from_db()
    premiere = point.filled_at

    connecte.post(reverse('btp:step_detail', args=[etape_avec_fiches.pk]),
                  {**base, f'point_{point.pk}': devis.pk})
    point.refresh_from_db()
    assert point.filled_at == premiere


def test_sans_aucun_devis_le_champ_le_dit(connecte, etape_avec_fiches):
    """Une liste vide sans explication passe pour un bug."""
    corps = connecte.get(reverse('btp:step_detail',
                                 args=[etape_avec_fiches.pk])).content.decode(
                                     'utf-8', 'replace')
    assert 'Aucun devis dans cette entreprise' in corps


def test_tout_remplir_designe_aussi_les_fiches(connecte, etape_avec_fiches,
                                               devis, fournisseur):
    from apps.btp.models import ProjectStepItem

    point_devis = ProjectStepItem.objects.get(step=etape_avec_fiches,
                                              answer_type='quote')
    point_fournisseur = ProjectStepItem.objects.get(step=etape_avec_fiches,
                                                    answer_type='supplier')
    reponse = connecte.post(
        reverse('btp:project_fill_all',
                args=[etape_avec_fiches.project.pk]), {
            f'point_{point_devis.pk}': devis.pk,
            f'point_{point_fournisseur.pk}': fournisseur.pk,
        })
    assert reponse.status_code == 302
    point_devis.refresh_from_db()
    point_fournisseur.refresh_from_db()
    assert point_devis.answer_quote == devis
    assert point_fournisseur.answer_supplier == fournisseur


def test_la_recherche_montre_la_fiche_designee(connecte, etape_avec_fiches,
                                               fournisseur):
    from apps.btp.models import ProjectStepItem

    ProjectStepItem.objects.filter(
        step=etape_avec_fiches, answer_type='supplier').update(
            answer_supplier=fournisseur)

    reponse = connecte.get(reverse('btp:points_search'),
                           {'q': 'Fournisseur retenu'})
    assert reponse.status_code == 200
    assert 'Négoce Rexel' in reponse.content.decode('utf-8', 'replace')


# ── 17. Les modèles prêts citent le devis et le fournisseur ─────────────────

@pytest.mark.parametrize('cle', ['electricite', 'etancheite'])
def test_les_modeles_prets_demandent_le_devis_et_le_fournisseur(connecte,
                                                                entreprise,
                                                                cle):
    from apps.btp.models import ProjectTemplateItem

    connecte.post(reverse('btp:template_install_starter'), {'cle': cle})
    points = ProjectTemplateItem.objects.filter(
        step__template__company=entreprise)

    # Le devis est demandé à la validation ET rappelé à la commande.
    assert points.filter(answer_type='quote').count() == 2
    assert points.filter(answer_type='supplier').count() == 1

    validation = points.get(answer_type='quote',
                            step__step_type='quote_validation')
    assert validation.is_required is True
    commande = points.get(answer_type='supplier',
                          step__step_type='material_prep')
    assert commande.is_required is True

    # Et la référence côté fournisseur reste du texte libre : ce n'est pas
    # une fiche de notre ERP, c'est un numéro chez eux.
    assert points.filter(
        label__icontains='devis fournisseur',
        answer_type='text').exists()


@pytest.mark.parametrize('cle', ['electricite', 'etancheite'])
def test_le_point_devis_du_modele_pret_se_remplit(connecte, entreprise,
                                                   client_crm, cle):
    """De bout en bout : installer, créer, désigner."""
    from decimal import Decimal

    from apps.btp.models import (
        BTPProject, BTPQuote, ProjectStepItem, ProjectTemplate)

    connecte.post(reverse('btp:template_install_starter'), {'cle': cle})
    modele = ProjectTemplate.objects.get()

    connecte.post(reverse('btp:project_create'), {
        'name': 'Chantier avec devis', 'customer': client_crm.pk,
        'status': 'study', 'start_date': '2026-05-04',
        'estimated_budget': '0', 'retention_rate': '5',
        'template': modele.pk,
    })
    chantier = BTPProject.objects.get(name='Chantier avec devis')
    facture = BTPQuote.objects.create(
        company=entreprise, project=chantier, customer=client_crm,
        number='DEV-0100', total_ht=Decimal('7400.00'))

    point = ProjectStepItem.objects.get(
        step__project=chantier, answer_type='quote',
        step__step_type='quote_validation')
    reponse = connecte.post(reverse('btp:project_fill_all',
                                    args=[chantier.pk]),
                            {f'point_{point.pk}': facture.pk})
    assert reponse.status_code == 302
    point.refresh_from_db()
    assert point.answer_quote == facture
    assert point.reponse_affichable == 'DEV-0100 — 7400.00 € HT'


def test_l_aide_du_modele_reste_affichee(connecte, chantier_avec_etapes):
    """Le passage a `champ.help_text` ne doit pas perdre l'aide du modele.

    Les deux sont egaux la plupart du temps -- le champ recoit celui du
    point -- mais verifier le cas courant evite que la correction du cas
    particulier casse le general.
    """
    from apps.btp.models import ProjectPlanStep, ProjectStepItem

    etape = ProjectPlanStep.objects.get(
        project=chantier_avec_etapes, name='Analyse sur place')
    ProjectStepItem.objects.create(
        step=etape, label='Avec une aide', answer_type='text',
        help_text='Voici la precision attendue.', order=90)

    for nom, args in [('btp:step_detail', [etape.pk]),
                      ('btp:project_fill_all', [chantier_avec_etapes.pk])]:
        corps = connecte.get(reverse(nom, args=args)).content.decode(
            'utf-8', 'replace')
        assert 'Voici la precision attendue.' in corps, nom
