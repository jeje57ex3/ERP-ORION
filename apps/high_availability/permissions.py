from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def super_admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not request.user.is_superuser:
            messages.error(request, 'Accès réservé au Super Admin Orion ERP.')
            return redirect('core:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper
