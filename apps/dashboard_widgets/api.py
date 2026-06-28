from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.dashboard_widgets.services import get_dashboard_widgets_for_user


def _get_company(request):
    return getattr(request, 'active_company', None) or getattr(request, 'current_company', None)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_widgets_api(request):
    company = _get_company(request)
    brand_key = request.GET.get("brand_key", "")
    widgets = get_dashboard_widgets_for_user(user=request.user, company=company, brand_key=brand_key)
    return Response({"widgets": widgets})
