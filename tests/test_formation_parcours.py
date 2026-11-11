"""Le parcours de formation : étapes verrouillées, quiz, validation terrain.

TROIS ÉTAPES, TROIS PREUVES DIFFÉRENTES

Lire des pages prouve qu'on a lu. Réussir un quiz prouve qu'on a retenu. Ni
l'un ni l'autre ne prouve qu'on sait FAIRE — d'où la troisième étape, qui ne
se joue pas devant un écran.

LA RÈGLE QUI PORTE TOUT LE RESTE

Un apprenant ne peut pas valider sa propre compétence. Si elle tombait, les
deux autres étapes resteraient utiles et la troisième deviendrait
décorative : il suffirait de se déclarer compétent. Elle est donc vérifiée
au niveau du service, et non seulement de la vue.
"""
import pytest

from django.utils import timezone


# ── Montage ──────────────────────────────────────────────────────────────────

@pytest.fixture
def entreprise(db):
    from apps.core.models import Company
    return Company.objects.create(name='Volt SARL', slug='volt-sarl')


@pytest.fixture
def apprenant(db, django_user_model):
    return django_user_model.objects.create_user(
        username='salarie', password='motdepasse-test', email='s@volt.fr')


@pytest.fixture
def chef(db, django_user_model):
    return django_user_model.objects.create_user(
        username='chef', password='motdepasse-test', email='c@volt.fr')


@pytest.fixture
def formation(db, entreprise):
    from apps.internal_training.models import TrainingCourse
    return TrainingCourse.objects.create(
        company=entreprise, title='Consignation électrique',
        status='published')


def _chapitre(formation, titre, ordre, nombre_de_pages=1):
    from apps.internal_training.models import TrainingChapter, TrainingPage

    chapitre = TrainingChapter.objects.create(
        course=formation, title=titre, order=ordre)
    pages = [
        TrainingPage.objects.create(
            chapter=chapitre, title=f'{titre} — page {i + 1}',
            order=i, status='published')
        for i in range(nombre_de_pages)
    ]
    return chapitre, pages


def _lire(page, utilisateur):
    from apps.internal_training.models import TrainingPageProgress
    TrainingPageProgress.objects.update_or_create(
        page=page, user=utilisateur,
        defaults={'is_completed': True, 'completed_at': timezone.now()})


def _quiz(formation, *, note_minimale=70, tentatives_max=3,
          nombre_de_questions=2):
    from apps.internal_training.models import (ChoixDeQuestion, QuestionDeQuiz,
                                               Quiz)

    quiz = Quiz.objects.create(
        course=formation, note_minimale=note_minimale,
        tentatives_max=tentatives_max, melanger_les_questions=False)
    for i in range(nombre_de_questions):
        question = QuestionDeQuiz.objects.create(
            quiz=quiz, enonce=f'Question {i + 1}', order=i)
        ChoixDeQuestion.objects.create(
            question=question, libelle='Bonne', est_correct=True, order=0)
        ChoixDeQuestion.objects.create(
            question=question, libelle='Mauvaise', est_correct=False, order=1)
    return quiz


def _competence(entreprise, code='ELEC-VAT', validite_mois=0):
    from apps.internal_training.models import Competence
    return Competence.objects.create(
        company=entreprise, code=code,
        libelle='Sait consigner avant intervention',
        validite_mois=validite_mois)


def _bonnes_reponses(quiz):
    return {q.pk: sorted(q.choix_corrects) for q in quiz.questions.all()}


# ── 1. Les étapes verrouillées ───────────────────────────────────────────────

@pytest.mark.django_db
def test_sans_option_l_ordre_n_est_pas_impose(formation, apprenant):
    """Le verrouillage est une OPTION, et son défaut est « non ».

    Une formation de référence qu'on consulte par morceaux n'a aucune raison
    d'imposer un ordre. Forcer l'un ou l'autre pour tout le monde serait un
    choix de bibliothécaire, pas de formateur.
    """
    from apps.internal_training import parcours

    _chapitre(formation, 'Chapitre 1', 0)
    _chapitre(formation, 'Chapitre 2', 1)

    etat = parcours.etat_des_chapitres(formation, apprenant)
    assert [bloc['verrouille'] for bloc in etat] == [False, False]


