from django.utils import timezone
from .models import (
    TrainingCourse, TrainingChapter, TrainingPage,
    TrainingPageBlock, TrainingEnrollment, TrainingPageProgress,
)


def create_course(*, company, title, description='', created_by=None) -> TrainingCourse:
    order = TrainingCourse.objects.filter(company=company).count()
    return TrainingCourse.objects.create(
        company=company,
        title=title,
        description=description,
        created_by=created_by,
        order=order,
    )


def update_course(*, course: TrainingCourse, title, description='', cover_image=None) -> TrainingCourse:
    course.title = title
    course.description = description
    if cover_image is not None:
        course.cover_image = cover_image
    course.save()
    return course


def publish_course(course: TrainingCourse) -> TrainingCourse:
    course.status = 'published'
    course.save(update_fields=['status', 'updated_at'])
    return course


def unpublish_course(course: TrainingCourse) -> TrainingCourse:
    course.status = 'draft'
    course.save(update_fields=['status', 'updated_at'])
    return course


def delete_course(course: TrainingCourse) -> None:
    course.delete()


def create_chapter(*, course: TrainingCourse, title) -> TrainingChapter:
    order = course.chapters.count()
    return TrainingChapter.objects.create(course=course, title=title, order=order)


def update_chapter(*, chapter: TrainingChapter, title) -> TrainingChapter:
    chapter.title = title
    chapter.save(update_fields=['title'])
    return chapter


def delete_chapter(chapter: TrainingChapter) -> None:
    chapter.delete()


def create_page(*, chapter: TrainingChapter, title) -> TrainingPage:
    order = chapter.pages.count()
    return TrainingPage.objects.create(chapter=chapter, title=title, order=order)


def update_page(*, page: TrainingPage, title, status=None) -> TrainingPage:
    page.title = title
    if status:
        page.status = status
    page.save()
    return page


def delete_page(page: TrainingPage) -> None:
    page.delete()


def add_block(*, page: TrainingPage, block_type, content='', file=None) -> TrainingPageBlock:
    order = page.blocks.count()
    return TrainingPageBlock.objects.create(
        page=page,
        block_type=block_type,
        content=content,
        file=file,
        order=order,
    )


def update_block(*, block: TrainingPageBlock, content='', file=None) -> TrainingPageBlock:
    block.content = content
    if file is not None:
        block.file = file
    block.save()
    return block


def delete_block(block: TrainingPageBlock) -> None:
    block.delete()


def reorder_blocks(*, page: TrainingPage, ordered_ids: list[int]) -> None:
    for idx, block_id in enumerate(ordered_ids):
        TrainingPageBlock.objects.filter(pk=block_id, page=page).update(order=idx)


def enroll_user(*, course: TrainingCourse, user) -> TrainingEnrollment:
    enrollment, _ = TrainingEnrollment.objects.get_or_create(course=course, user=user)
    return enrollment


def mark_page_complete(*, page: TrainingPage, user) -> TrainingPageProgress:
    progress, _ = TrainingPageProgress.objects.get_or_create(page=page, user=user)
    if not progress.is_completed:
        progress.is_completed = True
        progress.completed_at = timezone.now()
        progress.save(update_fields=['is_completed', 'completed_at'])
    return progress


def check_enrollment_completed(*, enrollment: TrainingEnrollment) -> bool:
    """Auto-complete enrollment if all published pages are done."""
    course = enrollment.course
    total_pages = TrainingPage.objects.filter(
        chapter__course=course, status='published',
    ).count()
    if total_pages == 0:
        return False
    completed = TrainingPageProgress.objects.filter(
        page__chapter__course=course,
        user=enrollment.user,
        is_completed=True,
    ).count()
    if completed >= total_pages:
        enrollment.completed_at = timezone.now()
        enrollment.save(update_fields=['completed_at'])
        return True
    return False
