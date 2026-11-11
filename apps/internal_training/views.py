from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.http import Http404

from apps.private_saas.decorators import require_company_module
from .models import TrainingCourse, TrainingChapter, TrainingPage, TrainingPageBlock
from .forms import TrainingCourseForm, TrainingChapterForm, TrainingPageForm, TrainingPageBlockForm
from .services import (
    create_course, update_course, publish_course, unpublish_course, delete_course,
    create_chapter, update_chapter, delete_chapter,
    create_page, update_page, delete_page,
    add_block, update_block, delete_block,
    enroll_user, mark_page_complete, check_enrollment_completed,
)
from .selectors import (
    get_courses_for_company, get_published_courses, get_enrolled_courses,
    get_course_detail, get_page_with_blocks, get_dashboard_stats,
    get_enrollment, get_completed_page_ids,
)


@login_required
@require_company_module('internal_training')
def dashboard(request):
    company = request.current_company
    stats = get_dashboard_stats(company)
    my_courses = get_enrolled_courses(request.user, company)
    all_published = get_published_courses(company)

    return render(request, 'internal_training/dashboard.html', {
        'page_title': 'Formations internes',
        'stats': stats,
        'my_courses': my_courses,
        'all_published': all_published,
    })


@login_required
@require_company_module('internal_training')
def course_list(request):
    company = request.current_company
    courses = get_courses_for_company(company)
    return render(request, 'internal_training/course_list.html', {
        'page_title': 'Toutes les formations',
        'courses': courses,
    })


@login_required
@require_company_module('internal_training')
def course_create(request):
    company = request.current_company
    if request.method == 'POST':
        form = TrainingCourseForm(request.POST, request.FILES)
        if form.is_valid():
            course = create_course(
                company=company,
                title=form.cleaned_data['title'],
                description=form.cleaned_data['description'],
                created_by=request.user,
            )
            if form.cleaned_data.get('cover_image'):
                course.cover_image = form.cleaned_data['cover_image']
                course.save(update_fields=['cover_image'])
            messages.success(request, f'Formation « {course.title} » créée.')
            return redirect('internal_training:course_detail', pk=course.pk)
    else:
        form = TrainingCourseForm()
    return render(request, 'internal_training/course_form.html', {
        'page_title': 'Nouvelle formation',
        'form': form,
        'action': 'create',
    })


@login_required
@require_company_module('internal_training')
def course_edit(request, pk):
    company = request.current_company
    course = get_object_or_404(TrainingCourse, pk=pk, company=company)
    if request.method == 'POST':
        form = TrainingCourseForm(request.POST, request.FILES, instance=course)
        if form.is_valid():
            update_course(
                course=course,
                title=form.cleaned_data['title'],
                description=form.cleaned_data['description'],
                cover_image=form.cleaned_data.get('cover_image'),
            )
            messages.success(request, 'Formation modifiée.')
            return redirect('internal_training:course_detail', pk=course.pk)
    else:
        form = TrainingCourseForm(instance=course)
    return render(request, 'internal_training/course_form.html', {
        'page_title': f'Modifier — {course.title}',
        'form': form,
        'course': course,
        'action': 'edit',
    })


@login_required
@require_company_module('internal_training')
def course_publish_toggle(request, pk):
    company = request.current_company
    course = get_object_or_404(TrainingCourse, pk=pk, company=company)
    if course.status == 'published':
        unpublish_course(course)
        messages.success(request, f'Formation « {course.title} » dépubliée.')
    else:
        publish_course(course)
        messages.success(request, f'Formation « {course.title} » publiée.')
    return redirect('internal_training:course_detail', pk=course.pk)


@login_required
@require_company_module('internal_training')
def course_delete(request, pk):
    company = request.current_company
    course = get_object_or_404(TrainingCourse, pk=pk, company=company)
    if request.method == 'POST':
        title = course.title
        delete_course(course)
        messages.success(request, f'Formation « {title} » supprimée.')
        return redirect('internal_training:course_list')
    return render(request, 'internal_training/course_form.html', {
        'page_title': f'Supprimer — {course.title}',
        'course': course,
        'action': 'delete',
        'form': None,
    })


