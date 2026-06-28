"""
access_control/decorators.py
Décorateurs de protection des vues Django.
"""
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from .services import user_has_module_access, user_has_view_access, user_has_action_access


def _get_company(request):
    return getattr(request, 'current_company', None)


def module_required(module_code):
    """Exige l'accès au module. Redirige avec message si refusé."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('accounts:login')
            company = _get_company(request)
            if not company or not user_has_module_access(request.user, company, module_code):
                messages.error(request, f"Vous n'avez pas accès au module « {module_code} ».")
                return redirect('core:dashboard')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def view_required(view_code):
    """Exige l'accès à une vue précise."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('accounts:login')
            company = _get_company(request)
            if not company or not user_has_view_access(request.user, company, view_code):
                messages.error(request, "Vous n'avez pas accès à cette page.")
                return redirect('core:dashboard')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def action_required(module_code, action_code):
    """Exige la capacité d'effectuer une action dans un module."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('accounts:login')
            company = _get_company(request)
            if not company or not user_has_action_access(request.user, company, module_code, action_code):
                messages.error(request, "Vous n'avez pas la permission d'effectuer cette action.")
                return redirect('core:dashboard')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
