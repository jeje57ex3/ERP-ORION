"""Les quatre granularités du planning, et la couleur qui le rendait illisible.

**Le défaut corrigé.** La grille écrivait
`background: var(--orion-card, #1b1b1f)` sur la colonne des noms. Or
`--orion-card` **n'existe nulle part** dans le système de design — la vraie
variable est `--orion-surface`. Le repli `#1b1b1f` s'appliquait donc
toujours : une cellule quasi noire, sous un texte qui héritait de
`--orion-text` (`#1f1b18` en thème clair). Noir sur noir, et les noms des
salariés illisibles. Les états souffraient du même mal : des pastels et un
`rgba(255,255,255,.35)` pensés pour un fond sombre, alors que le thème
**clair** est celui par défaut (`[data-theme="dark"]` est l'exception).

Une faute de frappe dans un nom de variable CSS ne lève rien, ne casse
aucun test fonctionnel, et produit silencieusement une page illisible. D'où
le garde-fou de la première section : **toute variable CSS citée par un
gabarit de planning doit être définie quelque part.**

**Les quatre vues.** Mois, semaine, jour, heure — une seule lecture
(`planning_intervalle`), quatre jeux de bornes. Quatre fonctions de lecture
auraient divergé à la première correction, et le même salarié serait
apparu en congé dans une vue et au travail dans une autre ; un test le
vérifie explicitement.

**Ce que la frise horaire ne peut pas montrer.** Le pointage est un total
déclaré par jour : il ne porte aucune heure d'horloge. La frise place donc
le *prévu*, lu sur le rythme. Les heures pointées sont un nombre, jamais
posé sur l'horloge — elles donneraient une précision qui n'existe pas.
"""

import os
import re
from datetime import date, time
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from apps.accounts.models import UserProfile
from apps.hr.models import Employee, LeaveRequest, WorkSchedule, WorkStoppage
from apps.hr.planning_service import (
    HEURE_FRISE_DEBUT,
    HEURE_FRISE_FIN,
    VUES,
    bornes_de_la_vue,
    creneau_prevu,
    heures_de_la_frise,
    lundi_de_la_semaine,
    pas_de_la_vue,
    planning_intervalle,
    position_sur_la_frise,
)

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── 1. Le garde-fou des couleurs ────────────────────────────────────────────

def test_toute_variable_css_citee_est_definie():
    """Une faute de frappe dans un nom de variable CSS ne lève rien.

    `var(--orion-card)` était simplement inconnue : le navigateur appliquait
    le repli, ici un quasi-noir, et la page devenait illisible sans qu'aucun
    test ne s'en aperçoive. Ce contrôle attrape la classe entière du défaut.
    """
    dossier = os.path.join(RACINE, 'templates', 'hr', 'planning')
    motif_usage = re.compile(r'var\(\s*(--[a-z0-9-]+)')
    motif_definition = re.compile(r'(--[a-z0-9-]+)\s*:')

    definies = set()
    for relatif in (os.path.join('static', 'css', 'orion-design-system.css'),
                    os.path.join('templates', 'hr', 'planning',
                                 '_palette.html')):
        chemin = os.path.join(RACINE, relatif)
        if os.path.isfile(chemin):
            with open(chemin, encoding='utf-8', errors='replace') as flux:
                definies.update(motif_definition.findall(flux.read()))

    inconnues = []
    for fichier in sorted(os.listdir(dossier)):
        if not fichier.endswith('.html'):
            continue
        chemin = os.path.join(dossier, fichier)
        with open(chemin, encoding='utf-8', errors='replace') as flux:
            contenu = flux.read()
        # Le commentaire d'en-tête de _palette.html cite volontairement le
        # nom fautif pour expliquer le défaut : on ne lit donc que ce qui
        # suit la balise <style>.
        position = contenu.find('<style')
        zone = contenu[position:] if position != -1 else contenu
        for nom in motif_usage.findall(zone):
            if nom not in definies:
                inconnues.append(f'{fichier} → {nom}')

    assert not inconnues, (
        'Variables CSS citées mais définies nulle part — le navigateur '
        'appliquera le repli, et la page peut devenir illisible sans qu\'aucun '
        'test ne le voie :\n  ' + '\n  '.join(sorted(set(inconnues))))


