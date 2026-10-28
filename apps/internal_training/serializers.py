from .models import (
    TrainingCourse, TrainingChapter, TrainingPage,
    TrainingPageBlock, TrainingEnrollment, TrainingPageProgress,
)


def serialize_block(block: TrainingPageBlock) -> dict:
    return {
        'id': block.pk,
        'type': block.block_type,
        'content': block.content,
        'file_url': block.file.url if block.file else None,
        'order': block.order,
    }


def serialize_page(page: TrainingPage, completed_ids: set = None) -> dict:
    completed_ids = completed_ids or set()
    return {
        'id': page.pk,
        'title': page.title,
        'status': page.status,
        'order': page.order,
        'is_completed': page.pk in completed_ids,
        'blocks': [serialize_block(b) for b in page.blocks.all()],
    }


def serialize_chapter(chapter: TrainingChapter, completed_ids: set = None) -> dict:
    return {
        'id': chapter.pk,
        'title': chapter.title,
        'order': chapter.order,
        'pages': [serialize_page(p, completed_ids) for p in chapter.pages.all()],
    }


def serialize_course(course: TrainingCourse) -> dict:
    return {
        'id': course.pk,
        'title': course.title,
        'description': course.description,
        'status': course.status,
        'chapters_count': course.chapters_count,
        'pages_count': course.pages_count,
        'enrolled_count': course.enrolled_count,
    }
