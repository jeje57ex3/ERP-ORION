"""
apps/system_health/permissions.py — Contrôle d'accès granulaire (16.12).

Utilisation :
    @health_permission_required('can_view_errors')
    def my_view(request):
        ...

Les super-admins (`is_superuser`) ont toujours accès à tout.
"""
from functools import wraps
from django.http import HttpResponseForbidden
from django.shortcuts import redirect

from .models import HealthPermission, HealthAuditLog


def _get_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    return xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR')


def health_permission_required(perm, log_action=None):
    """
    Vérifie qu'un utilisateur a la permission granulaire `perm` sur la section Santé.
    Les super-admins sont toujours autorisés.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('/accounts/login/?next=' + request.path)

            # Super-admin : accès total
            if request.user.is_superuser:
                if log_action:
                    _audit(request, log_action)
                return view_func(request, *args, **kwargs)

            # Vérification permission granulaire
            try:
                hp = HealthPermission.objects.get(user=request.user)
                if not getattr(hp, perm, False):
                    return HttpResponseForbidden(
                        "Accès refusé : permission insuffisante pour la section Santé du système."
                    )
            except HealthPermission.DoesNotExist:
                return HttpResponseForbidden(
                    "Accès refusé : aucune permission configurée pour cet utilisateur."
                )

            if log_action:
                _audit(request, log_action)
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def _audit(request, action, target_type='', target_id='', description=''):
    """Enregistre une entrée d'audit pour la section Santé."""
    try:
        HealthAuditLog.objects.create(
            user=request.user if request.user.is_authenticated else None,
            action=action,
            target_type=target_type,
            target_id=str(target_id),
            description=description,
            ip_address=_get_ip(request),
        )
    except Exception:
        pass  # L'audit ne doit jamais bloquer la requête


def has_health_perm(user, perm):
    """Vérification de permission sans décorateur (pour templates/context)."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    try:
        hp = HealthPermission.objects.get(user=user)
        return getattr(hp, perm, False)
    except HealthPermission.DoesNotExist:
        return False
