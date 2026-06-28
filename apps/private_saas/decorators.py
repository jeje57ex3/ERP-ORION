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