@login_required
@require_company_module('internal_training')
def course_detail(request, pk):
    company = request.current_company
    course = get_object_or_404(
        TrainingCourse.objects.prefetch_related('chapters__pages'),
        pk=pk, company=company,
    )
    enrollment = get_enrollment(request.user, course)
    completed_page_ids = get_completed_page_ids(request.user, course) if enrollment else set()
    return render(request, 'internal_training/course_detail.html', {
        'page_title': course.title,
        'course': course,
        'enrollment': enrollment,
        'completed_page_ids': completed_page_ids,
    })


# ── Chapitres ─────────────────────────────────────────────────────────────────

@login_required
@require_company_module('internal_training')
def chapter_create(request, course_pk):
    company = request.current_company
    course = get_object_or_404(TrainingCourse, pk=course_pk, company=company)
    if request.method == 'POST':
        form = TrainingChapterForm(request.POST)
        if form.is_valid():
            chapter = create_chapter(course=course, title=form.cleaned_data['title'])
            messages.success(request, f'Chapitre « {chapter.title} » ajouté.')
            return redirect('internal_training:course_detail', pk=course.pk)
    else:
        form = TrainingChapterForm()
    return render(request, 'internal_training/chapter_form.html', {
        'page_title': 'Nouveau chapitre',
        'form': form,
        'course': course,
        'action': 'create',
    })


@login_required
@require_company_module('internal_training')
def chapter_edit(request, pk):
    chapter = get_object_or_404(
        TrainingChapter, pk=pk, course__company=request.current_company,
    )
    if request.method == 'POST':
        form = TrainingChapterForm(request.POST, instance=chapter)
        if form.is_valid():
            update_chapter(chapter=chapter, title=form.cleaned_data['title'])
            messages.success(request, 'Chapitre modifié.')
            return redirect('internal_training:course_detail', pk=chapter.course_id)
    else:
        form = TrainingChapterForm(instance=chapter)
    return render(request, 'internal_training/chapter_form.html', {
        'page_title': f'Modifier — {chapter.title}',
        'form': form,
        'chapter': chapter,
        'course': chapter.course,
        'action': 'edit',
    })


@login_required
@require_company_module('internal_training')
def chapter_delete(request, pk):
    chapter = get_object_or_404(
        TrainingChapter, pk=pk, course__company=request.current_company,
    )
    if request.method == 'POST':
        course_pk = chapter.course_id
        delete_chapter(chapter)
        messages.success(request, 'Chapitre supprimé.')
        return redirect('internal_training:course_detail', pk=course_pk)
    return redirect('internal_training:course_detail', pk=chapter.course_id)


# ── Pages ─────────────────────────────────────────────────────────────────────

@login_required
@require_company_module('internal_training')
def page_create(request, chapter_pk):
    chapter = get_object_or_404(
        TrainingChapter, pk=chapter_pk, course__company=request.current_company,
    )
    if request.method == 'POST':
        form = TrainingPageForm(request.POST)
        if form.is_valid():
            page = create_page(chapter=chapter, title=form.cleaned_data['title'])
            messages.success(request, f'Page « {page.title} » créée.')
            return redirect('internal_training:page_editor', pk=page.pk)
    else:
        form = TrainingPageForm()
    return render(request, 'internal_training/page_form.html', {
        'page_title': 'Nouvelle page',
        'form': form,
        'chapter': chapter,
        'action': 'create',
    })


@login_required
@require_company_module('internal_training')
def page_edit(request, pk):
    page = get_object_or_404(
        TrainingPage, pk=pk, chapter__course__company=request.current_company,
    )
    if request.method == 'POST':
        form = TrainingPageForm(request.POST, instance=page)
        if form.is_valid():
            update_page(
                page=page,
                title=form.cleaned_data['title'],
                status=form.cleaned_data.get('status'),
            )
            messages.success(request, 'Page modifiée.')
            return redirect('internal_training:page_editor', pk=page.pk)
    else:
        form = TrainingPageForm(instance=page)
    return render(request, 'internal_training/page_form.html', {
        'page_title': f'Modifier — {page.title}',
        'form': form,
        'page': page,
        'chapter': page.chapter,
        'action': 'edit',
    })


