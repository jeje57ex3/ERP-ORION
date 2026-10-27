from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.user_security.models import UserRecoveryCode
from apps.user_security.services import get_or_create_2fa_settings


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def two_factor_status_api(request):
    settings_obj = get_or_create_2fa_settings(request.user)
    return Response({
        "is_enabled": settings_obj.is_enabled,
        "confirmed_at": settings_obj.confirmed_at,
        "last_verified_at": settings_obj.last_verified_at,
        "recovery_codes_remaining": UserRecoveryCode.objects.filter(
            user=request.user, used_at__isnull=True
        ).count(),
    })
