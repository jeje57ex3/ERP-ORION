"""apps/internal_training/parcours.py — Les règles du parcours.

TROIS ÉTAPES, TROIS PREUVES DIFFÉRENTES

  1. les chapitres : la personne a LU ;
  2. le quiz : elle a RETENU ;
  3. la validation terrain : elle sait FAIRE.

Aucune des deux premières ne démontre la troisième, et c'est pourquoi elles
ne se remplacent pas. Un quiz réussi à 100 % ne dit rien de ce qui se passe
sur un chantier ; c'est le constat d'un responsable présent qui le dit.

CE MODULE DÉCIDE, LES VUES AFFICHENT

Tout l'état du parcours se calcule ici, à partir de la base, et rien n'est
stocké en double. Un champ « étape courante » écrit sur l'inscription
dériverait de la réalité à la première page ajoutée au support : il dirait
« terminé » pour un parcours devenu plus long.

LES DEUX RÈGLES À NE PAS PERDRE

  * un apprenant ne valide pas sa propre compétence. Sans cela, toute la
    troisième étape devient décorative ;
  * la note minimale est FIGÉE au moment de la tentative. L'abaisser plus
    tard ne doit pas transformer rétroactivement un échec en réussite.
"""
from django.db import transaction
from django.utils import timezone

from .models import (ChoixDeQuestion, ReponseDeTentative, TentativeDeQuiz,
                     TrainingPage, TrainingPageProgress, ValidationTerrain)


class ParcoursRefuse(Exception):
    """L'action demandée n'est pas permise à ce stade, avec sa raison."""


# ── Lecture : où en est la personne ? ────────────────────────────────────────

def _pages_du_cours(course):
    return TrainingPage.objects.filter(
        chapter__course=course, status='published'
    ).order_by('chapter__order', 'order')


def _pages_faites(course, user):
    """Les identifiants de pages que cette personne a terminées."""
    return set(
        TrainingPageProgress.objects
        .filter(user=user, is_completed=True, page__chapter__course=course)
        .values_list('page_id', flat=True)
    )


def etat_des_chapitres(course, user):
    """Chaque chapitre, avec sa progression et son verrou.

    Le verrou n'est posé que si la formation l'a demandé. Un chapitre sans
    page publiée ne verrouille pas le suivant : sinon un chapitre vide — en
    cours de rédaction, par exemple — bloquerait tout le parcours sans que
    personne comprenne pourquoi.
    """
    faites = _pages_faites(course, user)
    resultat = []
    precedents_termines = True

    for chapitre in course.chapters.all().order_by('order', 'id'):
        pages = [p for p in _pages_du_cours(course)
                 if p.chapter_id == chapitre.id]
        total = len(pages)
        faites_ici = sum(1 for p in pages if p.id in faites)
        termine = total > 0 and faites_ici == total

        verrouille = (course.progression_sequentielle
                      and not precedents_termines)

        resultat.append({
            'chapitre': chapitre,
            'pages': pages,
            'pages_total': total,
            'pages_faites': faites_ici,
            'termine': termine,
            'verrouille': verrouille,
            'pourcentage': round(faites_ici / total * 100) if total else 0,
        })

        # Un chapitre vide est neutre : il ne termine rien et ne bloque rien.
        if total > 0:
            precedents_termines = precedents_termines and termine

    return resultat


def lecture_terminee(course, user):
    """Toutes les pages publiées de la formation sont-elles lues ?

    Une formation SANS page n'est pas « lue » : sans cette précaution, un
    support vide ouvrirait directement le quiz et la validation terrain.
    """
    pages = list(_pages_du_cours(course))
    if not pages:
        return False
    faites = _pages_faites(course, user)
    return all(page.id in faites for page in pages)


def quiz_du_cours(course):
    return getattr(course, 'quiz', None)


def etat_du_quiz(course, user):
    """L'accès au quiz, les tentatives restantes, le meilleur résultat."""
    quiz = quiz_du_cours(course)
    if quiz is None:
        return {'existe': False, 'accessible': False, 'reussi': False,
                'raison': 'Cette formation n’a pas de quiz.'}

    terminees = quiz.tentatives.filter(user=user, finie_le__isnull=False)
    reussi = terminees.filter(reussie=True).exists()
    meilleure = terminees.order_by('-score').first()
    nombre = terminees.count()

    illimite = quiz.tentatives_max == 0
    restantes = None if illimite else max(0, quiz.tentatives_max - nombre)

    accessible = True
    raison = ''
    if quiz.nombre_de_questions == 0:
        accessible = False
        raison = 'Le quiz ne contient encore aucune question.'
    elif not lecture_terminee(course, user):
        accessible = False
        raison = ('Le quiz s’ouvre quand toutes les pages de la formation '
                  'ont été lues.')
    elif reussi:
        accessible = False
        raison = 'Quiz déjà réussi.'
    elif not illimite and restantes == 0:
        accessible = False
        raison = (f'Les {quiz.tentatives_max} tentatives sont épuisées. Un '
                  f'responsable doit vous débloquer.')

    return {
        'existe': True, 'quiz': quiz, 'accessible': accessible,
        'raison': raison, 'reussi': reussi, 'meilleure': meilleure,
        'tentatives_faites': nombre, 'tentatives_restantes': restantes,
        'illimite': illimite,
    }


