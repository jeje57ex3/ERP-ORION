"""
apps/hr/planning_service.py — Le planning, assemblé depuis ce qui existe déjà

Ce module ne stocke rien. Il LIT quatre sources et les superpose jour par
jour :

- le rythme hebdomadaire (`hr.WorkSchedule`) → heures prévues, jours de repos
- les congés et la maladie (`hr.LeaveRequest`) → déjà en place, circuit
  d'approbation inclus
- les arrêts de travail (`hr.WorkStoppage`)
- les heures pointées (`btp.BTPTimesheet`)

Aucune de ces données n'est recopiée ici. Un second endroit pour déclarer un
congé, c'est un congé sur deux qui manque quelque part : le planning serait
faux la moitié du temps, et personne ne saurait laquelle.

**Une jointure à connaître.** `LeaveRequest.employee` et
`WorkStoppage.employee` désignent un `hr.Employee` ; `BTPTimesheet.employee`
désigne un `auth.User`. Et `Employee.user` est facultatif. Un salarié sans
compte utilisateur n'a donc aucune heure pointée — ce n'est pas une erreur de
lecture, c'est la structure, et le planning le dit au lieu d'afficher une
colonne vide inexpliquée (`sans_compte` sur chaque ligne d'équipe).

**Les requêtes sont groupées.** Pour vingt salariés sur trente jours, une
lecture par salarié et par jour ferait 600 requêtes par écran. Tout est donc
chargé en bloc puis réparti en mémoire : quatre requêtes, quel que soit le
nombre de salariés.
"""

import calendar
from collections import defaultdict
from datetime import date
from decimal import Decimal

ZERO = Decimal('0')

# Ordre de priorité de l'état d'une journée. Un arrêt de travail passe
# devant tout : on n'est pas « en congé » pendant un arrêt, et afficher le
# congé masquerait le fait médical, qui est celui qui compte pour la paie
# comme pour le remplacement sur le chantier.
ETATS = ('arret', 'conge', 'maladie', 'repos', 'travaille')

LIBELLES_ETAT = {
    'arret': 'Arrêt de travail',
    'conge': 'Congé',
    'maladie': 'Maladie',
    'repos': 'Repos',
    'travaille': 'Travaillé',
}

# Un congé refusé ou annulé ne doit PAS apparaître au planning : il
# n'empêche personne de travailler. En attente, si — c'est précisément
# l'information dont le responsable a besoin avant d'engager la semaine.
STATUTS_CONGE_VISIBLES = ('approved', 'pending')


def bornes_du_mois(annee, mois):
    """Premier et dernier jour du mois. Retourne (debut, fin)."""
    dernier = calendar.monthrange(annee, mois)[1]
    return date(annee, mois, 1), date(annee, mois, dernier)


def _jours_entre(debut, fin):
    from datetime import timedelta
    jour = debut
    while jour <= fin:
        yield jour
        jour += timedelta(days=1)


def _etat_du_jour(repos, conges, arrets):
    if arrets:
        return 'arret'
    for conge in conges:
        if conge.leave_type == 'sick':
            return 'maladie'
    if conges:
        return 'conge'
    return 'repos' if repos else 'travaille'