@login_required
@require_company_module('internal_training')
def page_delete(request, pk):
    page = get_object_or_404(
        TrainingPage, pk=pk, chapter__course__company=request.current_company,
    )
    if request.method == 'POST':
        chapter = page.chapter
        delete_page(page)
        messages.success(request, 'Page supprimée.')
        return redirect('internal_training:course_detail', pk=chapter.course_id)
    return redirect('internal_training:course_detail', pk=page.chapter.course_id)


# ── Éditeur de blocs ──────────────────────────────────────────────────────────

@login_required
@require_company_module('internal_training')
def page_editor(request, pk):
    page = get_object_or_404(
        TrainingPage.objects.prefetch_related('blocks').select_related('chapter__course'),
        pk=pk, chapter__course__company=request.current_company,
    )
    block_form = TrainingPageBlockForm()
    return render(request, 'internal_training/page_editor.html', {
        'page_title': f'Éditeur — {page.title}',
        'page': page,
        'block_form': block_form,
    })


@login_required
@require_company_module('internal_training')
def block_add(request, page_pk):
    page = get_object_or_404(
        TrainingPage, pk=page_pk, chapter__course__company=request.current_company,
    )
    if request.method == 'POST':
        form = TrainingPageBlockForm(request.POST, request.FILES)
        if form.is_valid():
            add_block(
                page=page,
                block_type=form.cleaned_data['block_type'],
                content=form.cleaned_data.get('content', ''),
                file=form.cleaned_data.get('file'),
            )
            messages.success(request, 'Bloc ajouté.')
    return redirect('internal_training:page_editor', pk=page.pk)


@login_required
@require_company_module('internal_training')
def block_edit(request, pk):
    block = get_object_or_404(
        TrainingPageBlock, pk=pk,
        page__chapter__course__company=request.current_company,
    )
    if request.method == 'POST':
        form = TrainingPageBlockForm(request.POST, request.FILES, instance=block)
        if form.is_valid():
            update_block(
                block=block,
                content=form.cleaned_data.get('content', ''),
                file=form.cleaned_data.get('file'),
            )
            messages.success(request, 'Bloc modifié.')
    return redirect('internal_training:page_editor', pk=block.page_id)


@login_required
@require_company_module('internal_training')
def block_delete(request, pk):
    block = get_object_or_404(
        TrainingPageBlock, pk=pk,
        page__chapter__course__company=request.current_company,
    )
    if request.method == 'POST':
        page_pk = block.page_id
        delete_block(block)
        messages.success(request, 'Bloc supprimé.')
        return redirect('internal_training:page_editor', pk=page_pk)
    return redirect('internal_training:page_editor', pk=block.page_id)


# ── Vue apprenant ─────────────────────────────────────────────────────────────

@login_required
@require_company_module('internal_training')
def page_view(request, pk):
    page = get_object_or_404(
        TrainingPage.objects.prefetch_related('blocks').select_related('chapter__course'),
        pk=pk,
        chapter__course__company=request.current_company,
        status='published',
    )
    course = page.chapter.course
    enrollment = get_enrollment(request.user, course)
    if not enrollment:
        enroll_user(course=course, user=request.user)
        enrollment = get_enrollment(request.user, course)

    completed_page_ids = get_completed_page_ids(request.user, course)

    # Navigation : page suivante / précédente dans le chapitre
    chapter_pages = list(page.chapter.pages.filter(status='published').order_by('order'))
    current_idx = next((i for i, p in enumerate(chapter_pages) if p.pk == page.pk), 0)
    prev_page = chapter_pages[current_idx - 1] if current_idx > 0 else None
    next_page = chapter_pages[current_idx + 1] if current_idx < len(chapter_pages) - 1 else None

    if request.method == 'POST' and request.POST.get('action') == 'mark_complete':
        progress = mark_page_complete(page=page, user=request.user)
        check_enrollment_completed(enrollment=enrollment)
        messages.success(request, 'Page marquée comme terminée.')
        if next_page:
            return redirect('internal_training:page_view', pk=next_page.pk)
        return redirect('internal_training:course_detail', pk=course.pk)

    return render(request, 'internal_training/page_view.html', {
        'page_title': page.title,
        'page': page,
        'course': course,
        'enrollment': enrollment,
        'completed_page_ids': completed_page_ids,
        'prev_page': prev_page,
        'next_page': next_page,
        'is_completed': page.pk in completed_page_ids,
    })