def test_la_palette_couvre_les_deux_themes():
    """Le thème CLAIR est celui par défaut, et c'est là que tout cassait.

    `[data-theme="dark"]` est l'exception. Une palette pensée pour le
    sombre seul produit exactement le défaut corrigé.
    """
    chemin = os.path.join(RACINE, 'templates', 'hr', 'planning',
                          '_palette.html')
    with open(chemin, encoding='utf-8') as flux:
        contenu = flux.read()

    etats = ('travaille', 'repos', 'conge', 'maladie', 'arret')
    # On part de <style> : le commentaire d'en-tête cite lui aussi
    # « [data-theme="dark"] » pour expliquer le défaut, et découper dessus
    # mettrait tout le CSS du côté « sombre ».
    css = contenu[contenu.index('<style'):]
    clair, sombre = css.split('[data-theme="dark"]', 1)

    for etat in etats:
        for face in ('fond', 'texte'):
            variable = f'--pl-{etat}-{face}:'
            assert variable in clair, f'{variable} absente du thème clair'
            assert variable in sombre, f'{variable} absente du thème sombre'


def test_aucune_couleur_en_dur_dans_les_grilles():
    """Les couleurs vivent dans la palette, pas dans les grilles.

    Une couleur écrite en dur dans un gabarit échappe à la correction de
    thème : c'est ainsi que `rgba(255,255,255,.35)` s'est retrouvé en texte
    blanc sur fond clair.
    """
    motif = re.compile(r'rgba\(\s*255\s*,\s*255\s*,\s*255')
    for fichier in ('equipe.html', 'heures.html'):
        chemin = os.path.join(RACINE, 'templates', 'hr', 'planning', fichier)
        with open(chemin, encoding='utf-8') as flux:
            contenu = flux.read()
        assert not motif.search(contenu), (
            f'{fichier} écrit du blanc en dur : illisible en thème clair.')


# ── Terrain ─────────────────────────────────────────────────────────────────

pytestmark = pytest.mark.django_db


@pytest.fixture
def entreprise(db):
    from apps.core.models import Company
    return Company.objects.create(name='Dupont SA', slug='dupont-sa')


def creer_compte(nom, role='user', company=None):
    utilisateur = User.objects.create_user(username=nom, password='x')
    profil, _ = UserProfile.objects.get_or_create(user=utilisateur)
    profil.role = role
    profil.save()
    if company is not None:
        profil.companies.add(company)
    return User.objects.get(pk=utilisateur.pk)


def creer_salarie(company, prenom='Marc', nom='Dupont'):
    return Employee.objects.create(
        company=company, first_name=prenom, last_name=nom,
        user=creer_compte(f'{prenom}.{nom}'.lower(), company=company),
        is_active=True)


@pytest.fixture
def salarie(entreprise):
    return creer_salarie(entreprise)


@pytest.fixture
def encadrant(entreprise):
    return creer_compte('patron', role='admin', company=entreprise)


# ── 2. Les bornes de chaque vue ─────────────────────────────────────────────

def test_bornes_de_la_vue_mois():
    debut, fin = bornes_de_la_vue('mois', date(2026, 3, 17))
    assert (debut, fin) == (date(2026, 3, 1), date(2026, 3, 31))


def test_bornes_de_la_vue_semaine():
    """17 mars 2026 est un mardi : la semaine va du lundi 16 au dimanche 22.

    La semaine commence le LUNDI, comme le veut l'usage français. Partir du
    dimanche décalerait tout le planning d'un jour par rapport à la façon
    dont les équipes parlent de leur semaine.
    """
    debut, fin = bornes_de_la_vue('semaine', date(2026, 3, 17))
    assert (debut, fin) == (date(2026, 3, 16), date(2026, 3, 22))
    assert debut.weekday() == 0
    assert fin.weekday() == 6


@pytest.mark.parametrize('vue', ['jour', 'heure'])
def test_bornes_d_une_vue_d_un_seul_jour(vue):
    jour = date(2026, 3, 17)
    assert bornes_de_la_vue(vue, jour) == (jour, jour)