@pytest.mark.django_db
def test_avec_l_option_le_second_chapitre_est_ferme(formation, apprenant):
    from apps.internal_training import parcours

    formation.progression_sequentielle = True
    formation.save()
    _chapitre(formation, 'Chapitre 1', 0)
    _chapitre(formation, 'Chapitre 2', 1)

    etat = parcours.etat_des_chapitres(formation, apprenant)
    assert etat[0]['verrouille'] is False
    assert etat[1]['verrouille'] is True


@pytest.mark.django_db
def test_lire_le_premier_chapitre_ouvre_le_second(formation, apprenant):
    from apps.internal_training import parcours

    formation.progression_sequentielle = True
    formation.save()
    _, pages1 = _chapitre(formation, 'Chapitre 1', 0, nombre_de_pages=2)
    _chapitre(formation, 'Chapitre 2', 1)

    _lire(pages1[0], apprenant)
    etat = parcours.etat_des_chapitres(formation, apprenant)
    assert etat[1]['verrouille'] is True, 'une page sur deux ne suffit pas'

    _lire(pages1[1], apprenant)
    etat = parcours.etat_des_chapitres(formation, apprenant)
    assert etat[0]['termine'] is True
    assert etat[1]['verrouille'] is False


@pytest.mark.django_db
def test_un_chapitre_vide_ne_bloque_pas_le_parcours(formation, apprenant):
    """LE PIÈGE DU VERROU.

    Un chapitre en cours de rédaction, sans page publiée, ne peut jamais
    être « terminé ». S'il comptait, il bloquerait tout ce qui le suit sans
    que personne comprenne pourquoi — et l'auteur du support serait le seul
    à pouvoir débloquer la situation, en publiant une page.
    """
    from apps.internal_training import parcours

    formation.progression_sequentielle = True
    formation.save()
    _chapitre(formation, 'Chapitre vide', 0, nombre_de_pages=0)
    _chapitre(formation, 'Chapitre 2', 1)

    etat = parcours.etat_des_chapitres(formation, apprenant)
    assert etat[1]['verrouille'] is False


@pytest.mark.django_db
def test_une_formation_sans_page_n_est_pas_consideree_lue(formation,
                                                          apprenant):
    """Sinon un support vide ouvrirait quiz et validation terrain d'emblée."""
    from apps.internal_training import parcours
    assert parcours.lecture_terminee(formation, apprenant) is False


# ── 2. Le quiz ───────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_le_quiz_est_ferme_avant_la_fin_de_la_lecture(formation, apprenant):
    from apps.internal_training import parcours

    _, pages = _chapitre(formation, 'Chapitre 1', 0, nombre_de_pages=2)
    _quiz(formation)
    _lire(pages[0], apprenant)

    etat = parcours.etat_du_quiz(formation, apprenant)
    assert etat['accessible'] is False
    assert 'lues' in etat['raison']

    with pytest.raises(parcours.ParcoursRefuse):
        parcours.demarrer_une_tentative(formation, apprenant)


@pytest.mark.django_db
def test_un_quiz_sans_question_ne_s_ouvre_pas(formation, apprenant):
    """Il serait réussi à 0 question sur 0, ce qui ne veut rien dire."""
    from apps.internal_training import parcours
    from apps.internal_training.models import Quiz

    _, pages = _chapitre(formation, 'Chapitre 1', 0)
    _lire(pages[0], apprenant)
    Quiz.objects.create(course=formation)

    etat = parcours.etat_du_quiz(formation, apprenant)
    assert etat['accessible'] is False
    assert 'aucune question' in etat['raison']


@pytest.mark.django_db
def test_toutes_bonnes_reponses_vaut_cent_pour_cent(formation, apprenant):
    from apps.internal_training import parcours

    _, pages = _chapitre(formation, 'Chapitre 1', 0)
    quiz = _quiz(formation)
    _lire(pages[0], apprenant)

    tentative = parcours.demarrer_une_tentative(formation, apprenant)
    tentative = parcours.corriger_une_tentative(
        tentative, _bonnes_reponses(quiz))

    assert tentative.score == 100
    assert tentative.reussie is True
    assert tentative.finie_le is not None