def planning_du_mois(employee, annee, mois, schedule=None):
    """Le mois d'UN salarié, jour par jour.

    `schedule` permet à l'appelant qui a déjà chargé les rythmes (vue
    d'équipe) de ne pas les relire ; sinon il est lu ici.

    Retourne {'debut', 'fin', 'jours': [cellule…], 'totaux': {…}}.
    """
    from apps.btp.models import BTPTimesheet
    from .models import LeaveRequest, WorkSchedule, WorkStoppage

    debut, fin = bornes_du_mois(annee, mois)

    if schedule is None:
        schedule = WorkSchedule.objects.filter(employee=employee).first()

    # Un congé ou un arrêt qui ENJAMBE le mois doit apparaître : d'où les
    # bornes croisées plutôt qu'un simple start_date__month. Filtrer sur le
    # mois de début ferait disparaître du planning de février un arrêt
    # commencé le 28 janvier — exactement celui qu'il faut voir.
    conges = list(LeaveRequest.objects.filter(
        employee=employee, status__in=STATUTS_CONGE_VISIBLES,
        start_date__lte=fin, end_date__gte=debut))

    arrets = list(WorkStoppage.objects.filter(employee=employee,
                                              start_date__lte=fin))
    # Une fin nulle signifie « en cours » : impossible à exprimer dans le
    # filtre ci-dessus sans exclure ce cas, le tri se fait donc en Python.
    arrets = [a for a in arrets if a.end_date is None or a.end_date >= debut]

    pointages = []
    if employee.user_id:
        pointages = list(
            BTPTimesheet.objects.filter(
                employee_id=employee.user_id,
                work_date__gte=debut, work_date__lte=fin)
            .select_related('project'))

    par_jour_conge = defaultdict(list)
    for conge in conges:
        for jour in _jours_entre(max(conge.start_date, debut),
                                 min(conge.end_date, fin)):
            par_jour_conge[jour].append(conge)

    par_jour_arret = defaultdict(list)
    for arret in arrets:
        borne_fin = min(arret.end_date, fin) if arret.end_date else fin
        for jour in _jours_entre(max(arret.start_date, debut), borne_fin):
            par_jour_arret[jour].append(arret)

    par_jour_pointage = defaultdict(list)
    for pointage in pointages:
        par_jour_pointage[pointage.work_date].append(pointage)

    jours = []
    totaux = {
        'heures_prevues': ZERO, 'heures_pointees': ZERO,
        'heures_sup': ZERO, 'jours_conge': 0, 'jours_arret': 0,
        'jours_repos': 0, 'jours_travailles': 0,
    }

    for jour in _jours_entre(debut, fin):
        repos = schedule.est_jour_de_repos(jour) if schedule else jour.weekday() >= 5
        prevues = schedule.heures_du_jour(jour) if schedule else (
            ZERO if repos else Decimal('7'))

        du_jour = par_jour_pointage[jour]
        pointees = sum((Decimal(p.hours or 0) for p in du_jour), ZERO)
        sup = sum((Decimal(p.overtime_hours or 0) for p in du_jour), ZERO)

        conges_jour = par_jour_conge[jour]
        arrets_jour = par_jour_arret[jour]
        etat = _etat_du_jour(repos, conges_jour, arrets_jour)

        # Les heures prévues d'un jour d'absence ne sont pas « prévues » :
        # les compter gonflerait l'écart entre prévu et pointé d'un mois
        # entier de congés, et ferait passer un salarié en vacances pour un
        # salarié en retard sur ses heures.
        prevues_retenues = ZERO if etat in ('arret', 'conge', 'maladie') else prevues

        jours.append({
            'date': jour,
            'etat': etat,
            'libelle_etat': LIBELLES_ETAT[etat],
            'repos': repos,
            'heures_prevues': prevues_retenues,
            'heures_pointees': pointees,
            'heures_sup': sup,
            'conges': conges_jour,
            'arrets': arrets_jour,
            'pointages': du_jour,
            'ecart': pointees - prevues_retenues,
        })

        totaux['heures_prevues'] += prevues_retenues
        totaux['heures_pointees'] += pointees
        totaux['heures_sup'] += sup
        if etat == 'arret':
            totaux['jours_arret'] += 1
        elif etat in ('conge', 'maladie'):
            totaux['jours_conge'] += 1
        elif etat == 'repos':
            totaux['jours_repos'] += 1
        else:
            totaux['jours_travailles'] += 1

    totaux['ecart'] = totaux['heures_pointees'] - totaux['heures_prevues']

    return {
        'debut': debut, 'fin': fin, 'employee': employee,
        'schedule': schedule, 'jours': jours, 'totaux': totaux,
        'sans_compte': not employee.user_id,
    }


def planning_employe_vide(annee, mois):
    """Un planning de la même forme, mais sans salarié.

    Sert au compte qui n'a pas de fiche salarié — prestataire, expert
    externe, compte de service. Le gabarit reçoit alors exactement les
    mêmes clés et n'a pas à savoir que le cas existe : sans cela, chaque
    accès à `planning.totaux` dans le gabarit deviendrait une condition, et
    l'oubli d'une seule rendrait la page blanche.
    """
    debut, fin = bornes_du_mois(annee, mois)
    return {
        'debut': debut, 'fin': fin, 'employee': None, 'schedule': None,
        'jours': [],
        'totaux': {
            'heures_prevues': ZERO, 'heures_pointees': ZERO,
            'heures_sup': ZERO, 'jours_conge': 0, 'jours_arret': 0,
            'jours_repos': 0, 'jours_travailles': 0, 'ecart': ZERO,
        },
        'sans_compte': False,
    }


