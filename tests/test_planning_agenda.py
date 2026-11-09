# -*- coding: utf-8 -*-
"""Le planning de la semaine se lit comme un agenda.

L'écran listait des pastilles « 3,5 h » dans une case par salarié et par
jour. On y lisait COMBIEN, jamais QUAND, et deux journées très différentes
se ressemblaient.

CE QUE LA BASE NE CONTIENT PAS. `DedicatedTimeBlock` porte une date et une
DURÉE — pas d'heure de début. « Paul, le 12 mars, 3,5 h » ne dit pas à
quelle heure Paul commence.

La position verticale est donc CALCULÉE, à partir de ce que la fiche
salarié sait déjà : heure d'embauche, heure de fin, pause déjeuner. Les
blocs sont posés à la suite, la pause sautée.

C'est un choix, et il a une contrepartie que l'écran annonce : la hauteur
d'un bloc est sa durée réelle, mais son heure affichée est déduite et non
fixée. Un agenda qui laisserait croire à des horaires fermes alors qu'il
les devine ferait manquer un rendez-vous.

Les tests du moteur ci-dessous tournent SANS base : ce sont des calculs,
et les faire passer par des modèles n'y ajouterait que de la lenteur.
"""

from datetime import date, datetime, time
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.work_planning import calendrier


def _employe(pk=1, debut=time(9, 0), fin=time(17, 0),
             pause=(time(12, 0), time(13, 0)), couleur='#112233'):
    return SimpleNamespace(
        pk=pk,
        normal_work_start=debut,
        normal_work_end=fin,
        lunch_break_start=pause[0] if pause else None,
        lunch_break_end=pause[1] if pause else None,
        color_code=couleur,
        user=SimpleNamespace(get_full_name=lambda: 'Paul Martin',
                             username='paul'),
    )


def _bloc(employe, jour, heures, mission=None):
    return SimpleNamespace(
        pk=1, employee_id=employe.pk, date=jour,
        hours=Decimal(str(heures)), mission=mission, task=None)


LUNDI = date(2026, 3, 2)


# ─── Le découpage autour de la pause ──────────────────────────────────────

def test_une_journee_complete_est_coupee_par_le_dejeuner():
    """Sept heures depuis 9 h donnent 9 h–12 h puis 13 h–17 h.

    Dessiner le bloc d'un seul tenant le ferait traverser la bande de la
    pause, ce qui est faux : le salarié ne travaille pas pendant.
    """
    segments = calendrier._segments_du_bloc(9 * 60, 7 * 60,
                                            (12 * 60, 13 * 60))

    assert segments == [(540, 720), (780, 1020)]


def test_un_bloc_qui_tient_avant_la_pause_n_est_pas_coupe():
    assert calendrier._segments_du_bloc(
        9 * 60, 120, (12 * 60, 13 * 60)) == [(540, 660)]


def test_un_bloc_commence_pendant_la_pause_est_repousse():
    assert calendrier._segments_du_bloc(
        12 * 60 + 30, 120, (12 * 60, 13 * 60)) == [(780, 900)]


def test_sans_pause_declaree_rien_n_est_coupe():
    """La pause est facultative sur la fiche salarié."""
    assert calendrier._segments_du_bloc(
        9 * 60, 7 * 60, None) == [(540, 960)]


# ─── Les blocs simultanés se partagent la largeur ─────────────────────────

def test_deux_blocs_simultanes_se_partagent_la_largeur():
    """Sinon l'un cacherait l'autre, et un salarié disparaîtrait."""
    elements = [
        {'debut_min': 540, 'fin_min': 660},
        {'debut_min': 540, 'fin_min': 600},
    ]

    calendrier._placer_cote_a_cote(elements)

    assert {e['colonne'] for e in elements} == {0, 1}
    assert all(e['nb_colonnes'] == 2 for e in elements)


