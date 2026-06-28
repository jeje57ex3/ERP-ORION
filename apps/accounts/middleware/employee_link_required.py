"""
Middleware optionnel : redirige les utilisateurs non-admin sans fiche salarié.
Pour l'activer, ajouter dans settings.py MIDDLEWARE :
    'apps.accounts.middleware.employee_link_required.EmployeeLinkRequiredMiddleware',
"""
from django.shortcuts import redirect
from django.urls import reverse

from apps.accounts.services.user_employee_link_service import (
    is_user_exempt_from_employee_link,
    get_user_employee,
)

# Chemins toujours accessibles (même sans fiche salarié)
ALLOWED_PATHS = [
    '/accounts/login/',
    '/accounts/logout/',
    '/accounts/missing-employee/',
    '/admin/',
    '/static/',
    '/media/',
]


class EmployeeLinkRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)

        if user and user.is_authenticated:
            if not is_user_exempt_from_employee_link(user):
                if not get_user_employee(user):
                    path = request.path
                    if not any(path.startswith(p) for p in ALLOWED_PATHS):
                        return redirect(reverse('accounts:missing_employee'))

        return self.get_response(request)