# ── Inscription ───────────────────────────────────────────────────────────────

@login_required
@require_company_module('internal_training')
def course_enroll(request, pk):
    company = request.current_company
    course = get_object_or_404(TrainingCourse, pk=pk, company=company, status='published')
    enroll_user(course=course, user=request.user)
    messages.success(request, f'Vous êtes inscrit à « {course.title} ».')
    return redirect('internal_training:course_detail', pk=course.pk)


# ══════════════════════════════════════════════════════════════════════════
# Parcours : étapes, quiz, validation terrain
# ══════════════════════════════════════════════════════════════════════════
#
# Toutes les règles vivent dans parcours.py. Ces vues ne font que les
# appeler et afficher le résultat — y remettre une condition, c'est garantir
# qu'elle divergera de celle du service.


@login_required
@require_company_module('internal_training')
def parcours_view(request, pk):
    """La page de l'apprenant : où j'en suis, et ce qui est ouvert."""
    from . import parcours as moteur

    company = request.current_company
    course = get_object_or_404(
        TrainingCourse.objects.prefetch_related('chapters__pages',
                                                'competences'),
        pk=pk, company=company,
    )
    inscription = get_enrollment(request.user, course)
    if inscription is None:
        messages.info(
            request, 'Inscrivez-vous à cette formation pour suivre le '
                     'parcours.')
        return redirect('internal_training:course_detail', pk=course.pk)

    return render(request, 'internal_training/parcours.html', {
        'page_title': f'Parcours — {course.title}',
        'course': course,
        'enrollment': inscription,
        'etat': moteur.etat_du_parcours(course, request.user),
    })


@login_required
@require_company_module('internal_training')
def quiz_passer(request, pk):
    """Le quiz : GET affiche les questions, POST corrige.

    La correction est faite PAR LE SERVEUR à partir des identifiants de
    choix, et les choix d'une autre question sont ignorés — un identifiant
    falsifié dans le formulaire ne compte pas et ne fait pas échouer la
    correction.
    """
    from . import parcours as moteur

    company = request.current_company
    course = get_object_or_404(TrainingCourse, pk=pk, company=company)

    if get_enrollment(request.user, course) is None:
        raise Http404('Non inscrit à cette formation.')

    try:
        tentative = moteur.demarrer_une_tentative(course, request.user)
    except moteur.ParcoursRefuse as refus:
        messages.warning(request, str(refus))
        return redirect('internal_training:parcours', pk=course.pk)

    quiz = tentative.quiz
    questions = list(quiz.questions.prefetch_related('choix'))
    if quiz.melanger_les_questions and request.method == 'GET':
        import random
        random.shuffle(questions)

    if request.method == 'POST':
        choix_par_question = {}
        for question in quiz.questions.all():
            bruts = request.POST.getlist(f'question_{question.pk}')
            retenus = []
            for brut in bruts:
                try:
                    retenus.append(int(brut))
                except (TypeError, ValueError):
                    continue
            choix_par_question[question.pk] = retenus

        try:
            tentative = moteur.corriger_une_tentative(
                tentative, choix_par_question)
        except moteur.ParcoursRefuse as refus:
            messages.error(request, str(refus))
            return redirect('internal_training:parcours', pk=course.pk)

        if tentative.reussie:
            messages.success(
                request,
                f'Quiz réussi avec {tentative.score} %. Les validations sur '
                f'le terrain sont ouvertes.')
        else:
            messages.warning(
                request,
                f'{tentative.score} % — il en fallait '
                f'{tentative.note_minimale_appliquee} %.')
        return redirect('internal_training:quiz_resultat', pk=tentative.pk)

    return render(request, 'internal_training/quiz.html', {
        'page_title': quiz.titre,
        'course': course,
        'quiz': quiz,
        'tentative': tentative,
        'questions': questions,
    })