def test_un_bloc_qui_ne_chevauche_rien_reprend_la_colonne_libre():
    elements = [
        {'debut_min': 540, 'fin_min': 600},
        {'debut_min': 600, 'fin_min': 660},
    ]

    calendrier._placer_cote_a_cote(elements)

    assert [e['colonne'] for e in elements] == [0, 0], (
        'deux blocs qui se suivent ne doivent pas se partager la largeur'
    )


# ─── La grille complète ───────────────────────────────────────────────────

def test_les_blocs_d_un_salarie_s_enchainent_dans_la_journee():
    """Deux blocs le même jour : le second commence où le premier finit."""
    employe = _employe()
    blocs = [_bloc(employe, LUNDI, 2), _bloc(employe, LUNDI, 1)]

    grille = calendrier.grille_de_la_semaine(blocs, [employe], [LUNDI])
    poses = grille['jours'][0]['blocs']

    assert [(b['debut'], b['fin']) for b in poses] == [
        (time(9, 0), time(11, 0)), (time(11, 0), time(12, 0))]


def test_la_grille_s_etend_pour_montrer_les_depassements():
    """Un agenda qui s'arrête à l'heure de fin cacherait les heures sup.

    C'est-à-dire précisément ce qu'on veut voir.
    """
    employe = _employe(fin=time(17, 0))
    blocs = [_bloc(employe, LUNDI, 11)]       # 9 h + 11 h + pause -> 21 h

    grille = calendrier.grille_de_la_semaine(blocs, [employe], [LUNDI])

    assert grille['heure_max'] >= 21


def test_les_positions_restent_dans_la_grille():
    employe = _employe()
    blocs = [_bloc(employe, LUNDI, 7)]

    grille = calendrier.grille_de_la_semaine(blocs, [employe], [LUNDI])

    for pose in grille['jours'][0]['blocs']:
        assert 0 <= pose['haut_pct'] <= 100
        assert 0 < pose['hauteur_pct'] <= 100
        assert pose['haut_pct'] + pose['hauteur_pct'] <= 100.5


def test_le_total_du_jour_ne_compte_pas_deux_fois_un_bloc_coupe():
    """Un bloc coupé par la pause donne DEUX segments, une seule durée."""
    employe = _employe()
    blocs = [_bloc(employe, LUNDI, 7)]

    grille = calendrier.grille_de_la_semaine(blocs, [employe], [LUNDI])
    jour = grille['jours'][0]

    assert len(jour['blocs']) == 2
    assert jour['total_heures'] == Decimal('7')


def test_un_bloc_sans_duree_n_est_pas_dessine():
    employe = _employe()
    blocs = [_bloc(employe, LUNDI, 0)]

    grille = calendrier.grille_de_la_semaine(blocs, [employe], [LUNDI])

    assert grille['jours'][0]['blocs'] == []


def test_une_heure_de_debut_saisie_l_emporte_sur_le_calcul():
    """Le champ n'existe pas encore ; le jour où il existera, rien à changer.

    C'est la raison du `getattr` dans le moteur : la déduction est un
    pis-aller, pas une règle.
    """
    employe = _employe()
    bloc = _bloc(employe, LUNDI, 2)
    bloc.heure_debut = time(14, 30)

    grille = calendrier.grille_de_la_semaine([bloc], [employe], [LUNDI])

    assert grille['jours'][0]['blocs'][0]['debut'] == time(14, 30)


# ─── Le trait de l'heure courante ─────────────────────────────────────────

def test_le_trait_de_maintenant_se_place_au_bon_endroit():
    position = calendrier.position_de_maintenant(
        8, 18, datetime(2026, 3, 2, 13, 0))

    assert position == pytest.approx(50.0, abs=0.1)


def test_pas_de_trait_hors_des_heures_affichees():
    """La nuit, il n'y a rien à montrer."""
    assert calendrier.position_de_maintenant(
        8, 18, datetime(2026, 3, 2, 3, 0)) is None
    assert calendrier.position_de_maintenant(
        8, 18, datetime(2026, 3, 2, 23, 0)) is None