def test_une_semaine_qui_enjambe_deux_mois(entreprise, salarie):
    """Le 1er avril 2026 est un mercredi : la semaine commence en mars.

    Une vue semaine qui se limiterait au mois courant couperait la semaine
    en deux et ferait disparaître trois jours.
    """
    debut, fin = bornes_de_la_vue('semaine', date(2026, 4, 1))
    assert debut == date(2026, 3, 30)
    assert fin == date(2026, 4, 5)
    planning = planning_intervalle(entreprise, debut, fin, vue='semaine')
    assert len(planning['dates']) == 7


@pytest.mark.parametrize('jour,lundi', [
    (date(2026, 3, 16), date(2026, 3, 16)),   # un lundi
    (date(2026, 3, 22), date(2026, 3, 16)),   # un dimanche
    (date(2026, 1, 1), date(2025, 12, 29)),   # franchit l'année
])
def test_lundi_de_la_semaine(jour, lundi):
    assert lundi_de_la_semaine(jour) == lundi


def test_le_pas_suit_la_vue():
    """Avancer d'un jour en vue mois demanderait trente clics."""
    assert pas_de_la_vue('mois') is None      # durée variable, traitée à part
    assert pas_de_la_vue('semaine').days == 7
    assert pas_de_la_vue('jour').days == 1
    assert pas_de_la_vue('heure').days == 1


# ── 3. Le créneau prévu ─────────────────────────────────────────────────────

def test_le_creneau_part_de_l_heure_de_debut_et_ajoute_la_pause(entreprise,
                                                                 salarie):
    """7 h de travail + 1 h de pause depuis 8 h → 8 h 00 – 16 h 00."""
    rythme = WorkSchedule.objects.create(
        company=entreprise, employee=salarie,
        heure_debut=time(8, 0), pause_minutes=60)
    creneau = creneau_prevu(rythme, date(2026, 3, 16))  # un lundi
    assert creneau['debut'].time() == time(8, 0)
    assert creneau['fin'].time() == time(16, 0)
    assert creneau['heures'] == Decimal('7')
    assert creneau['pause_minutes'] == 60


def test_une_pause_nulle_raccourcit_la_journee(entreprise, salarie):
    rythme = WorkSchedule.objects.create(
        company=entreprise, employee=salarie,
        heure_debut=time(7, 30), pause_minutes=0)
    creneau = creneau_prevu(rythme, date(2026, 3, 16))
    assert creneau['fin'].time() == time(14, 30)


def test_une_demi_journee_donne_un_creneau_court(entreprise, salarie):
    rythme = WorkSchedule.objects.create(
        company=entreprise, employee=salarie,
        hours_friday=Decimal('3.5'), heure_debut=time(8, 0),
        pause_minutes=0)
    creneau = creneau_prevu(rythme, date(2026, 3, 20))  # un vendredi
    assert creneau['fin'].time() == time(11, 30)


def test_un_jour_de_repos_n_a_pas_de_creneau(entreprise, salarie):
    """Il n'y a pas d'horaire à placer, et en inventer un afficherait une
    présence prévue un jour où personne ne vient."""
    rythme = WorkSchedule.objects.create(company=entreprise,
                                         employee=salarie)
    assert creneau_prevu(rythme, date(2026, 3, 15)) is None   # dimanche


def test_sans_rythme_le_creneau_est_une_hypothese(salarie):
    """8 h de début, 7 h de travail : raisonnable, et signalé par l'interface."""
    creneau = creneau_prevu(None, date(2026, 3, 16))
    assert creneau['debut'].time() == time(8, 0)
    assert creneau['heures'] == Decimal('7')
    assert creneau_prevu(None, date(2026, 3, 15)) is None      # week-end


# ── 4. La position sur la frise ─────────────────────────────────────────────

def test_la_frise_couvre_la_journee_de_chantier():
    heures = heures_de_la_frise()
    assert heures[0] == HEURE_FRISE_DEBUT == 6
    assert heures[-1] == HEURE_FRISE_FIN == 20