def etat_du_terrain(course, user):
    """Les validations de compétences attendues, et leur sort."""
    competences = list(course.competences.filter(active=True))
    if not competences:
        return {'existe': False, 'accessible': False, 'validations': [],
                'tout_acquis': False,
                'raison': 'Cette formation ne vise aucune compétence.'}

    quiz = etat_du_quiz(course, user)
    accessible = quiz['reussi'] if quiz['existe'] else lecture_terminee(
        course, user)

    validations = list(
        ValidationTerrain.objects
        .filter(apprenant=user, course=course,
                competence__in=competences)
        .select_related('competence', 'valide_par')
    )
    acquises = {v.competence_id for v in validations if v.est_acquise}

    return {
        'existe': True,
        'accessible': accessible,
        'raison': '' if accessible else (
            'La validation sur le terrain s’ouvre après la réussite du '
            'quiz.'),
        'competences': competences,
        'validations': validations,
        'tout_acquis': len(acquises) == len(competences),
        'manquantes': [c for c in competences if c.id not in acquises],
    }


def etat_du_parcours(course, user):
    """L'état complet : ce que la page du parcours affiche."""
    chapitres = etat_des_chapitres(course, user)
    quiz = etat_du_quiz(course, user)
    terrain = etat_du_terrain(course, user)

    lecture_ok = lecture_terminee(course, user)
    quiz_ok = quiz['reussi'] if quiz['existe'] else True
    terrain_ok = terrain['tout_acquis'] if terrain['existe'] else True

    if not lecture_ok:
        etape = 'lecture'
    elif not quiz_ok:
        etape = 'quiz'
    elif not terrain_ok:
        etape = 'terrain'
    else:
        etape = 'termine'

    # Trois étapes, un tiers chacune. La lecture compte au prorata des pages
    # lues ; les deux autres sont tout ou rien, parce qu'un quiz à moitié
    # réussi n'est pas réussi.
    pages = list(_pages_du_cours(course))
    part_lecture = (len(_pages_faites(course, user)) / len(pages)
                    if pages else 0)
    etapes_actives = 1 + (1 if quiz['existe'] else 0) + (
        1 if terrain['existe'] else 0)
    avance = part_lecture
    if quiz['existe'] and quiz_ok:
        avance += 1
    if terrain['existe'] and terrain_ok:
        avance += 1
    pourcentage = round(avance / etapes_actives * 100) if etapes_actives else 0

    return {
        'chapitres': chapitres,
        'quiz': quiz,
        'terrain': terrain,
        'lecture_terminee': lecture_ok,
        'etape': etape,
        'pourcentage': min(100, pourcentage),
    }


# ── Écriture : passer le quiz ────────────────────────────────────────────────

def demarrer_une_tentative(course, user):
    """Ouvre une tentative, ou refuse en disant pourquoi."""
    etat = etat_du_quiz(course, user)
    if not etat['existe']:
        raise ParcoursRefuse(etat['raison'])
    if not etat['accessible']:
        raise ParcoursRefuse(etat['raison'])

    quiz = etat['quiz']

    # Une tentative laissée ouverte est reprise plutôt que doublée : fermer
    # l'onglet au milieu d'un quiz ne doit pas consommer un essai.
    en_cours = quiz.tentatives.filter(
        user=user, finie_le__isnull=True).order_by('-debutee_le').first()
    if en_cours is not None:
        return en_cours

    return TentativeDeQuiz.objects.create(
        quiz=quiz, user=user,
        numero=etat['tentatives_faites'] + 1,
        note_minimale_appliquee=quiz.note_minimale,
    )