def test_la_semaine_part_du_lundi():
    semaine = calendrier.semaine_de(date(2026, 3, 5))     # un jeudi

    assert semaine[0] == date(2026, 3, 2)
    assert len(semaine) == 7
    assert semaine[-1] == date(2026, 3, 8)


# ─── L'écran ──────────────────────────────────────────────────────────────

@pytest.fixture
def ecran(client, django_user_model, db):
    """Une entreprise, un salarié, et un bloc de 7 h le lundi."""
    from django.contrib.auth import get_user_model

    from apps.core.models import Company
    from apps.work_planning.models import DedicatedTimeBlock, EmployeeProfile

    entreprise = Company.objects.create(name='Volt SARL', slug='volt-sarl')
    patron = django_user_model.objects.create_superuser(
        username='chef', password='motdepasse-test', email='chef@x.fr')
    patron.profile.companies.add(entreprise)
    patron.profile.current_company = entreprise
    patron.profile.save()

    salarie_user = get_user_model().objects.create_user(
        username='paul', password='x', first_name='Paul', last_name='Martin')
    profil = EmployeeProfile.objects.create(
        company=entreprise, user=salarie_user, color_code='#112233',
        normal_work_start=time(9, 0), normal_work_end=time(17, 0),
        lunch_break_start=time(12, 0), lunch_break_end=time(13, 0))
    DedicatedTimeBlock.objects.create(
        company=entreprise, employee=profil, date=LUNDI,
        hours=Decimal('7.0'))

    client.force_login(patron)
    return client


def _page(client, semaine='2026-03-02'):
    from django.urls import reverse

    reponse = client.get(
        reverse('work_planning:weekly_planning') + '?semaine=' + semaine)
    assert reponse.status_code == 200
    return reponse.content.decode()


@pytest.mark.django_db
def test_l_ecran_affiche_une_grille_horaire(ecran):
    contenu = _page(ecran)

    assert 'agenda-colonne' in contenu
    assert 'agenda-heure' in contenu
    assert '9:00' in contenu, 'les heures ne sont pas affichées'


@pytest.mark.django_db
def test_le_bloc_est_pose_et_coupe_par_la_pause(ecran):
    contenu = _page(ecran)

    assert contenu.count('agenda-bloc"') == 2, (
        'un bloc de 7 h doit donner deux segments autour du déjeuner')
    assert 'Paul Martin' in contenu
    assert '#112233' in contenu, 'la couleur du salarié manque'


@pytest.mark.django_db
def test_l_ecran_dit_que_l_heure_est_calculee(ecran):
    """L'honnêteté de cet écran tient à cette phrase.

    Sans elle, un agenda qui déduit ses horaires laisse croire à des
    rendez-vous fixés.
    """
    contenu = _page(ecran)

    assert 'calculée' in contenu
    assert "heure d'embauche" in contenu


@pytest.mark.django_db
def test_le_trait_de_maintenant_n_apparait_pas_sur_une_autre_semaine(ecran):
    """Le tracer sur une semaine passée n'aurait aucun sens."""
    contenu = _page(ecran, semaine='2026-03-02')

    # `class="..."` et non le simple nom : « agenda-maintenant » figure
    # aussi dans la feuille de style, donc toujours présent dans la page.
    # Première version de ce test : elle ne pouvait pas passer, et c'est
    # elle qui avait tort.
    assert 'class="agenda-maintenant"' not in contenu


@pytest.mark.django_db
def test_sans_salarie_l_ecran_le_dit_autrement(client, django_user_model):
    """Deux vides très différents, et les confondre fait chercher au
    mauvais endroit."""
    from django.urls import reverse

    from apps.core.models import Company

    entreprise = Company.objects.create(name='Volt SARL', slug='volt-sarl')
    patron = django_user_model.objects.create_superuser(
        username='chef', password='motdepasse-test', email='chef@x.fr')
    patron.profile.companies.add(entreprise)
    patron.profile.current_company = entreprise
    patron.profile.save()
    client.force_login(patron)

    contenu = client.get(
        reverse('work_planning:weekly_planning')).content.decode()

    assert 'Aucun employé' in contenu