@pytest.mark.django_db
def test_une_question_sur_deux_ne_suffit_pas_a_soixante_dix(formation,
                                                            apprenant):
    from apps.internal_training import parcours

    _, pages = _chapitre(formation, 'Chapitre 1', 0)
    quiz = _quiz(formation, note_minimale=70)
    _lire(pages[0], apprenant)

    questions = list(quiz.questions.all())
    reponses = {questions[0].pk: sorted(questions[0].choix_corrects)}

    tentative = parcours.demarrer_une_tentative(formation, apprenant)
    tentative = parcours.corriger_une_tentative(tentative, reponses)

    assert tentative.score == 50
    assert tentative.reussie is False


@pytest.mark.django_db
def test_une_question_a_choix_multiples_exige_l_ensemble_exact(formation,
                                                               apprenant):
    """Toutes les bonnes, et aucune mauvaise. Une réponse partielle est
    fausse : cocher une bonne case sur trois ne démontre rien."""
    from apps.internal_training import parcours
    from apps.internal_training.models import (ChoixDeQuestion, QuestionDeQuiz,
                                               Quiz)

    _, pages = _chapitre(formation, 'Chapitre 1', 0)
    _lire(pages[0], apprenant)

    quiz = Quiz.objects.create(
        course=formation, note_minimale=100, melanger_les_questions=False)
    question = QuestionDeQuiz.objects.create(
        quiz=quiz, enonce='Lesquels ?', type_de_question='multiple')
    a = ChoixDeQuestion.objects.create(
        question=question, libelle='A', est_correct=True)
    b = ChoixDeQuestion.objects.create(
        question=question, libelle='B', est_correct=True)
    c = ChoixDeQuestion.objects.create(
        question=question, libelle='C', est_correct=False)

    # Une seule bonne sur deux : faux.
    t1 = parcours.demarrer_une_tentative(formation, apprenant)
    t1 = parcours.corriger_une_tentative(t1, {question.pk: [a.pk]})
    assert t1.score == 0

    # Les deux bonnes plus une mauvaise : faux aussi.
    t2 = parcours.demarrer_une_tentative(formation, apprenant)
    t2 = parcours.corriger_une_tentative(
        t2, {question.pk: [a.pk, b.pk, c.pk]})
    assert t2.score == 0

    # Exactement les deux bonnes.
    t3 = parcours.demarrer_une_tentative(formation, apprenant)
    t3 = parcours.corriger_une_tentative(t3, {question.pk: [a.pk, b.pk]})
    assert t3.score == 100


@pytest.mark.django_db
def test_un_choix_etranger_a_la_question_est_ignore(formation, apprenant):
    """Un identifiant falsifié dans le formulaire ne doit ni compter ni
    faire échouer la correction."""
    from apps.internal_training import parcours

    _, pages = _chapitre(formation, 'Chapitre 1', 0)
    quiz = _quiz(formation, nombre_de_questions=2)
    _lire(pages[0], apprenant)

    questions = list(quiz.questions.all())
    choix_de_l_autre = questions[1].choix.first().pk
    reponses = {
        questions[0].pk: sorted(questions[0].choix_corrects) + [
            choix_de_l_autre],
        questions[1].pk: sorted(questions[1].choix_corrects),
    }

    tentative = parcours.demarrer_une_tentative(formation, apprenant)
    tentative = parcours.corriger_une_tentative(tentative, reponses)
    assert tentative.score == 100


@pytest.mark.django_db
def test_une_question_sans_bonne_reponse_declaree_est_comptee_fausse(
        formation, apprenant):
    """Cas d'un quiz mal saisi. La compter juste offrirait des points
    gratuits et masquerait l'erreur de saisie."""
    from apps.internal_training import parcours
    from apps.internal_training.models import (ChoixDeQuestion, QuestionDeQuiz,
                                               Quiz)

    _, pages = _chapitre(formation, 'Chapitre 1', 0)
    _lire(pages[0], apprenant)

    quiz = Quiz.objects.create(course=formation, melanger_les_questions=False)
    question = QuestionDeQuiz.objects.create(quiz=quiz, enonce='Oubliée ?')
    choix = ChoixDeQuestion.objects.create(
        question=question, libelle='A', est_correct=False)

    tentative = parcours.demarrer_une_tentative(formation, apprenant)
    tentative = parcours.corriger_une_tentative(
        tentative, {question.pk: [choix.pk]})
    assert tentative.score == 0