@transaction.atomic
def corriger_une_tentative(tentative, choix_par_question):
    """Note la tentative. `choix_par_question` : {question_id: [choix_id]}.

    UNE QUESTION SANS BONNE RÉPONSE DÉCLARÉE est comptée fausse, jamais
    juste. C'est le cas d'un quiz mal saisi ; la faire passer pour juste
    offrirait des points gratuits et masquerait l'erreur de saisie.
    """
    if tentative.finie_le is not None:
        raise ParcoursRefuse('Cette tentative est déjà corrigée.')

    questions = list(tentative.quiz.questions.prefetch_related('choix'))
    if not questions:
        raise ParcoursRefuse('Le quiz ne contient aucune question.')

    justes = 0
    for question in questions:
        attendus = question.choix_corrects
        proposes = set(choix_par_question.get(question.id, []))
        # On ne retient que des choix qui appartiennent VRAIMENT à la
        # question : un identifiant falsifié dans le formulaire ne doit pas
        # compter, ni faire échouer la correction.
        legitimes = set(question.choix.values_list('pk', flat=True))
        proposes &= legitimes

        correcte = bool(attendus) and proposes == attendus
        if correcte:
            justes += 1

        reponse = ReponseDeTentative.objects.create(
            tentative=tentative, question=question, est_correcte=correcte)
        if proposes:
            reponse.choix_retenus.set(
                ChoixDeQuestion.objects.filter(pk__in=proposes))

    tentative.score = round(justes / len(questions) * 100)
    tentative.reussie = tentative.score >= tentative.note_minimale_appliquee
    tentative.finie_le = timezone.now()
    tentative.save(update_fields=['score', 'reussie', 'finie_le'])

    if tentative.reussie:
        ouvrir_les_validations_terrain(tentative.quiz.course, tentative.user)

    return tentative


# ── Écriture : la validation terrain ─────────────────────────────────────────

def ouvrir_les_validations_terrain(course, user):
    """Crée une demande de validation par compétence encore non acquise.

    Appelée à la réussite du quiz. Idempotente : une demande déjà en attente
    n'est pas doublée, et une compétence déjà acquise et non expirée n'est
    pas redemandée.
    """
    creees = []
    for competence in course.competences.filter(active=True):
        existantes = ValidationTerrain.objects.filter(
            competence=competence, apprenant=user, course=course)
        if any(v.est_acquise for v in existantes):
            continue
        if existantes.filter(statut='en_attente').exists():
            continue
        creees.append(ValidationTerrain.objects.create(
            competence=competence, apprenant=user, course=course,
            statut='en_attente'))
    return creees


def peut_valider(valideur, validation):
    """Qui a le droit de prononcer cette validation.

    LA RÈGLE CENTRALE : jamais l'apprenant lui-même. Le reste — quel
    responsable au juste — relève des droits de l'ERP et se vérifie dans la
    vue ; celle-ci, en revanche, ne doit dépendre d'aucun réglage.
    """
    if valideur is None or not valideur.is_authenticated:
        return False, 'Il faut être connecté pour valider.'
    if valideur.pk == validation.apprenant_id:
        return False, ('Une compétence ne peut pas être validée par la '
                       'personne qui l’acquiert.')
    return True, ''


@transaction.atomic
def prononcer_une_validation(validation, valideur, statut, *,
                             constatee_le=None, lieu='', commentaire='',
                             piece_jointe=None):
    """Enregistre le constat d'un responsable."""
    autorise, raison = peut_valider(valideur, validation)
    if not autorise:
        raise ParcoursRefuse(raison)

    if statut not in dict(ValidationTerrain.STATUT_CHOICES):
        raise ParcoursRefuse(f'Statut inconnu : {statut}.')
    if statut == 'en_attente':
        raise ParcoursRefuse(
            'Prononcer une validation veut dire trancher : validée, à revoir '
            'ou refusée.')

    validation.statut = statut
    validation.valide_par = valideur
    validation.constatee_le = constatee_le or timezone.now()
    validation.lieu = lieu or validation.lieu
    validation.commentaire = commentaire or validation.commentaire
    if piece_jointe is not None:
        validation.piece_jointe = piece_jointe

    # L'expiration est calculée depuis la validité de la compétence TELLE
    # QU'ELLE EST AU MOMENT DU CONSTAT. La rallonger plus tard ne doit pas
    # prolonger une habilitation déjà délivrée.
    validation.expire_le = None
    if statut == 'validee' and validation.competence.validite_mois:
        from datetime import timedelta
        jours = round(validation.competence.validite_mois * 30.44)
        validation.expire_le = (
            validation.constatee_le.date() + timedelta(days=jours))

    validation.save()

    if statut == 'validee':
        _marquer_la_formation_terminee_si_tout_est_fait(
            validation.course, validation.apprenant)

    return validation


def _marquer_la_formation_terminee_si_tout_est_fait(course, user):
    """Pose `completed_at` sur l'inscription quand les trois étapes sont là.

    Ne défait jamais : une formation déjà notée terminée le reste, même si
    le support s'allonge ensuite. Retirer une réussite acquise à cause d'un
    chapitre ajouté après coup serait injuste et incompréhensible.
    """
    if course is None:
        return None

    from .models import TrainingEnrollment

    inscription = TrainingEnrollment.objects.filter(
        course=course, user=user).first()
    if inscription is None or inscription.completed_at is not None:
        return inscription

    etat = etat_du_parcours(course, user)
    if etat['etape'] != 'termine':
        return inscription

    inscription.completed_at = timezone.now()
    inscription.save(update_fields=['completed_at'])
    return inscription