def test_un_creneau_de_8h_a_16h_se_place_au_milieu(entreprise, salarie):
    """Frise 6 h – 20 h, soit 14 h. De 8 h à 16 h : 2/14 à gauche, 8/14 large."""
    rythme = WorkSchedule.objects.create(
        company=entreprise, employee=salarie,
        heure_debut=time(8, 0), pause_minutes=60)
    frise = position_sur_la_frise(creneau_prevu(rythme, date(2026, 3, 16)))
    assert frise['gauche'] == pytest.approx(2 * 100 / 14, abs=0.05)
    assert frise['largeur'] == pytest.approx(8 * 100 / 14, abs=0.05)
    assert frise['coupe_avant'] is False
    assert frise['coupe_apres'] is False


def test_un_depart_avant_six_heures_est_coupe_pas_deborde(entreprise,
                                                           salarie):
    """Un bloc qui déborde sort de la piste et chevauche les voisins.

    Il est donc coupé à 6 h, et l'information « ça commence avant » est
    conservée séparément pour que le gabarit puisse le dire.
    """
    rythme = WorkSchedule.objects.create(
        company=entreprise, employee=salarie,
        heure_debut=time(4, 0), pause_minutes=0)
    frise = position_sur_la_frise(creneau_prevu(rythme, date(2026, 3, 16)))
    assert frise['gauche'] == 0
    assert frise['coupe_avant'] is True
    # 4 h + 7 h = 11 h ; visible de 6 h à 11 h, soit 5/14
    assert frise['largeur'] == pytest.approx(5 * 100 / 14, abs=0.05)


def test_une_fin_apres_vingt_heures_est_coupee(entreprise, salarie):
    rythme = WorkSchedule.objects.create(
        company=entreprise, employee=salarie,
        heure_debut=time(16, 0), pause_minutes=0)
    frise = position_sur_la_frise(creneau_prevu(rythme, date(2026, 3, 16)))
    assert frise['coupe_apres'] is True
    assert frise['gauche'] + frise['largeur'] == pytest.approx(100, abs=0.05)


def test_un_creneau_entierement_hors_frise_ne_rend_rien(entreprise, salarie):
    """Une équipe de nuit : rien à afficher sur une frise 6 h – 20 h.

    Rendre un bloc de largeur nulle laisserait un artefact de un pixel qu'on
    prendrait pour une donnée.
    """
    rythme = WorkSchedule.objects.create(
        company=entreprise, employee=salarie,
        heure_debut=time(21, 0), pause_minutes=0)
    assert position_sur_la_frise(creneau_prevu(rythme, date(2026, 3, 16))) is None


def test_sans_creneau_pas_de_position():
    assert position_sur_la_frise(None) is None


# ── 5. Les cellules portent le créneau, et seulement quand il a un sens ─────

def test_un_jour_travaille_porte_son_creneau(entreprise, salarie):
    WorkSchedule.objects.create(company=entreprise, employee=salarie,
                                heure_debut=time(8, 0))
    jour = date(2026, 3, 16)
    case = planning_intervalle(entreprise, jour, jour,
                               vue='jour')['lignes'][0]['cellules'][0]
    assert case['creneau'] is not None
    assert case['frise'] is not None


@pytest.mark.parametrize('fabrique,etat', [
    ('conge', 'conge'), ('arret', 'arret'),
])
def test_un_jour_d_absence_ne_porte_aucun_creneau(entreprise, salarie,
                                                   fabrique, etat):
    """Sinon la frise afficherait une présence prévue un jour d'arrêt.

    Le créneau n'est calculé que pour un jour réellement travaillé.
    """
    WorkSchedule.objects.create(company=entreprise, employee=salarie)
    jour = date(2026, 3, 16)
    if fabrique == 'conge':
        LeaveRequest.objects.create(
            company=entreprise, employee=salarie, leave_type='paid',
            start_date=jour, end_date=jour, status='approved')
    else:
        WorkStoppage.objects.create(
            company=entreprise, employee=salarie, kind='maladie',
            start_date=jour, end_date=jour)

    case = planning_intervalle(entreprise, jour, jour,
                               vue='heure')['lignes'][0]['cellules'][0]
    assert case['etat'] == etat
    assert case['creneau'] is None
    assert case['frise'] is None


# ── 6. Les quatre vues disent la même chose ─────────────────────────────────

