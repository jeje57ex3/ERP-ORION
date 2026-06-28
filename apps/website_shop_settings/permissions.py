from functools import wraps
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required


def shop_settings_access_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise PermissionDenied
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        company = getattr(request, 'current_company', None)
        if not company:
            raise PermissionDenied
        if hasattr(request.user, 'company_accesses'):
            access = request.user.company_accesses.filter(
                company=company,
                role__in=('admin', 'owner'),
                is_active=True,
            ).exists()
            if access:
                return view_func(request, *args, **kwargs)
        raise PermissionDenied
    return wrapper


def can_view_sensitive_settings(user):
    return user.is_authenticated and user.is_superuser