# ─── Les quatre granularités ─────────────────────────────────────────────────
#
# Mois, semaine, jour, heure : QUATRE vues, UNE lecture. Toutes passent par
# planning_intervalle(), et ne diffèrent que par les bornes qu'elles lui
# donnent. Quatre fonctions de lecture auraient diverge a la premiere
# correction, et le meme salarie serait apparu en conge dans une vue et au
# travail dans une autre.

VUES = ('mois', 'semaine', 'jour', 'heure')

LIBELLES_VUE = {
    'mois': 'Mois', 'semaine': 'Semaine', 'jour': 'Jour', 'heure': 'Heure',
}

# Plage affichee par la frise horaire. 6 h - 20 h couvre une journee de
# chantier, y compris les departs tot et les fins tardives, sans ecraser la
# frise en quatorze colonnes illisibles.
HEURE_FRISE_DEBUT = 6
HEURE_FRISE_FIN = 20


def lundi_de_la_semaine(jour):
    """Le lundi de la semaine contenant `jour`.

    La semaine commence le lundi, comme le veut l'usage francais (ISO
    8601). Partir du dimanche decalerait tout le planning d'un jour par
    rapport a la facon dont les equipes parlent de leur semaine.
    """
    from datetime import timedelta
    return jour - timedelta(days=jour.weekday())


def bornes_de_la_vue(vue, ancre):
    """Les bornes a afficher pour cette vue, autour de cette date.

    `ancre` est la date de reference : le mois qui la contient, la semaine
    qui la contient, ou elle-meme.
    """
    from datetime import timedelta
    if vue == 'mois':
        return bornes_du_mois(ancre.year, ancre.month)
    if vue == 'semaine':
        lundi = lundi_de_la_semaine(ancre)
        return lundi, lundi + timedelta(days=6)
    # jour et heure portent sur une seule date.
    return ancre, ancre


def pas_de_la_vue(vue):
    """De combien avancent les fleches « precedent / suivant ».

    Un pas de vue : un mois en vue mois, une semaine en vue semaine, un
    jour pour les deux dernieres. Avancer d'un jour en vue mois obligerait
    a cliquer trente fois pour changer de mois.
    """
    from datetime import timedelta
    if vue == 'mois':
        return None  # traite a part : les mois n'ont pas une duree fixe
    return timedelta(days=7 if vue == 'semaine' else 1)


def creneau_prevu(schedule, jour):
    """Le créneau de présence prévu : (début, fin, heures), ou None.

    Honnêteté de la frise horaire : le POINTAGE ne porte aucune heure
    d'horloge — c'est un total déclaré par jour, et c'est un choix assumé.
    La seule chose qu'on puisse placer sur une frise est donc le PRÉVU, lu
    sur le rythme du salarié. Les heures réellement pointées sont affichées
    comme un nombre, à côté, et jamais posées sur l'horloge : elles
    donneraient une précision qui n'existe pas.

    Sans rythme, on retombe sur 8 h — 15 h 00 + une heure de pause, ce qui
    est une hypothèse que l'interface signale.
    """
    from datetime import datetime, timedelta

    heures = (schedule.heures_du_jour(jour) if schedule
              else (ZERO if jour.weekday() >= 5 else Decimal('7')))
    if heures == 0:
        return None

    debut_heure = schedule.heure_debut if schedule else None
    if debut_heure is None:
        from datetime import time as _time
        debut_heure = _time(8, 0)
    pause = schedule.pause_minutes if schedule else 60

    debut = datetime.combine(jour, debut_heure)
    fin = debut + timedelta(hours=float(heures), minutes=pause or 0)
    return {'debut': debut, 'fin': fin, 'heures': heures,
            'pause_minutes': pause or 0}


