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
