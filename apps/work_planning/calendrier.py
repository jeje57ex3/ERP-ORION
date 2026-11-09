# -*- coding: utf-8 -*-
"""Pose les blocs de temps sur une grille horaire, à la façon d'un agenda.

CE QUE LA BASE CONTIENT, ET CE QU'ELLE NE CONTIENT PAS.

`DedicatedTimeBlock` porte une **date** et une **durée** (`hours`). Il n'a
**pas d'heure de début** : « Paul, le 12 mars, 3,5 h sur la mission
Dubois » ne dit pas à quelle heure Paul commence.

Une grille horaire a pourtant besoin d'une position verticale. Deux voies
étaient possibles :

1. Ajouter un champ « heure de début » au modèle, et demander à chacun de
   le renseigner — une migration, et surtout une saisie de plus sur chaque
   bloc déjà créé, qui resterait vide en attendant.
2. La DÉDUIRE de ce que la fiche salarié sait déjà : `normal_work_start`,
   `normal_work_end`, et la pause déjeuner.

C'est la seconde qui est appliquée ici. Les blocs d'un salarié sont posés
**à la suite**, à partir de son heure d'embauche, en sautant sa pause.

CE QUE CELA SIGNIFIE, ET CE QUE CELA NE SIGNIFIE PAS. La hauteur d'un bloc
est sa durée réelle, et l'ordre est l'ordre de la journée. Mais la position
verticale est **calculée**, pas enregistrée : elle dit « voici comment la
journée se remplit », et non « le rendez-vous est à 10 h 15 ». L'écran le
dit, parce qu'un agenda qui laisse croire à des horaires fermes alors qu'il
les devine ferait manquer un rendez-vous.

Le jour où une heure de début sera saisie, cette fonction la préférera au
calcul — c'est la raison du `getattr` sur `heure_debut`.
"""

from datetime import date as _date
from datetime import datetime, time, timedelta
from decimal import Decimal

# Bornes de repli quand aucun salarié n'a d'horaire exploitable.
HEURE_MIN_PAR_DEFAUT = 7
HEURE_MAX_PAR_DEFAUT = 19

# Un agenda qui s'arrête à l'heure de fin théorique cacherait les
# dépassements, c'est-à-dire précisément ce qu'on veut voir.
MARGE_HEURES = 1


def _minutes(heure):
    return heure.hour * 60 + heure.minute


def _en_heure(minutes):
    minutes = max(0, min(24 * 60 - 1, int(minutes)))
    return time(minutes // 60, minutes % 60)


def _duree_en_minutes(bloc):
    try:
        return max(0, int(round(float(bloc.hours or Decimal('0')) * 60)))
    except (TypeError, ValueError):
        return 0


def _pause(employe):
    """La pause déjeuner en minutes, ou None s'il n'y en a pas."""
    debut = getattr(employe, 'lunch_break_start', None)
    fin = getattr(employe, 'lunch_break_end', None)
    if not debut or not fin:
        return None
    a, b = _minutes(debut), _minutes(fin)
    return (a, b) if b > a else None


def _segments_du_bloc(depart, duree, pause):
    """Découpe un bloc autour de la pause déjeuner.

    Un bloc de sept heures commencé le matin ENJAMBE le déjeuner. Le
    dessiner d'un seul tenant le ferait traverser la bande grisée de la
    pause, ce qui est faux : le salarié ne travaille pas pendant. On rend
    donc deux segments, et le temps de pause ne compte pas dans la durée.
    """
    segments = []
    position = depart
    restant = duree

    while restant > 0:
        if pause and pause[0] <= position < pause[1]:
            position = pause[1]
            continue
        if pause and position < pause[0]:
            disponible = pause[0] - position
        else:
            disponible = restant
        pris = min(restant, disponible)
        segments.append((position, position + pris))
        position += pris
        restant -= pris
        if restant > 0 and pause and position >= pause[0]:
            position = max(position, pause[1])

    return segments


def _placer_cote_a_cote(elements):
    """Assigne une colonne à chaque élément qui en chevauche un autre.

    C'est ce que fait un agenda quand deux rendez-vous tombent en même
    temps : ils se partagent la largeur au lieu de se recouvrir. Deux
    salariés qui travaillent le même matin doivent tous deux se voir.

    Algorithme glouton sur les éléments triés par début : on cherche la
    première colonne dont le dernier élément est terminé.
    """
    elements.sort(key=lambda e: (e['debut_min'], e['fin_min']))
    fins_par_colonne = []

    for element in elements:
        for index, fin in enumerate(fins_par_colonne):
            if fin <= element['debut_min']:
                element['colonne'] = index
                fins_par_colonne[index] = element['fin_min']
                break
        else:
            element['colonne'] = len(fins_par_colonne)
            fins_par_colonne.append(element['fin_min'])

    total = max(1, len(fins_par_colonne))
    for element in elements:
        element['nb_colonnes'] = total
    return elements


def grille_de_la_semaine(blocs, employes, jours):
    """La semaine prête à dessiner : des jours, des heures, des blocs placés.

    Rend un dictionnaire avec `heure_min`, `heure_max`, `heures` et
    `jours`. Chaque bloc porte sa position en POURCENTAGE de la hauteur du
    jour, pour que le gabarit n'ait aucun calcul à faire.
    """
    par_employe = {e.pk: e for e in employes}

    # ── Les bornes de la grille ─────────────────────────────────────────
    debuts = [_minutes(e.normal_work_start) for e in employes
              if getattr(e, 'normal_work_start', None)]
    fins = [_minutes(e.normal_work_end) for e in employes
            if getattr(e, 'normal_work_end', None)]
    heure_min = min(debuts) // 60 if debuts else HEURE_MIN_PAR_DEFAUT
    heure_max = (max(fins) + 59) // 60 if fins else HEURE_MAX_PAR_DEFAUT

    # ── Le remplissage de chaque journée, salarié par salarié ───────────
    par_jour = {jour: [] for jour in jours}
    curseurs = {}

    for bloc in blocs:
        employe = par_employe.get(bloc.employee_id)
        if employe is None or bloc.date not in par_jour:
            continue

        duree = _duree_en_minutes(bloc)
        if duree <= 0:
            continue

        pause = _pause(employe)
        cle = (employe.pk, bloc.date)
        if cle not in curseurs:
            depart = getattr(employe, 'normal_work_start', None) or time(9, 0)
            curseurs[cle] = _minutes(depart)

        # Une heure de début SAISIE l'emporte toujours sur le calcul. Le
        # champ n'existe pas aujourd'hui ; le jour où il existera, cette
        # fonction n'aura pas à changer.
        saisie = getattr(bloc, 'heure_debut', None)
        depart = _minutes(saisie) if saisie else curseurs[cle]

        segments = _segments_du_bloc(depart, duree, pause)
        if not segments:
            continue
        curseurs[cle] = segments[-1][1]

        for index, (debut, fin) in enumerate(segments):
            par_jour[bloc.date].append({
                'bloc': bloc,
                'employe': employe,
                'couleur': getattr(employe, 'color_code', '') or '#6366F1',
                'debut_min': debut,
                'fin_min': fin,
                'debut': _en_heure(debut),
                'fin': _en_heure(fin),
                'duree_heures': bloc.hours,
                'coupe_par_la_pause': len(segments) > 1,
                'premier_segment': index == 0,
            })
            heure_max = max(heure_max, (fin + 59) // 60)

    heure_max = min(24, max(heure_max, heure_min + 1) + MARGE_HEURES)
    hauteur = max(1, (heure_max - heure_min) * 60)

    jours_rendus = []
    for jour in jours:
        elements = _placer_cote_a_cote(par_jour[jour])
        for element in elements:
            haut = (element['debut_min'] - heure_min * 60) / hauteur * 100
            element['haut_pct'] = round(max(0.0, min(100.0, haut)), 3)
            element['hauteur_pct'] = round(
                max(1.2, (element['fin_min'] - element['debut_min'])
                    / hauteur * 100), 3)
            element['largeur_pct'] = round(100 / element['nb_colonnes'], 3)
            element['gauche_pct'] = round(
                element['colonne'] * 100 / element['nb_colonnes'], 3)
        jours_rendus.append({
            'date': jour,
            'blocs': elements,
            'total_heures': sum(
                (e['bloc'].hours for e in elements if e['premier_segment']),
                Decimal('0')),
        })

    return {
        'heure_min': heure_min,
        'heure_max': heure_max,
        'heures': list(range(heure_min, heure_max)),
        'jours': jours_rendus,
    }


def position_de_maintenant(heure_min, heure_max, maintenant=None):
    """Où tracer le trait de l'heure courante, en pourcentage. None si hors.

    Le trait rouge de l'heure courante est ce qui fait qu'un agenda se lit
    d'un coup d'œil : sans lui, on cherche où l'on en est.
    """
    maintenant = maintenant or datetime.now()
    minutes = maintenant.hour * 60 + maintenant.minute
    if not (heure_min * 60 <= minutes <= heure_max * 60):
        return None
    hauteur = max(1, (heure_max - heure_min) * 60)
    return round((minutes - heure_min * 60) / hauteur * 100, 3)


def semaine_de(reference=None):
    """Du lundi au dimanche contenant cette date."""
    reference = reference or _date.today()
    lundi = reference - timedelta(days=reference.weekday())
    return [lundi + timedelta(days=index) for index in range(7)]
