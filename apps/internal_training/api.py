import json
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404

from apps.private_saas.decorators import require_company_module
from .models import TrainingCourse, TrainingPage, TrainingPageBlock
from .services import (
    mark_page_complete, check_enrollment_completed,
    reorder_blocks, enroll_user,
)
from .selectors import get_enrollment
from .serializers import serialize_block


@login_required
@require_company_module('internal_training')
def api_mark_page_complete(request, pk):
    page = get_object_or_404(
        TrainingPage, pk=pk,
        chapter__course__company=request.current_company,
        status='published',
    )
    course = page.chapter.course
    enrollment = get_enrollment(request.user, course)
    if not enrollment:
        enrollment = enroll_user(course=course, user=request.user)

    progress = mark_page_complete(page=page, user=request.user)
    course_completed = check_enrollment_completed(enrollment=enrollment)
    return JsonResponse({
        'ok': True,
        'is_completed': progress.is_completed,
        'course_completed': course_completed,
    })


@login_required
@require_company_module('internal_training')
@require_POST
def api_reorder_blocks(request, page_pk):
    page = get_object_or_404(
        TrainingPage, pk=page_pk,
        chapter__course__company=request.current_company,
    )
    try:
        data = json.loads(request.body)
        ordered_ids = [int(i) for i in data.get('order', [])]
    except (ValueError, KeyError):
        return JsonResponse({'ok': False, 'error': 'Données invalides'}, status=400)
    reorder_blocks(page=page, ordered_ids=ordered_ids)
    return JsonResponse({'ok': True})


@login_required
@require_company_module('internal_training')
def api_course_progress(request, pk):
    company = request.current_company
    course = get_object_or_404(TrainingCourse, pk=pk, company=company)
    from .selectors import get_completed_page_ids, get_enrollment
    enrollment = get_enrollment(request.user, course)
    completed = get_completed_page_ids(request.user, course) if enrollment else set()
    from .models import TrainingPage
    total = TrainingPage.objects.filter(
        chapter__course=course, status='published',
    ).count()
    return JsonResponse({
        'ok': True,
        'completed': len(completed),
        'total': total,
        'percent': round(len(completed) / total * 100) if total else 0,
        'enrollment_completed': enrollment.is_completed if enrollment else False,
    })