@pytest.mark.django_db
def test_les_tentatives_sont_bornees(formation, apprenant):
    from apps.internal_training import parcours

    _, pages = _chapitre(formation, 'Chapitre 1', 0)
    quiz = _quiz(formation, tentatives_max=2, note_minimale=100)
    _lire(pages[0], apprenant)

    questions = list(quiz.questions.all())
    mauvaises = {q.pk: [] for q in questions}

    for _ in range(2):
        tentative = parcours.demarrer_une_tentative(formation, apprenant)
        parcours.corriger_une_tentative(tentative, mauvaises)

    etat = parcours.etat_du_quiz(formation, apprenant)
    assert etat['accessible'] is False
    assert etat['tentatives_restantes'] == 0
    with pytest.raises(parcours.ParcoursRefuse):
        parcours.demarrer_une_tentative(formation, apprenant)


@pytest.mark.django_db
def test_abandonner_ne_consomme_pas_une_tentative(formation, apprenant):
    """Fermer l'onglet au milieu d'un quiz ne doit pas coûter un essai."""
    from apps.internal_training import parcours

    _, pages = _chapitre(formation, 'Chapitre 1', 0)
    _quiz(formation, tentatives_max=1)
    _lire(pages[0], apprenant)

    premiere = parcours.demarrer_une_tentative(formation, apprenant)
    seconde = parcours.demarrer_une_tentative(formation, apprenant)
    assert premiere.pk == seconde.pk, 'une tentative ouverte doit être reprise'


@pytest.mark.django_db
def test_abaisser_la_note_minimale_ne_rattrape_pas_un_echec(formation,
                                                            apprenant):
    """Le seuil est figé au moment de la tentative.

    Sinon un responsable qui assouplit le quiz transformerait
    rétroactivement des échecs en réussites, sans que personne l'ait voulu.
    """
    from apps.internal_training import parcours

    _, pages = _chapitre(formation, 'Chapitre 1', 0)
    quiz = _quiz(formation, note_minimale=100)
    _lire(pages[0], apprenant)

    questions = list(quiz.questions.all())
    une_seule = {questions[0].pk: sorted(questions[0].choix_corrects)}

    tentative = parcours.demarrer_une_tentative(formation, apprenant)
    tentative = parcours.corriger_une_tentative(tentative, une_seule)
    assert tentative.reussie is False
    assert tentative.note_minimale_appliquee == 100

    quiz.note_minimale = 50
    quiz.save()
    tentative.refresh_from_db()
    assert tentative.reussie is False
    assert tentative.note_minimale_appliquee == 100


@pytest.mark.django_db
def test_une_tentative_corrigee_ne_se_recorrige_pas(formation, apprenant):
    from apps.internal_training import parcours

    _, pages = _chapitre(formation, 'Chapitre 1', 0)
    quiz = _quiz(formation)
    _lire(pages[0], apprenant)

    tentative = parcours.demarrer_une_tentative(formation, apprenant)
    parcours.corriger_une_tentative(tentative, _bonnes_reponses(quiz))

    with pytest.raises(parcours.ParcoursRefuse):
        parcours.corriger_une_tentative(tentative, _bonnes_reponses(quiz))


# ── 3. La validation terrain ─────────────────────────────────────────────────

@pytest.mark.django_db
def test_reussir_le_quiz_ouvre_les_demandes_de_validation(
        formation, entreprise, apprenant):
    from apps.internal_training import parcours
    from apps.internal_training.models import ValidationTerrain

    _, pages = _chapitre(formation, 'Chapitre 1', 0)
    quiz = _quiz(formation)
    formation.competences.add(_competence(entreprise))
    _lire(pages[0], apprenant)

    tentative = parcours.demarrer_une_tentative(formation, apprenant)
    parcours.corriger_une_tentative(tentative, _bonnes_reponses(quiz))

    demandes = ValidationTerrain.objects.filter(apprenant=apprenant)
    assert demandes.count() == 1
    assert demandes.first().statut == 'en_attente'


@pytest.mark.django_db
def test_l_ouverture_des_demandes_est_idempotente(formation, entreprise,
                                                  apprenant):
    from apps.internal_training import parcours
    from apps.internal_training.models import ValidationTerrain

    formation.competences.add(_competence(entreprise))
    parcours.ouvrir_les_validations_terrain(formation, apprenant)
    parcours.ouvrir_les_validations_terrain(formation, apprenant)

    assert ValidationTerrain.objects.filter(apprenant=apprenant).count() == 1


