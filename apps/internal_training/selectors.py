from django.db.models import Count, Q
from .models import (
    TrainingCourse, TrainingChapter, TrainingPage,
    TrainingEnrollment, TrainingPageProgress,
)


def get_courses_for_company(company, status=None):
    qs = TrainingCourse.objects.filter(company=company)
    if status:
        qs = qs.filter(status=status)
    return qs.order_by('order', 'created_at')


def get_published_courses(company):
    return get_courses_for_company(company, status='published')


def get_enrolled_courses(user, company):
    return TrainingCourse.objects.filter(
        company=company,
        status='published',
        enrollments__user=user,
    ).order_by('order', 'created_at')


def get_course_detail(pk, company=None):
    qs = TrainingCourse.objects.prefetch_related('chapters__pages__blocks')
    if company:
        qs = qs.filter(company=company)
    return qs.get(pk=pk)


def get_page_with_blocks(pk):
    return TrainingPage.objects.prefetch_related('blocks').select_related(
        'chapter__course',
    ).get(pk=pk)


def get_user_progress_for_course(user, course):
    page_ids = TrainingPage.objects.filter(
        chapter__course=course,
    ).values_list('id', flat=True)
    done = set(
        TrainingPageProgress.objects.filter(
            user=user,
            page_id__in=page_ids,
            is_completed=True,
        ).values_list('page_id', flat=True)
    )
    return done


def get_dashboard_stats(company):
    courses = TrainingCourse.objects.filter(company=company)
    return {
        'total_courses': courses.count(),
        'published_courses': courses.filter(status='published').count(),
        'draft_courses': courses.filter(status='draft').count(),
        'total_enrollments': TrainingEnrollment.objects.filter(course__company=company).count(),
        'completed_enrollments': TrainingEnrollment.objects.filter(
            course__company=company, completed_at__isnull=False,
        ).count(),
    }


def get_enrollment(user, course):
    try:
        return TrainingEnrollment.objects.get(user=user, course=course)
    except TrainingEnrollment.DoesNotExist:
        return None


def get_completed_page_ids(user, course):
    return set(
        TrainingPageProgress.objects.filter(
            user=user,
            page__chapter__course=course,
            is_completed=True,
        ).values_list('page_id', flat=True)
    )