def test_les_quatre_vues_s_accordent_sur_un_meme_jour(entreprise, salarie):
    """Une seule lecture derrière les quatre granularités.

    Quatre fonctions auraient divergé à la première correction, et le même
    salarié serait apparu en congé dans une vue et au travail dans une
    autre.
    """
    WorkSchedule.objects.create(company=entreprise, employee=salarie)
    jour = date(2026, 3, 18)
    WorkStoppage.objects.create(
        company=entreprise, employee=salarie, kind='accident_travail',
        start_date=jour, end_date=jour)

    etats = set()
    for vue in VUES:
        debut, fin = bornes_de_la_vue(vue, jour)
        planning = planning_intervalle(entreprise, debut, fin, vue=vue)
        case = next(c for c in planning['lignes'][0]['cellules']
                    if c['date'] == jour)
        etats.add(case['etat'])
    assert etats == {'arret'}


def test_le_nombre_de_requetes_ne_depend_pas_de_la_vue(
        entreprise, django_assert_num_queries):
    """Cinq requêtes, que l'intervalle fasse un jour ou trente-et-un."""
    for index in range(5):
        creer_salarie(entreprise, f'Sal{index}', f'Nom{index}')

    for vue in VUES:
        debut, fin = bornes_de_la_vue(vue, date(2026, 3, 17))
        with django_assert_num_queries(5):
            planning_intervalle(entreprise, debut, fin, vue=vue)


# ── 7. Les écrans ───────────────────────────────────────────────────────────

@pytest.mark.parametrize('vue', ['mois', 'semaine', 'jour', 'heure'])
def test_chaque_vue_s_affiche(client, encadrant, entreprise, salarie, vue):
    WorkSchedule.objects.create(company=entreprise, employee=salarie)
    client.force_login(encadrant)
    reponse = client.get(reverse('hr:planning_equipe'),
                         {'vue': vue, 'date': '2026-03-17'})
    assert reponse.status_code == 200
    assert salarie.full_name in reponse.content.decode()
    assert reponse.context['nav']['vue'] == vue


@pytest.mark.parametrize('valeur', ['xyz', '', 'MOIS', 'semaines', '../../'])
def test_une_vue_inconnue_retombe_sur_le_mois(client, encadrant, salarie,
                                               valeur):
    """?vue=xyz est une URL mal tapée, pas une panne."""
    client.force_login(encadrant)
    reponse = client.get(reverse('hr:planning_equipe'), {'vue': valeur})
    assert reponse.status_code == 200
    attendu = 'mois' if valeur.lower() not in VUES else valeur.lower()
    assert reponse.context['nav']['vue'] == attendu


@pytest.mark.parametrize('valeur', ['pas-une-date', '2026-13-45', '2026-02',
                                    '', 'null'])
def test_une_date_de_travers_ne_casse_pas_la_page(client, encadrant, salarie,
                                                   valeur):
    client.force_login(encadrant)
    reponse = client.get(reverse('hr:planning_equipe'),
                         {'vue': 'jour', 'date': valeur})
    assert reponse.status_code == 200


def test_les_anciens_liens_annee_mois_fonctionnent_encore(client, encadrant,
                                                           salarie):
    """Des liens ont déjà pu être mis en favori ou envoyés.

    Changer la forme de l'URL les casserait sans rien apporter.
    """
    client.force_login(encadrant)
    reponse = client.get(reverse('hr:planning_equipe'),
                         {'annee': '2025', 'mois': '7'})
    assert reponse.status_code == 200
    assert reponse.context['planning']['debut'] == date(2025, 7, 1)


def test_la_vue_heure_utilise_son_propre_gabarit(client, encadrant, salarie):
    """Son tableau n'a rien de commun avec la grille.

    Au-delà d'une journée, les blocs deviendraient des traits de deux
    pixels et ne diraient plus rien.
    """
    client.force_login(encadrant)
    reponse = client.get(reverse('hr:planning_equipe'),
                         {'vue': 'heure', 'date': '2026-03-17'})
    noms = [gabarit.name for gabarit in reponse.templates if gabarit.name]
    assert 'hr/planning/heures.html' in noms
    assert 'hr/planning/equipe.html' not in noms