@pytest.mark.django_db
def test_un_apprenant_ne_valide_pas_sa_propre_competence(
        formation, entreprise, apprenant):
    """LA RÈGLE QUI PORTE TOUT LE RESTE.

    Si elle tombait, il suffirait de se déclarer compétent et la troisième
    étape ne prouverait plus rien. Vérifiée dans le SERVICE, pas seulement
    dans la vue : une autre vue, une API, un import, passeraient par ici.
    """
    from apps.internal_training import parcours

    formation.competences.add(_competence(entreprise))
    validation = parcours.ouvrir_les_validations_terrain(
        formation, apprenant)[0]

    autorise, raison = parcours.peut_valider(apprenant, validation)
    assert autorise is False
    assert 'acquiert' in raison

    with pytest.raises(parcours.ParcoursRefuse):
        parcours.prononcer_une_validation(validation, apprenant, 'validee')

    validation.refresh_from_db()
    assert validation.statut == 'en_attente'


@pytest.mark.django_db
def test_un_responsable_valide_et_le_constat_est_consigne(
        formation, entreprise, apprenant, chef):
    from apps.internal_training import parcours

    formation.competences.add(_competence(entreprise))
    validation = parcours.ouvrir_les_validations_terrain(
        formation, apprenant)[0]

    parcours.prononcer_une_validation(
        validation, chef, 'validee',
        lieu='Chantier Dupont', commentaire='VAT faite dans les règles.')

    validation.refresh_from_db()
    assert validation.statut == 'validee'
    assert validation.valide_par == chef
    assert validation.constatee_le is not None
    assert validation.lieu == 'Chantier Dupont'
    assert validation.est_acquise is True


@pytest.mark.django_db
def test_prononcer_en_attente_est_refuse(formation, entreprise, apprenant,
                                         chef):
    """Trancher veut dire trancher : validée, à revoir ou refusée."""
    from apps.internal_training import parcours

    formation.competences.add(_competence(entreprise))
    validation = parcours.ouvrir_les_validations_terrain(
        formation, apprenant)[0]

    with pytest.raises(parcours.ParcoursRefuse):
        parcours.prononcer_une_validation(validation, chef, 'en_attente')


@pytest.mark.django_db
def test_une_competence_a_duree_limitee_expire(formation, entreprise,
                                               apprenant, chef):
    """Une habilitation acquise en 2019 ne dit plus rien de 2026."""
    import datetime

    from apps.internal_training import parcours

    formation.competences.add(_competence(entreprise, validite_mois=12))
    validation = parcours.ouvrir_les_validations_terrain(
        formation, apprenant)[0]

    constat = timezone.now() - datetime.timedelta(days=400)
    parcours.prononcer_une_validation(
        validation, chef, 'validee', constatee_le=constat)

    validation.refresh_from_db()
    assert validation.expire_le is not None
    assert validation.est_expiree is True
    assert validation.est_acquise is False, (
        'une habilitation expirée ne doit pas compter comme acquise')


@pytest.mark.django_db
def test_une_competence_sans_duree_ne_expire_jamais(formation, entreprise,
                                                    apprenant, chef):
    from apps.internal_training import parcours

    formation.competences.add(_competence(entreprise, validite_mois=0))
    validation = parcours.ouvrir_les_validations_terrain(
        formation, apprenant)[0]
    parcours.prononcer_une_validation(validation, chef, 'validee')

    validation.refresh_from_db()
    assert validation.expire_le is None
    assert validation.est_expiree is False
    assert validation.est_acquise is True


@pytest.mark.django_db
def test_rallonger_la_validite_ne_prolonge_pas_une_habilitation_delivree(
        formation, entreprise, apprenant, chef):
    """L'expiration est figée au constat, comme la note minimale au quiz."""
    from apps.internal_training import parcours

    competence = _competence(entreprise, validite_mois=12)
    formation.competences.add(competence)
    validation = parcours.ouvrir_les_validations_terrain(
        formation, apprenant)[0]
    parcours.prononcer_une_validation(validation, chef, 'validee')

    validation.refresh_from_db()
    echeance = validation.expire_le

    competence.validite_mois = 60
    competence.save()
    validation.refresh_from_db()
    assert validation.expire_le == echeance