def position_sur_la_frise(creneau):
    """Position et largeur du bloc, en pourcentage de la frise.

    Calculé ici et non dans le gabarit : Django ne sait pas diviser, et un
    filtre maison pour cela se tromperait aux bords — un créneau qui
    commence avant 6 h ou finit après 20 h doit être coupé, pas débordé.
    """
    if creneau is None:
        return None
    total_minutes = (HEURE_FRISE_FIN - HEURE_FRISE_DEBUT) * 60
    depart = creneau['debut'].hour * 60 + creneau['debut'].minute
    arrivee = creneau['fin'].hour * 60 + creneau['fin'].minute
    if creneau['fin'].date() > creneau['debut'].date():
        arrivee = HEURE_FRISE_FIN * 60  # debordement sur le lendemain
    origine = HEURE_FRISE_DEBUT * 60

    gauche = max(0, depart - origine)
    droite = min(total_minutes, arrivee - origine)
    if droite <= gauche:
        return None
    return {
        'gauche': round(gauche * 100 / total_minutes, 2),
        'largeur': round((droite - gauche) * 100 / total_minutes, 2),
        'coupe_avant': depart < origine,
        'coupe_apres': arrivee > HEURE_FRISE_FIN * 60,
    }


def heures_de_la_frise():
    """Les graduations de la frise, pour l'en-tete du gabarit."""
    return list(range(HEURE_FRISE_DEBUT, HEURE_FRISE_FIN + 1))


def planning_equipe(company, annee, mois, employees=None):
    """Le mois de TOUTE l'équipe. Conservée pour les appels existants.

    Délègue à planning_intervalle : une seule lecture pour les quatre
    granularités.
    """
    debut, fin = bornes_du_mois(annee, mois)
    return planning_intervalle(company, debut, fin, employees=employees)


def planning_intervalle(company, debut, fin, employees=None, vue='mois'):
    """L'équipe sur un intervalle quelconque, en cinq requêtes.

    Une lecture par salarié et par jour ferait 600 requêtes pour vingt
    salariés sur trente jours. Tout est donc chargé en bloc ici, puis
    réparti en mémoire — et le nombre de requêtes ne dépend ni de la durée
    de l'intervalle ni du nombre de salariés.

    Retourne {'debut', 'fin', 'dates', 'lignes', 'totaux', 'vue'}.
    """
    from apps.btp.models import BTPTimesheet
    from .models import Employee, LeaveRequest, WorkSchedule, WorkStoppage

    if employees is None:
        employees = list(Employee.objects.filter(
            company=company, is_active=True).order_by('last_name',
                                                      'first_name'))
    else:
        employees = list(employees)

    ids = [e.pk for e in employees]
    ids_user = [e.user_id for e in employees if e.user_id]

    rythmes = {
        s.employee_id: s
        for s in WorkSchedule.objects.filter(employee_id__in=ids)
    }
    conges = defaultdict(list)
    for conge in LeaveRequest.objects.filter(
            employee_id__in=ids, status__in=STATUTS_CONGE_VISIBLES,
            start_date__lte=fin, end_date__gte=debut):
        conges[conge.employee_id].append(conge)

    arrets = defaultdict(list)
    for arret in WorkStoppage.objects.filter(employee_id__in=ids,
                                             start_date__lte=fin):
        if arret.end_date is None or arret.end_date >= debut:
            arrets[arret.employee_id].append(arret)

    pointages = defaultdict(list)
    if ids_user:
        for pointage in BTPTimesheet.objects.filter(
                employee_id__in=ids_user,
                work_date__gte=debut, work_date__lte=fin
        ).select_related('project'):
            pointages[pointage.employee_id].append(pointage)

    dates = list(_jours_entre(debut, fin))
    lignes = []
    cumul = {'heures_prevues': ZERO, 'heures_pointees': ZERO,
             'heures_sup': ZERO, 'jours_conge': 0, 'jours_arret': 0}

    for employee in employees:
        ligne = _ligne_equipe(
            employee, dates, rythmes.get(employee.pk),
            conges.get(employee.pk, []), arrets.get(employee.pk, []),
            pointages.get(employee.user_id, []) if employee.user_id else [],
            debut, fin)
        lignes.append(ligne)
        for cle in cumul:
            cumul[cle] += ligne['totaux'][cle]

    return {'debut': debut, 'fin': fin, 'dates': dates,
            'lignes': lignes, 'totaux': cumul, 'vue': vue,
            'heures_frise': heures_de_la_frise()}


