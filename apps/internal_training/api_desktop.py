from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.models import Company
from apps.private_saas.module_access import company_has_module
from apps.private_saas.services import get_accessible_companies
from apps.internal_training.models import TrainingCourse


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def desktop_training_courses_api(request):
    company_id = request.GET.get("company_id")

    if not company_id:
        return Response({"detail": "Paramètre company_id requis."}, status=400)

    accessible = get_accessible_companies(request.user)
    company = accessible.filter(id=company_id, is_active=True).first()

    if not company:
        return Response({"detail": "Entreprise introuvable ou accès refusé."}, status=403)

    if not company_has_module(company, "internal_training"):
        return Response({"detail": "Module formations non activé pour cette entreprise."}, status=403)

    courses = TrainingCourse.objects.filter(company=company).order_by("order", "-created_at")

    return Response({
        "courses": [
            {
                "id": course.id,
                "title": course.title,
                "description": course.description,
                "status": course.status,
                "order": course.order,
                "chapters_count": course.chapters_count,
                "pages_count": course.pages_count,
                "created_at": course.created_at.isoformat(),
            }
            for course in courses
        ]
    })