def test_la_frise_annonce_ce_qu_elle_ne_sait_pas(client, encadrant,
                                                  entreprise, salarie):
    """Une frise qui suggère « arrivé à 8 h 02 » sans l'avoir mesuré est
    pire qu'une absence de frise."""
    WorkSchedule.objects.create(company=entreprise, employee=salarie)
    client.force_login(encadrant)
    corps = client.get(reverse('hr:planning_equipe'),
                       {'vue': 'heure', 'date': '2026-03-17'}).content.decode()
    assert 'total déclaré par jour' in corps
    assert 'badgeage' in corps


def test_la_vue_semaine_affiche_sept_colonnes(client, encadrant, entreprise,
                                               salarie):
    client.force_login(encadrant)
    reponse = client.get(reverse('hr:planning_equipe'),
                         {'vue': 'semaine', 'date': '2026-03-17'})
    assert len(reponse.context['planning']['dates']) == 7


def test_les_fleches_portent_une_date_complete(client, encadrant, salarie):
    """Une URL de planning doit pouvoir être copiée et désigner la même
    période. Un décalage relatif dépendrait de la date du jour."""
    client.force_login(encadrant)
    reponse = client.get(reverse('hr:planning_equipe'),
                         {'vue': 'semaine', 'date': '2026-03-17'})
    nav = reponse.context['nav']
    assert nav['precedente'] == date(2026, 3, 9)
    assert nav['suivante'] == date(2026, 3, 23)


def test_les_fleches_de_la_vue_mois_avancent_d_un_mois(client, encadrant,
                                                        salarie):
    client.force_login(encadrant)
    nav = client.get(reverse('hr:planning_equipe'),
                     {'vue': 'mois', 'date': '2026-03-17'}).context['nav']
    assert nav['precedente'] == date(2026, 2, 1)
    assert nav['suivante'] == date(2026, 4, 1)


def test_un_rythme_s_enregistre_sans_preciser_l_horaire(entreprise, salarie):
    """Les deux nouveaux champs retombent sur le défaut du modèle.

    Les laisser obligatoires faisait échouer l'enregistrement de qui vide
    la case de pause — là où le défaut est la réponse évidente — et
    cassait tout appel qui ne les transmet pas. Le formulaire non lié est
    de toute façon pré-rempli, donc rien ne change à l'écran.
    """
    from apps.hr.forms_planning import WorkScheduleForm

    donnees = {'employee': salarie.pk}
    donnees.update({f'hours_{cle}': '7' for cle in (
        'monday', 'tuesday', 'wednesday', 'thursday', 'friday')})
    donnees.update({'hours_saturday': '0', 'hours_sunday': '0'})

    form = WorkScheduleForm(donnees, company=entreprise)
    assert form.is_valid() is True, form.errors

    rythme = form.save(commit=False)
    rythme.company = entreprise
    rythme.save()
    assert rythme.heure_debut == time(8, 0)
    assert rythme.pause_minutes == 60


def test_une_pause_a_zero_est_respectee(entreprise, salarie):
    """Zéro n'est pas « vide » : une équipe sans pause doit pouvoir le dire.

    Confondre les deux appliquerait une heure de pause à qui n'en prend
    pas, et décalerait sa fin de journée sur la frise.
    """
    from apps.hr.forms_planning import WorkScheduleForm

    donnees = {'employee': salarie.pk, 'heure_debut': '06:30',
               'pause_minutes': '0'}
    donnees.update({f'hours_{cle}': '7' for cle in (
        'monday', 'tuesday', 'wednesday', 'thursday', 'friday')})
    donnees.update({'hours_saturday': '0', 'hours_sunday': '0'})

    form = WorkScheduleForm(donnees, company=entreprise)
    assert form.is_valid() is True, form.errors
    rythme = form.save(commit=False)
    assert rythme.pause_minutes == 0
    assert rythme.heure_debut == time(6, 30)


def test_les_noms_ne_sont_plus_sur_fond_noir(client, encadrant, salarie):
    """Régression mesurée.

    La colonne des noms portait `var(--orion-card, #1b1b1f)` : variable
    inexistante, repli quasi noir, texte sombre hérité. Noir sur noir.
    """
    client.force_login(encadrant)
    corps = client.get(reverse('hr:planning_equipe')).content.decode()
    assert '#1b1b1f' not in corps
    assert '--pl-nom-fond' in corps
    assert 'var(--orion-surface)' in corps
