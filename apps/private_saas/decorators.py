"""
apps/private_saas/decorators.py — Décorateurs Super Admin Orion ERP
"""
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def super_admin_required(view_func):
    """Restreint la vue aux superusers Django uniquement."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not request.user.is_superuser:
            messages.error(request, 'Accès réservé au Super Admin Orion ERP.')
            return redirect('core:dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped


def require_company_module(module_code):
    """Bloque l'accès si le module n'est pas activé pour la société courante
    (apps.private_saas.module_access.company_has_module — même source de
    vérité que le sélecteur de modules du desktop ERP)."""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('accounts:login')
            from apps.private_saas.module_access import company_has_module
            company = getattr(request, 'current_company', None)
            if not request.user.is_superuser and not company_has_module(company, module_code):
                messages.error(request, "Ce module n'est pas activé pour votre entreprise.")
                return redirect('core:dashboard')
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator
