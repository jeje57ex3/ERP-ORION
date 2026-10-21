"""Le planning : congés, maladie, arrêts, repos, heures pointées.

Ce module ne stocke presque rien, et c'est son intérêt. Il **lit** quatre
sources et les superpose :

- le rythme hebdomadaire (`hr.WorkSchedule`) → heures prévues, jours de repos
- les congés et la maladie (`hr.LeaveRequest`) → existaient déjà
- les arrêts de travail (`hr.WorkStoppage`)
- les heures pointées (`btp.BTPTimesheet`) → existaient déjà

Aucune de ces données n'est recopiée. Un second endroit pour déclarer un
congé, c'est un congé sur deux qui manque quelque part, et le planning
serait faux la moitié du temps sans que l'on sache laquelle.

Les propriétés vérifiées ici, par ordre de gravité :

**L'arrêt de travail passe devant tout.** On n'est pas « en congé » pendant
un arrêt. Afficher le congé masquerait le fait médical, qui est celui qui
compte pour la paie comme pour le remplacement sur le chantier.

**Un congé ou un arrêt qui enjambe le mois apparaît quand même.** Filtrer
sur le mois de début ferait disparaître du planning de février un arrêt
commencé le 28 janvier — exactement celui qu'il faut voir.

**Une fin d'arrêt absente signifie « toujours en cours »**, et non « finie
aujourd'hui ». Le traiter autrement effacerait du planning l'arrêt le plus
préoccupant : celui dont on ne connaît pas le terme.

**La jointure User / Employee.** `LeaveRequest.employee` désigne un
`hr.Employee`, `BTPTimesheet.employee` désigne un `auth.User`, et
`Employee.user` est facultatif. Un salarié sans compte n'a donc aucune
heure pointée — le planning le dit (`sans_compte`) au lieu d'afficher une
colonne vide inexpliquée.
"""

from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from apps.accounts.models import UserProfile
from apps.hr.models import Employee, LeaveRequest, WorkSchedule, WorkStoppage
from apps.hr.planning_service import (
    annee_mois_demandes,
    bornes_du_mois,
    mois_precedent,
    mois_suivant,
    planning_du_mois,
    planning_equipe,
)

pytestmark = pytest.mark.django_db


# ── Terrain ─────────────────────────────────────────────────────────────────

@pytest.fixture
def entreprise(db):
    from apps.core.models import Company
    return Company.objects.create(name='Dupont SA', slug='dupont-sa')


@pytest.fixture
def autre_entreprise(db):
    from apps.core.models import Company
    return Company.objects.create(name='Martin SA', slug='martin-sa')


def creer_compte(nom, role='user', company=None):
    utilisateur = User.objects.create_user(
        username=nom, password='x', email=f'{nom}@exemple.fr')
    profil, _ = UserProfile.objects.get_or_create(user=utilisateur)
    profil.role = role
    profil.save()
    if company is not None:
        profil.companies.add(company)
    # Relecture : le signal qui crée le profil le met en cache sur l'objet
    # User avec son rôle d'origine. Sans cela, utilisateur.profile.role
    # rendrait encore 'user'.
    return User.objects.get(pk=utilisateur.pk)


def creer_salarie(company, prenom='Marc', nom='Dupont', avec_compte=True):
    utilisateur = creer_compte(f'{prenom}.{nom}'.lower(), company=company) \
        if avec_compte else None
    return Employee.objects.create(
        company=company, first_name=prenom, last_name=nom,
        user=utilisateur, is_active=True)


def creer_chantier(company, nom='Chantier A'):
    from apps.btp.models import BTPProject
    from apps.crm.models import Customer
    client = Customer.objects.create(company=company, name='Client A')
    return BTPProject.objects.create(company=company, name=nom,
                                     customer=client)


def pointer(company, salarie, jour, heures=8, sup=0, chantier=None):
    from apps.btp.models import BTPTimesheet
    return BTPTimesheet.objects.create(
        company=company, project=chantier, employee=salarie.user,
        work_date=jour, hours=heures, overtime_hours=sup)


@pytest.fixture
def salarie(entreprise):
    return creer_salarie(entreprise)


@pytest.fixture
def encadrant(entreprise):
    return creer_compte('patron', role='admin', company=entreprise)


def jour_du_mois(planning, numero):
    """La cellule du jour `numero` dans un planning mensuel."""
    return next(j for j in planning['jours'] if j['date'].day == numero)


# ── 1. Le rythme hebdomadaire ───────────────────────────────────────────────

def test_un_jour_a_zero_heure_est_un_jour_de_repos(salarie, entreprise):
    """La notion découle des heures et n'a pas de case à elle.

    Avec un booléen séparé, « repos » et « 7 h prévues » auraient pu se
    contredire, et rien n'aurait dit lequel croire.
    """
    rythme = WorkSchedule.objects.create(company=entreprise,
                                         employee=salarie)
    # 15 mars 2026 est un dimanche, 16 un lundi.
    assert rythme.est_jour_de_repos(date(2026, 3, 15)) is True
    assert rythme.est_jour_de_repos(date(2026, 3, 16)) is False


def test_le_rythme_par_defaut_fait_trente_cinq_heures(salarie, entreprise):
    """7 h du lundi au vendredi : le temps plein légal français.

    Un défaut juste évite de remplir sept champs pour le salarié ordinaire.
    """
    rythme = WorkSchedule.objects.create(company=entreprise,
                                         employee=salarie)
    assert rythme.heures_hebdomadaires == Decimal('35')
    assert rythme.jours_travailles == ['Lundi', 'Mardi', 'Mercredi',
                                       'Jeudi', 'Vendredi']


def test_un_temps_partiel_avec_mercredi_libre(salarie, entreprise):
    rythme = WorkSchedule.objects.create(
        company=entreprise, employee=salarie, hours_wednesday=0)
    assert rythme.heures_hebdomadaires == Decimal('28')
    assert 'Mercredi' not in rythme.jours_travailles
    # 18 mars 2026 est un mercredi.
    assert rythme.est_jour_de_repos(date(2026, 3, 18)) is True


def test_une_demi_journee_est_exprimable(salarie, entreprise):
    """Ce que des booléens n'auraient pas permis.

    Avec une case « travaillé / repos », un vendredi de 3,5 h aurait été
    annoncé comme une journée entière, et l'écart d'heures aurait été faux
    toutes les semaines.
    """
    rythme = WorkSchedule.objects.create(
        company=entreprise, employee=salarie, hours_friday=Decimal('3.5'))
    assert rythme.heures_hebdomadaires == Decimal('31.5')
    assert rythme.heures_du_jour(date(2026, 3, 20)) == Decimal('3.5')
    assert rythme.est_jour_de_repos(date(2026, 3, 20)) is False


def test_heures_par_jour_rend_les_sept_jours_dans_l_ordre(salarie,
                                                          entreprise):
    """Propriété écrite pour les gabarits.

    Django n'accepte pas « {% for h in champ1,champ2,… %} » : le tag for
    prend UNE expression, et une liste littérale y lève une
    TemplateSyntaxError.
    """
    rythme = WorkSchedule.objects.create(company=entreprise,
                                         employee=salarie)
    jours = rythme.heures_par_jour
    assert len(jours) == 7
    assert jours[0]['libelle'] == 'Lundi'
    assert jours[6]['libelle'] == 'Dimanche'
    assert jours[6]['repos'] is True


def test_sans_rythme_le_planning_suppose_lundi_vendredi(salarie):
    """Une hypothèse, pas une donnée — et l'interface le signale.

    Sans repli, un salarié sans rythme n'aurait aucune heure prévue et
    paraîtrait toujours à jour.
    """
    planning = planning_du_mois(salarie, 2026, 3)
    assert planning['schedule'] is None
    assert jour_du_mois(planning, 16)['heures_prevues'] == Decimal('7')
    assert jour_du_mois(planning, 15)['repos'] is True


# ── 2. L'arrêt de travail passe devant tout ─────────────────────────────────

def test_un_arret_masque_un_conge_pose_le_meme_jour(salarie, entreprise):
    """On n'est pas « en congé » pendant un arrêt de travail.

    C'est le fait médical qui compte — pour la paie comme pour le
    remplacement sur le chantier. Afficher le congé le cacherait.
    """
    LeaveRequest.objects.create(
        company=entreprise, employee=salarie, leave_type='paid',
        start_date=date(2026, 3, 16), end_date=date(2026, 3, 20),
        status='approved')
    WorkStoppage.objects.create(
        company=entreprise, employee=salarie, kind='accident_travail',
        start_date=date(2026, 3, 18), end_date=date(2026, 3, 25))

    planning = planning_du_mois(salarie, 2026, 3)
    assert jour_du_mois(planning, 17)['etat'] == 'conge'
    assert jour_du_mois(planning, 18)['etat'] == 'arret'
    assert jour_du_mois(planning, 22)['etat'] == 'arret'


def test_un_arret_sans_fin_court_jusqu_au_bout_du_mois(salarie, entreprise):
    """Une fin absente signifie « toujours en cours ».

    La traiter comme une fin immédiate ferait disparaître du planning
    l'arrêt le plus préoccupant : celui dont on ne connaît pas le terme.
    """
    arret = WorkStoppage.objects.create(
        company=entreprise, employee=salarie, kind='maladie',
        start_date=date(2026, 3, 10), end_date=None)

    planning = planning_du_mois(salarie, 2026, 3)
    assert jour_du_mois(planning, 9)['etat'] != 'arret'
    assert jour_du_mois(planning, 10)['etat'] == 'arret'
    assert jour_du_mois(planning, 31)['etat'] == 'arret'
    assert arret.duree_jours is None
    assert arret.couvre(date(2030, 1, 1)) is True


def test_un_arret_sans_fin_reste_visible_les_mois_suivants(salarie,
                                                           entreprise):
    """Commencé en janvier, il doit apparaître en mars."""
    WorkStoppage.objects.create(
        company=entreprise, employee=salarie, kind='maladie',
        start_date=date(2026, 1, 20), end_date=None)
    planning = planning_du_mois(salarie, 2026, 3)
    assert all(jour['etat'] == 'arret' for jour in planning['jours'])
    assert planning['totaux']['jours_arret'] == 31


def test_un_arret_qui_enjambe_le_mois_apparait(salarie, entreprise):
    """Filtrer sur le mois de début l'aurait fait disparaître.

    Un arrêt commencé le 28 janvier et fini le 10 février n'appartient à
    aucun « mois de début » de février — et c'est exactement celui qu'il
    faut voir en février.
    """
    WorkStoppage.objects.create(
        company=entreprise, employee=salarie, kind='maladie',
        start_date=date(2026, 1, 28), end_date=date(2026, 2, 10))

    planning = planning_du_mois(salarie, 2026, 2)
    assert jour_du_mois(planning, 1)['etat'] == 'arret'
    assert jour_du_mois(planning, 10)['etat'] == 'arret'
    assert jour_du_mois(planning, 11)['etat'] != 'arret'


def test_un_conge_qui_enjambe_le_mois_apparait(salarie, entreprise):
    LeaveRequest.objects.create(
        company=entreprise, employee=salarie, leave_type='paid',
        start_date=date(2026, 2, 25), end_date=date(2026, 3, 5),
        status='approved')
    planning = planning_du_mois(salarie, 2026, 3)
    assert jour_du_mois(planning, 2)['etat'] == 'conge'
    assert jour_du_mois(planning, 6)['etat'] != 'conge'


def test_la_maladie_est_distinguee_du_conge(salarie, entreprise):
    """Un congé payé et un congé maladie ne se gèrent pas pareil."""
    LeaveRequest.objects.create(
        company=entreprise, employee=salarie, leave_type='sick',
        start_date=date(2026, 3, 16), end_date=date(2026, 3, 17),
        status='approved')
    planning = planning_du_mois(salarie, 2026, 3)
    assert jour_du_mois(planning, 16)['etat'] == 'maladie'


# ── 3. Les statuts de congé ─────────────────────────────────────────────────

def test_un_conge_refuse_n_apparait_pas(salarie, entreprise):
    """Il n'empêche personne de travailler.

    L'afficher ferait croire à une absence, et le responsable chercherait
    un remplaçant pour un salarié présent.
    """
    LeaveRequest.objects.create(
        company=entreprise, employee=salarie, leave_type='paid',
        start_date=date(2026, 3, 16), end_date=date(2026, 3, 20),
        status='refused')
    planning = planning_du_mois(salarie, 2026, 3)
    assert jour_du_mois(planning, 17)['etat'] == 'travaille'


def test_un_conge_annule_n_apparait_pas(salarie, entreprise):
    LeaveRequest.objects.create(
        company=entreprise, employee=salarie, leave_type='paid',
        start_date=date(2026, 3, 16), end_date=date(2026, 3, 20),
        status='cancelled')
    planning = planning_du_mois(salarie, 2026, 3)
    assert jour_du_mois(planning, 17)['etat'] == 'travaille'


def test_un_conge_en_attente_apparait(salarie, entreprise):
    """C'est précisément l'information utile avant d'engager la semaine."""
    LeaveRequest.objects.create(
        company=entreprise, employee=salarie, leave_type='paid',
        start_date=date(2026, 3, 16), end_date=date(2026, 3, 20),
        status='pending')
    planning = planning_du_mois(salarie, 2026, 3)
    jour = jour_du_mois(planning, 17)
    assert jour['etat'] == 'conge'
    assert jour['conges'][0].status == 'pending'


# ── 4. Les heures pointées ──────────────────────────────────────────────────

def test_les_heures_pointees_remontent_dans_le_planning(salarie, entreprise):
    chantier = creer_chantier(entreprise)
    pointer(entreprise, salarie, date(2026, 3, 16), heures=8, chantier=chantier)
    pointer(entreprise, salarie, date(2026, 3, 16), heures=Decimal('1.5'),
            sup=Decimal('1.5'))

    planning = planning_du_mois(salarie, 2026, 3)
    jour = jour_du_mois(planning, 16)
    assert jour['heures_pointees'] == Decimal('9.5')
    assert jour['heures_sup'] == Decimal('1.5')
    assert len(jour['pointages']) == 2


def test_une_heure_sans_chantier_est_comptee(salarie, entreprise):
    """Atelier, trajet, réunion : ces heures existent et sont payées.

    Le chantier était obligatoire ; elles étaient donc soit absentes du
    pointage, soit imputées à un chantier au hasard — ce qui faussait son
    coût.
    """
    pointage = pointer(entreprise, salarie, date(2026, 3, 16), heures=4)
    assert pointage.project is None
    planning = planning_du_mois(salarie, 2026, 3)
    assert jour_du_mois(planning, 16)['heures_pointees'] == Decimal('4')


def test_un_salarie_sans_compte_n_a_aucune_heure(entreprise):
    """Ce n'est pas une erreur de lecture, c'est la structure.

    BTPTimesheet.employee désigne un auth.User, et Employee.user est
    facultatif. Le planning le signale au lieu d'afficher une colonne vide
    inexpliquée.
    """
    sans_compte = creer_salarie(entreprise, 'Jean', 'Sanscompte',
                                avec_compte=False)
    planning = planning_du_mois(sans_compte, 2026, 3)
    assert planning['sans_compte'] is True
    assert planning['totaux']['heures_pointees'] == Decimal('0')


def test_les_heures_d_un_autre_salarie_ne_remontent_pas(entreprise):
    """La jointure passe par Employee.user : elle doit être exacte."""
    un = creer_salarie(entreprise, 'Marc', 'Un')
    deux = creer_salarie(entreprise, 'Luc', 'Deux')
    pointer(entreprise, un, date(2026, 3, 16), heures=8)

    assert planning_du_mois(un, 2026, 3)['totaux']['heures_pointees'] == Decimal('8')
    assert planning_du_mois(deux, 2026, 3)['totaux']['heures_pointees'] == Decimal('0')


# ── 5. L'écart entre prévu et pointé ────────────────────────────────────────

def test_les_heures_prevues_d_un_jour_d_absence_ne_comptent_pas(salarie,
                                                                entreprise):
    """Sinon un mois de congés ferait passer le salarié pour un retardataire.

    Compter les heures prévues d'un jour de congé gonfle l'écart d'un mois
    entier, et transforme des vacances en dette d'heures.
    """
    WorkSchedule.objects.create(company=entreprise, employee=salarie)
    LeaveRequest.objects.create(
        company=entreprise, employee=salarie, leave_type='paid',
        start_date=date(2026, 3, 2), end_date=date(2026, 3, 6),
        status='approved')

    planning = planning_du_mois(salarie, 2026, 3)
    assert jour_du_mois(planning, 3)['heures_prevues'] == Decimal('0')
    # Mars 2026 : 22 jours ouvrés, moins 5 de congé = 17 × 7 h
    assert planning['totaux']['heures_prevues'] == Decimal('119')
    assert planning['totaux']['jours_conge'] == 5


def test_l_ecart_est_la_difference_pointe_moins_prevu(salarie, entreprise):
    WorkSchedule.objects.create(company=entreprise, employee=salarie)
    # Un seul jour pointé sur les 22 ouvrés du mois.
    pointer(entreprise, salarie, date(2026, 3, 16), heures=8)
    planning = planning_du_mois(salarie, 2026, 3)
    assert planning['totaux']['heures_prevues'] == Decimal('154')  # 22 × 7
    assert planning['totaux']['heures_pointees'] == Decimal('8')
    assert planning['totaux']['ecart'] == Decimal('-146')


def test_les_totaux_se_repartissent_sans_recouvrement(salarie, entreprise):
    """Chaque jour compte dans une seule catégorie.

    Sinon la somme des catégories dépasserait le nombre de jours du mois,
    et aucun total ne serait interprétable.
    """
    WorkSchedule.objects.create(company=entreprise, employee=salarie)
    LeaveRequest.objects.create(
        company=entreprise, employee=salarie, leave_type='paid',
        start_date=date(2026, 3, 2), end_date=date(2026, 3, 6),
        status='approved')
    WorkStoppage.objects.create(
        company=entreprise, employee=salarie, kind='maladie',
        start_date=date(2026, 3, 10), end_date=date(2026, 3, 12))

    totaux = planning_du_mois(salarie, 2026, 3)['totaux']
    somme = (totaux['jours_conge'] + totaux['jours_arret']
             + totaux['jours_repos'] + totaux['jours_travailles'])
    assert somme == 31


# ── 6. La grille d'équipe ───────────────────────────────────────────────────

def test_la_grille_contient_une_ligne_par_salarie_actif(entreprise):
    creer_salarie(entreprise, 'Marc', 'Un')
    creer_salarie(entreprise, 'Luc', 'Deux')
    inactif = creer_salarie(entreprise, 'Jean', 'Parti')
    inactif.is_active = False
    inactif.save()

    planning = planning_equipe(entreprise, 2026, 3)
    noms = [ligne['employee'].last_name for ligne in planning['lignes']]
    assert noms == ['Deux', 'Un']
    assert len(planning['dates']) == 31


def test_la_grille_ne_montre_pas_les_salaries_d_une_autre_entreprise(
        entreprise, autre_entreprise):
    creer_salarie(entreprise, 'Marc', 'Interne')
    creer_salarie(autre_entreprise, 'Paul', 'Externe')
    planning = planning_equipe(entreprise, 2026, 3)
    noms = [ligne['employee'].last_name for ligne in planning['lignes']]
    assert noms == ['Interne']


def test_la_grille_et_la_fiche_disent_la_meme_chose(salarie, entreprise):
    """Deux chemins de lecture, une seule vérité.

    La grille d'équipe recalcule tout en mémoire pour tenir en quatre
    requêtes ; si elle divergeait de la vue par salarié, le planning se
    contredirait d'un écran à l'autre.
    """
    WorkSchedule.objects.create(company=entreprise, employee=salarie,
                                hours_wednesday=0)
    LeaveRequest.objects.create(
        company=entreprise, employee=salarie, leave_type='sick',
        start_date=date(2026, 3, 9), end_date=date(2026, 3, 10),
        status='approved')
    WorkStoppage.objects.create(
        company=entreprise, employee=salarie, kind='accident_travail',
        start_date=date(2026, 3, 16), end_date=date(2026, 3, 20))
    pointer(entreprise, salarie, date(2026, 3, 3), heures=Decimal('7.5'),
            sup=Decimal('0.5'))

    fiche = planning_du_mois(salarie, 2026, 3)
    ligne = planning_equipe(entreprise, 2026, 3)['lignes'][0]

    etats_fiche = [jour['etat'] for jour in fiche['jours']]
    etats_grille = [case['etat'] for case in ligne['cellules']]
    assert etats_fiche == etats_grille

    for cle in ('heures_prevues', 'heures_pointees', 'heures_sup',
                'jours_conge', 'jours_arret', 'ecart'):
        assert fiche['totaux'][cle] == ligne['totaux'][cle], cle


def test_la_grille_tient_en_un_nombre_fixe_de_requetes(entreprise,
                                                       django_assert_num_queries):
    """Quatre requêtes, quel que soit le nombre de salariés.

    Une lecture par salarié et par jour ferait 600 requêtes pour vingt
    salariés sur trente jours : l'écran deviendrait inutilisable
    exactement au moment où il devient utile.
    """
    for index in range(6):
        creer_salarie(entreprise, f'Sal{index}', f'Nom{index}')

    # 1 salariés + 1 rythmes + 1 congés + 1 arrêts + 1 pointages
    with django_assert_num_queries(5):
        planning_equipe(entreprise, 2026, 3)


# ── 7. Les bornes et la navigation ──────────────────────────────────────────

@pytest.mark.parametrize('annee,mois,dernier', [
    (2026, 1, 31), (2026, 2, 28), (2024, 2, 29), (2026, 4, 30),
])
def test_bornes_du_mois(annee, mois, dernier):
    """Février bissextile inclus : calendar.monthrange le sait, pas nous."""
    debut, fin = bornes_du_mois(annee, mois)
    assert debut == date(annee, mois, 1)
    assert fin == date(annee, mois, dernier)


def test_navigation_passe_les_annees():
    assert mois_precedent(2026, 1) == (2025, 12)
    assert mois_suivant(2026, 12) == (2027, 1)
    assert mois_precedent(2026, 3) == (2026, 2)
    assert mois_suivant(2026, 3) == (2026, 4)


@pytest.mark.parametrize('params', [
    {'mois': '13'}, {'mois': '0'}, {'mois': 'abc'}, {'annee': 'xx'},
    {'annee': '99999'}, {'mois': '-1'},
])
def test_une_url_de_travers_ne_casse_pas_la_page(params, rf):
    """Un mois à 13 lèverait ValueError dans calendar.monthrange.

    Soit une erreur 500 sur une simple URL mal tapée, là où le mois
    courant est une réponse raisonnable.
    """
    requete = rf.get('/hr/planning/', params)
    annee, mois = annee_mois_demandes(requete,
                                      aujourdhui=date(2026, 3, 15))
    assert (annee, mois) == (2026, 3)


def test_une_url_valide_est_respectee(rf):
    requete = rf.get('/hr/planning/', {'annee': '2025', 'mois': '7'})
    assert annee_mois_demandes(requete) == (2025, 7)


# ── 8. L'arrêt de travail, modèle ───────────────────────────────────────────

def test_une_fin_avant_le_debut_est_refusee(salarie, entreprise):
    from django.core.exceptions import ValidationError
    arret = WorkStoppage(company=entreprise, employee=salarie,
                         start_date=date(2026, 3, 20),
                         end_date=date(2026, 3, 10))
    with pytest.raises(ValidationError) as echec:
        arret.full_clean()
    assert 'end_date' in echec.value.error_dict


def test_une_prolongation_d_un_autre_salarie_est_refusee(entreprise):
    """Chaîner les arrêts de deux personnes rendrait les deux illisibles."""
    from django.core.exceptions import ValidationError
    un = creer_salarie(entreprise, 'Marc', 'Un')
    deux = creer_salarie(entreprise, 'Luc', 'Deux')
    initial = WorkStoppage.objects.create(
        company=entreprise, employee=un, start_date=date(2026, 3, 2),
        end_date=date(2026, 3, 9))
    suite = WorkStoppage(company=entreprise, employee=deux,
                         start_date=date(2026, 3, 10),
                         prolongation_de=initial)
    with pytest.raises(ValidationError) as echec:
        suite.full_clean()
    assert 'prolongation_de' in echec.value.error_dict


def test_une_prolongation_anterieure_a_l_arret_initial_est_refusee(
        salarie, entreprise):
    from django.core.exceptions import ValidationError
    initial = WorkStoppage.objects.create(
        company=entreprise, employee=salarie, start_date=date(2026, 3, 10),
        end_date=date(2026, 3, 17))
    suite = WorkStoppage(company=entreprise, employee=salarie,
                         start_date=date(2026, 3, 1),
                         prolongation_de=initial)
    with pytest.raises(ValidationError):
        suite.full_clean()


def test_une_prolongation_valide_passe(salarie, entreprise):
    initial = WorkStoppage.objects.create(
        company=entreprise, employee=salarie, start_date=date(2026, 3, 2),
        end_date=date(2026, 3, 9))
    suite = WorkStoppage(company=entreprise, employee=salarie,
                         start_date=date(2026, 3, 10),
                         end_date=date(2026, 3, 20),
                         prolongation_de=initial)
    suite.full_clean()
    suite.save()
    assert list(initial.prolongations.all()) == [suite]


def test_la_duree_est_inclusive(salarie, entreprise):
    """Du 10 au 10, c'est un jour, pas zéro."""
    arret = WorkStoppage.objects.create(
        company=entreprise, employee=salarie, start_date=date(2026, 3, 10),
        end_date=date(2026, 3, 10))
    assert arret.duree_jours == 1


# ── 9. Les formulaires : bornés à la VALIDATION ─────────────────────────────

def test_le_formulaire_d_arret_refuse_un_salarie_d_une_autre_entreprise(
        entreprise, autre_entreprise):
    """Le défaut que ce module corrige ailleurs, évité ici d'emblée.

    Borner la liste à l'affichage seulement laisse accepter un identifiant
    forgé : l'arrêt serait enregistré sous l'entreprise courante en
    désignant le salarié d'une autre.
    """
    from apps.hr.forms_planning import WorkStoppageForm
    etranger = creer_salarie(autre_entreprise, 'Paul', 'Externe')
    form = WorkStoppageForm(
        {'employee': etranger.pk, 'kind': 'maladie',
         'start_date': '2026-03-10'}, company=entreprise)
    assert form.is_valid() is False
    assert 'employee' in form.errors


def test_le_formulaire_d_arret_accepte_un_salarie_de_l_entreprise(
        entreprise, salarie):
    from apps.hr.forms_planning import WorkStoppageForm
    form = WorkStoppageForm(
        {'employee': salarie.pk, 'kind': 'maladie',
         'start_date': '2026-03-10'}, company=entreprise)
    assert form.is_valid() is True, form.errors


def test_le_formulaire_de_rythme_refuse_un_rythme_entierement_a_zero(
        entreprise, salarie):
    """Un rythme vide ferait passer le salarié pour disponible toute l'année."""
    from apps.hr.forms_planning import WorkScheduleForm
    donnees = {'employee': salarie.pk}
    donnees.update({f'hours_{cle}': '0' for cle in (
        'monday', 'tuesday', 'wednesday', 'thursday', 'friday',
        'saturday', 'sunday')})
    form = WorkScheduleForm(donnees, company=entreprise)
    assert form.is_valid() is False
    assert 'désactivez' in str(form.errors)


def test_le_formulaire_de_rythme_ne_propose_pas_un_salarie_deja_pourvu(
        entreprise, salarie):
    """Un rythme par salarié : le proposer mènerait à une erreur d'unicité."""
    from apps.hr.forms_planning import WorkScheduleForm
    WorkSchedule.objects.create(company=entreprise, employee=salarie)
    autre = creer_salarie(entreprise, 'Luc', 'Deux')
    form = WorkScheduleForm(company=entreprise)
    proposables = list(form.fields['employee'].queryset)
    assert salarie not in proposables
    assert autre in proposables


def test_le_salarie_d_un_rythme_existant_ne_se_change_pas(entreprise,
                                                           salarie):
    """Le déplacer reviendrait à déplacer un historique.

    Le champ est désactivé : Django ignore alors la valeur soumise et
    reprend l'initiale, donc même un POST forgé ne le déplace pas.
    """
    from apps.hr.forms_planning import WorkScheduleForm
    rythme = WorkSchedule.objects.create(company=entreprise,
                                         employee=salarie)
    autre = creer_salarie(entreprise, 'Luc', 'Deux')

    donnees = {'employee': autre.pk}
    donnees.update({f'hours_{cle}': '7' for cle in (
        'monday', 'tuesday', 'wednesday', 'thursday', 'friday')})
    donnees.update({'hours_saturday': '0', 'hours_sunday': '0'})

    form = WorkScheduleForm(donnees, instance=rythme, company=entreprise)
    assert form.is_valid() is True, form.errors
    enregistre = form.save()
    assert enregistre.employee_id == salarie.pk


# ── 10. Les vues ────────────────────────────────────────────────────────────

def test_la_grille_est_reservee_a_l_encadrement(client, entreprise, salarie):
    """Elle montre les arrêts de travail : des données de santé.

    Un salarié voit le sien sans droit particulier ; voir celui des autres
    est autre chose.
    """
    simple = creer_compte('ouvrier', role='user', company=entreprise)
    client.force_login(simple)
    reponse = client.get(reverse('hr:planning_equipe'), follow=True)
    assert reponse.redirect_chain
    assert reverse('hr:mon_planning') in reponse.redirect_chain[-1][0]