# ── 4. Le parcours complet ───────────────────────────────────────────────────

@pytest.mark.django_db
def test_les_trois_etapes_se_suivent(formation, entreprise, apprenant, chef):
    """Le chemin qui aboutit, de bout en bout."""
    from apps.internal_training import parcours
    from apps.internal_training.models import TrainingEnrollment

    _, pages = _chapitre(formation, 'Chapitre 1', 0)
    quiz = _quiz(formation)
    formation.competences.add(_competence(entreprise))
    TrainingEnrollment.objects.create(course=formation, user=apprenant)

    assert parcours.etat_du_parcours(formation, apprenant)['etape'] == 'lecture'

    _lire(pages[0], apprenant)
    assert parcours.etat_du_parcours(formation, apprenant)['etape'] == 'quiz'

    tentative = parcours.demarrer_une_tentative(formation, apprenant)
    parcours.corriger_une_tentative(tentative, _bonnes_reponses(quiz))
    assert parcours.etat_du_parcours(formation, apprenant)['etape'] == 'terrain'

    from apps.internal_training.models import ValidationTerrain
    validation = ValidationTerrain.objects.get(apprenant=apprenant)
    parcours.prononcer_une_validation(validation, chef, 'validee')

    etat = parcours.etat_du_parcours(formation, apprenant)
    assert etat['etape'] == 'termine'
    assert etat['pourcentage'] == 100

    inscription = TrainingEnrollment.objects.get(
        course=formation, user=apprenant)
    assert inscription.completed_at is not None


@pytest.mark.django_db
def test_une_formation_terminee_le_reste_si_le_support_s_allonge(
        formation, entreprise, apprenant, chef):
    """Retirer une réussite acquise parce qu'un chapitre a été ajouté après
    coup serait injuste et incompréhensible."""
    from apps.internal_training import parcours
    from apps.internal_training.models import (TrainingEnrollment,
                                               ValidationTerrain)

    _, pages = _chapitre(formation, 'Chapitre 1', 0)
    quiz = _quiz(formation)
    formation.competences.add(_competence(entreprise))
    TrainingEnrollment.objects.create(course=formation, user=apprenant)

    _lire(pages[0], apprenant)
    tentative = parcours.demarrer_une_tentative(formation, apprenant)
    parcours.corriger_une_tentative(tentative, _bonnes_reponses(quiz))
    parcours.prononcer_une_validation(
        ValidationTerrain.objects.get(apprenant=apprenant), chef, 'validee')

    acheve_le = TrainingEnrollment.objects.get(
        course=formation, user=apprenant).completed_at
    assert acheve_le is not None

    _chapitre(formation, 'Chapitre 2 ajouté après', 1)
    parcours._marquer_la_formation_terminee_si_tout_est_fait(
        formation, apprenant)

    assert TrainingEnrollment.objects.get(
        course=formation, user=apprenant).completed_at == acheve_le


# ── 5. Les pages ─────────────────────────────────────────────────────────────
#
# POURQUOI DES SUPERUSERS ICI
#
# `require_company_module` exige que `request.current_company` soit résolue
# ET que le module soit activé pour elle. Un `create_user` nu n'a aucune
# entreprise : CompanyMiddleware laisse `current_company` à None, le
# décorateur redirige, et le test mesurerait le décorateur au lieu du
# parcours. Pour un superuser, le repli de CompanyMiddleware prend la
# première entreprise active, ce qui donne un vrai 200.
#
# C'est aussi réaliste : dans cet ERP, le responsable qui valide une
# compétence est un administrateur. La règle « un apprenant ne valide pas sa
# propre compétence » est, elle, vérifiée au niveau du SERVICE, donc
# indépendamment de tout droit — voir plus haut.


@pytest.fixture
def apprenant_admin(db, django_user_model):
    return django_user_model.objects.create_superuser(
        username='apprenant-admin', password='motdepasse-test',
        email='aa@volt.fr')


@pytest.fixture
def chef_admin(db, django_user_model):
    return django_user_model.objects.create_superuser(
        username='chef-admin', password='motdepasse-test', email='ca@volt.fr')