def _ligne_equipe(employee, dates, schedule, conges, arrets, pointages,
                  debut, fin):
    """Une ligne de la grille d'équipe, sans aucune requête.

    Toutes les données sont déjà en mémoire : c'est ce qui permet à la vue
    d'équipe de tenir en quatre requêtes au total plutôt qu'en quatre par
    salarié.
    """
    par_jour_conge = defaultdict(list)
    for conge in conges:
        for jour in _jours_entre(max(conge.start_date, debut),
                                 min(conge.end_date, fin)):
            par_jour_conge[jour].append(conge)

    par_jour_arret = defaultdict(list)
    for arret in arrets:
        borne_fin = min(arret.end_date, fin) if arret.end_date else fin
        for jour in _jours_entre(max(arret.start_date, debut), borne_fin):
            par_jour_arret[jour].append(arret)

    par_jour_pointage = defaultdict(list)
    for pointage in pointages:
        par_jour_pointage[pointage.work_date].append(pointage)

    cellules = []
    totaux = {'heures_prevues': ZERO, 'heures_pointees': ZERO,
              'heures_sup': ZERO, 'jours_conge': 0, 'jours_arret': 0}

    for jour in dates:
        repos = schedule.est_jour_de_repos(jour) if schedule else jour.weekday() >= 5
        prevues = schedule.heures_du_jour(jour) if schedule else (
            ZERO if repos else Decimal('7'))
        conges_jour = par_jour_conge[jour]
        arrets_jour = par_jour_arret[jour]
        etat = _etat_du_jour(repos, conges_jour, arrets_jour)
        prevues_retenues = ZERO if etat in ('arret', 'conge', 'maladie') else prevues

        du_jour = par_jour_pointage[jour]
        pointees = sum((Decimal(p.hours or 0) for p in du_jour), ZERO)
        sup = sum((Decimal(p.overtime_hours or 0) for p in du_jour), ZERO)

        # Le creneau n'est calcule que s'il y a lieu : un jour d'absence
        # n'a pas d'horaire a afficher, et le calculer quand meme ferait
        # apparaitre sur la frise une presence prevue un jour d'arret.
        creneau = None
        if etat == 'travaille':
            creneau = creneau_prevu(schedule, jour)

        cellules.append({
            'date': jour, 'etat': etat, 'libelle_etat': LIBELLES_ETAT[etat],
            'heures_pointees': pointees, 'heures_prevues': prevues_retenues,
            'heures_sup': sup,
            'pointages': du_jour,
            'conges': conges_jour,
            'arrets': arrets_jour,
            'creneau': creneau,
            'frise': position_sur_la_frise(creneau),
        })

        totaux['heures_prevues'] += prevues_retenues
        totaux['heures_pointees'] += pointees
        totaux['heures_sup'] += sup
        if etat == 'arret':
            totaux['jours_arret'] += 1
        elif etat in ('conge', 'maladie'):
            totaux['jours_conge'] += 1

    totaux['ecart'] = totaux['heures_pointees'] - totaux['heures_prevues']

    return {
        'employee': employee, 'schedule': schedule, 'cellules': cellules,
        'totaux': totaux, 'sans_compte': not employee.user_id,
    }


def mois_precedent(annee, mois):
    return (annee - 1, 12) if mois == 1 else (annee, mois - 1)


def mois_suivant(annee, mois):
    return (annee + 1, 1) if mois == 12 else (annee, mois + 1)


def annee_mois_demandes(requete, aujourdhui=None):
    """Lit ?annee= et ?mois= en tolérant n'importe quelle saisie.

    Un mois à 13 ou une année à « abc » lèverait ValueError dans
    calendar.monthrange et renverrait une erreur 500 sur une simple URL
    tapée de travers. On retombe sur le mois courant.
    """
    from django.utils import timezone
    reference = aujourdhui or timezone.localdate()
    try:
        annee = int(requete.GET.get('annee', reference.year))
        mois = int(requete.GET.get('mois', reference.month))
    except (TypeError, ValueError):
        return reference.year, reference.month
    if not 1 <= mois <= 12 or not 1900 <= annee <= 2200:
        return reference.year, reference.month
    return annee, mois