def test_un_encadrant_voit_la_grille(client, encadrant, entreprise, salarie):
    client.force_login(encadrant)
    reponse = client.get(reverse('hr:planning_equipe'))
    assert reponse.status_code == 200
    assert salarie.full_name in reponse.content.decode()


def test_un_salarie_voit_son_propre_planning(client, entreprise):
    salarie = creer_salarie(entreprise, 'Marc', 'Dupont')
    client.force_login(salarie.user)
    reponse = client.get(reverse('hr:planning_employe',
                                 args=[salarie.pk]))
    assert reponse.status_code == 200


def test_un_salarie_ne_voit_pas_le_planning_d_un_autre(client, entreprise):
    salarie = creer_salarie(entreprise, 'Marc', 'Dupont')
    autre = creer_salarie(entreprise, 'Luc', 'Deux')
    client.force_login(salarie.user)
    reponse = client.get(reverse('hr:planning_employe', args=[autre.pk]),
                         follow=True)
    assert reponse.redirect_chain


def test_le_planning_d_une_autre_entreprise_est_introuvable(
        client, encadrant, autre_entreprise):
    """404, et non 403 : l'existence du salarié ne doit pas se déduire."""
    etranger = creer_salarie(autre_entreprise, 'Paul', 'Externe')
    client.force_login(encadrant)
    reponse = client.get(reverse('hr:planning_employe',
                                 args=[etranger.pk]))
    assert reponse.status_code == 404


def test_mon_planning_explique_l_absence_de_fiche(client, entreprise):
    """Prestataire, expert externe, compte de service : cas normal.

    Renvoyer une page vide ou un 404 ferait chercher une panne.
    """
    sans_fiche = creer_compte('externe', role='user', company=entreprise)
    client.force_login(sans_fiche)
    reponse = client.get(reverse('hr:mon_planning'))
    assert reponse.status_code == 200
    assert reponse.context['sans_fiche'] is True
    assert 'pas rattaché à une fiche salarié' in reponse.content.decode()


def test_la_creation_d_un_rythme(client, encadrant, entreprise, salarie):
    client.force_login(encadrant)
    donnees = {'employee': salarie.pk, 'hours_monday': '7',
               'hours_tuesday': '7', 'hours_wednesday': '0',
               'hours_thursday': '7', 'hours_friday': '7',
               'hours_saturday': '0', 'hours_sunday': '0'}
    client.post(reverse('hr:schedule_create'), donnees)
    rythme = WorkSchedule.objects.get(employee=salarie)
    assert rythme.heures_hebdomadaires == Decimal('28')
    # L'entreprise vient du salarié, pas de la session.
    assert rythme.company_id == entreprise.pk


def test_la_declaration_d_un_arret(client, encadrant, entreprise, salarie):
    client.force_login(encadrant)
    client.post(reverse('hr:stoppage_create'), {
        'employee': salarie.pk, 'kind': 'accident_travail',
        'start_date': '2026-03-10', 'end_date': '2026-03-20'})
    arret = WorkStoppage.objects.get(employee=salarie)
    assert arret.kind == 'accident_travail'
    assert arret.declared_by == encadrant
    assert arret.company_id == entreprise.pk


def test_la_suppression_d_un_rythme_exige_un_post(client, encadrant,
                                                  entreprise, salarie):
    rythme = WorkSchedule.objects.create(company=entreprise,
                                         employee=salarie)
    client.force_login(encadrant)
    assert client.get(reverse('hr:schedule_delete',
                              args=[rythme.pk])).status_code == 405
    assert WorkSchedule.objects.filter(pk=rythme.pk).exists()


def test_un_arret_d_une_autre_entreprise_ne_se_supprime_pas(
        client, encadrant, autre_entreprise):
    etranger = creer_salarie(autre_entreprise, 'Paul', 'Externe')
    arret = WorkStoppage.objects.create(
        company=autre_entreprise, employee=etranger,
        start_date=date(2026, 3, 10))
    client.force_login(encadrant)
    reponse = client.post(reverse('hr:stoppage_delete', args=[arret.pk]))
    assert reponse.status_code == 404
    assert WorkStoppage.objects.filter(pk=arret.pk).exists()


def test_un_anonyme_ne_voit_rien(client):
    for nom in ('hr:planning_equipe', 'hr:mon_planning', 'hr:schedule_list',
                'hr:stoppage_list'):
        reponse = client.get(reverse(nom))
        assert reponse.status_code in (301, 302), nom