@pytest.mark.django_db
def test_la_page_du_parcours_s_affiche(client, formation, apprenant_admin):
    from apps.internal_training.models import TrainingEnrollment

    _chapitre(formation, 'Chapitre 1', 0)
    TrainingEnrollment.objects.create(course=formation, user=apprenant_admin)
    client.force_login(apprenant_admin)

    reponse = client.get(f'/erp/formations/{formation.pk}/parcours/')
    assert reponse.status_code == 200
    contenu = reponse.content.decode()
    assert 'Parcours' in contenu
    # Les trois etapes doivent etre nommees : c'est tout l'objet de l'ecran.
    assert 'Les chapitres' in contenu
    assert 'terrain' in contenu.lower()


@pytest.mark.django_db
def test_le_parcours_renvoie_vers_l_inscription_si_non_inscrit(
        client, formation, apprenant_admin):
    """Un parcours sans inscription n'a pas d'état à afficher."""
    client.force_login(apprenant_admin)
    reponse = client.get(f'/erp/formations/{formation.pk}/parcours/')
    assert reponse.status_code == 302
    assert str(formation.pk) in reponse['Location']


@pytest.mark.django_db
def test_mes_competences_separe_l_acquis_de_l_expire(
        client, formation, entreprise, apprenant_admin, chef_admin):
    """Une habilitation expirée n'est pas une habilitation : l'écran les
    sépare au lieu de les mélanger dans une liste « validées »."""
    import datetime

    from apps.internal_training import parcours

    formation.competences.add(_competence(entreprise, code='VIVE'))
    formation.competences.add(
        _competence(entreprise, code='PERIMEE', validite_mois=12))
    demandes = parcours.ouvrir_les_validations_terrain(
        formation, apprenant_admin)

    for demande in demandes:
        if demande.competence.code == 'PERIMEE':
            parcours.prononcer_une_validation(
                demande, chef_admin, 'validee',
                constatee_le=timezone.now() - datetime.timedelta(days=400))
        else:
            parcours.prononcer_une_validation(
                demande, chef_admin, 'validee')

    client.force_login(apprenant_admin)
    reponse = client.get('/erp/formations/competences/mes-competences/')
    assert reponse.status_code == 200

    acquises = [v.competence.code for v in reponse.context['acquises']]
    expirees = [v.competence.code for v in reponse.context['expirees']]
    assert acquises == ['VIVE']
    assert expirees == ['PERIMEE']


@pytest.mark.django_db
def test_l_ecran_du_valideur_n_affiche_pas_ses_propres_demandes(
        client, formation, entreprise, apprenant_admin, chef_admin):
    """Se voir dans sa propre liste de validations n'aurait aucun sens, et
    inviterait à essayer."""
    from apps.internal_training import parcours

    formation.competences.add(_competence(entreprise, code='A'))
    parcours.ouvrir_les_validations_terrain(formation, apprenant_admin)
    parcours.ouvrir_les_validations_terrain(formation, chef_admin)

    client.force_login(chef_admin)
    reponse = client.get('/erp/formations/competences/validations/')
    assert reponse.status_code == 200

    attentes = list(reponse.context['attentes'])
    assert attentes, 'la liste ne devrait pas etre vide'
    assert all(v.apprenant_id != chef_admin.pk for v in attentes)
    assert any(v.apprenant_id == apprenant_admin.pk for v in attentes)


@pytest.mark.django_db
def test_le_valideur_ne_peut_pas_se_valider_par_l_adresse_directe(
        client, formation, entreprise, chef_admin):
    """La liste l'exclut ; l'adresse de l'action doit refuser aussi.

    Masquer un bouton n'est pas une sécurité : il suffit d'appeler
    l'adresse.
    """
    from apps.internal_training import parcours

    formation.competences.add(_competence(entreprise, code='SOLO'))
    validation = parcours.ouvrir_les_validations_terrain(
        formation, chef_admin)[0]

    client.force_login(chef_admin)
    reponse = client.post(
        f'/erp/formations/competences/validations/{validation.pk}/prononcer/',
        {'statut': 'validee'}, follow=True)

    assert reponse.status_code == 200
    validation.refresh_from_db()
    assert validation.statut == 'en_attente', (
        'une validation de soi-meme a ete acceptee par la vue')
    textes = [str(m) for m in reponse.context['messages']]
    assert any('acquiert' in t for t in textes), textes