@login_required
@require_company_module('internal_training')
def quiz_resultat(request, pk):
    """Le détail d'une tentative corrigée.

    Une tentative n'est visible que par la personne qui l'a passée, ou par
    un responsable : un score est une donnée personnelle.
    """
    from .models import TentativeDeQuiz

    company = request.current_company
    tentative = get_object_or_404(
        TentativeDeQuiz.objects.select_related('quiz__course'),
        pk=pk, quiz__course__company=company)

    est_responsable = (request.user.is_superuser
                       or request.user.is_staff)
    if tentative.user_id != request.user.pk and not est_responsable:
        raise Http404('Tentative introuvable.')

    return render(request, 'internal_training/quiz_resultat.html', {
        'page_title': f'Résultat — {tentative.quiz.titre}',
        'tentative': tentative,
        'course': tentative.quiz.course,
        'reponses': tentative.reponses.select_related('question')
                                      .prefetch_related('choix_retenus',
                                                        'question__choix'),
    })


@login_required
@require_company_module('internal_training')
def validations_a_prononcer(request):
    """L'écran du responsable : ce qui attend un constat de terrain.

    On y voit les demandes de TOUTE l'entreprise sauf les siennes : une
    personne ne valide pas sa propre compétence, donc lui montrer ses
    propres demandes dans cette liste n'aurait aucun sens.
    """
    from .models import ValidationTerrain

    company = request.current_company
    attentes = (ValidationTerrain.objects
                .filter(statut='en_attente',
                        competence__company=company)
                .exclude(apprenant=request.user)
                .select_related('competence', 'apprenant', 'course')
                .order_by('demandee_le'))

    recentes = (ValidationTerrain.objects
                .filter(competence__company=company)
                .exclude(statut='en_attente')
                .select_related('competence', 'apprenant', 'valide_par')
                .order_by('-constatee_le')[:20])

    return render(request, 'internal_training/validations_terrain.html', {
        'page_title': 'Validations sur le terrain',
        'attentes': attentes,
        'recentes': recentes,
    })


@login_required
@require_company_module('internal_training')
def validation_prononcer(request, pk):
    """Enregistre le constat d'un responsable. POST uniquement."""
    from . import parcours as moteur
    from .models import ValidationTerrain

    company = request.current_company
    validation = get_object_or_404(
        ValidationTerrain, pk=pk, competence__company=company)

    if request.method != 'POST':
        return redirect('internal_training:validations_terrain')

    constatee = None
    brut = (request.POST.get('constatee_le') or '').strip()
    if brut:
        from django.utils.dateparse import parse_date, parse_datetime
        from django.utils import timezone as tz
        valeur = parse_datetime(brut)
        if valeur is None:
            jour = parse_date(brut)
            if jour is not None:
                import datetime
                valeur = datetime.datetime.combine(jour, datetime.time(12, 0))
        if valeur is not None:
            constatee = (tz.make_aware(valeur)
                         if tz.is_naive(valeur) else valeur)

    try:
        moteur.prononcer_une_validation(
            validation,
            request.user,
            request.POST.get('statut', ''),
            constatee_le=constatee,
            lieu=(request.POST.get('lieu') or '').strip(),
            commentaire=(request.POST.get('commentaire') or '').strip(),
            piece_jointe=request.FILES.get('piece_jointe'),
        )
    except moteur.ParcoursRefuse as refus:
        messages.error(request, str(refus))
        return redirect('internal_training:validations_terrain')

    messages.success(
        request,
        f'{validation.competence.code} — {validation.get_statut_display()} '
        f'pour {validation.apprenant.get_full_name() or validation.apprenant}.')
    return redirect('internal_training:validations_terrain')


@login_required
@require_company_module('internal_training')
def mes_competences(request):
    """Ce que la personne a acquis, et ce qui expire.

    Une habilitation expirée n'est pas une habilitation : l'écran les sépare
    au lieu de les mélanger dans une liste « validées ».
    """
    from .models import ValidationTerrain

    company = request.current_company
    toutes = (ValidationTerrain.objects
              .filter(apprenant=request.user, competence__company=company)
              .select_related('competence', 'valide_par', 'course'))

    acquises = [v for v in toutes if v.est_acquise]
    expirees = [v for v in toutes if v.est_expiree]
    attente = [v for v in toutes if v.statut == 'en_attente']
    refusees = [v for v in toutes if v.statut in ('refusee', 'a_revoir')]

    return render(request, 'internal_training/mes_competences.html', {
        'page_title': 'Mes compétences',
        'acquises': acquises,
        'expirees': expirees,
        'attente': attente,
        'refusees': refusees,
    })
