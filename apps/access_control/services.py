"""
access_control/services.py
Logique centralisée de vérification des permissions.

Priorité :
1. Superuser Django → accès total
2. Admin société (UserCompanyAccess.role.code == 'admin') → accès total sur sa société
3. Override explicite utilisateur → prend le dessus sur le rôle
4. Permission du rôle → accès selon le rôle attribué
5. Permission du service → accès selon le département de l'employé
6. Refus par défaut
"""
from django.contrib.auth.models import User
from .models import (
    ERPModule, ERPView, ERPAction,
    UserCompanyAccess, UserPermissionOverride, RolePermission, DepartmentAccess, AccessLog,
)


# ---------------------------------------------------------------------------
# Helpers salarié ↔ utilisateur
# ---------------------------------------------------------------------------

def get_employee_for_user(user):
    """Retourne la fiche Employee liée à cet utilisateur, ou None."""
    try:
        return user.employee_profile
    except Exception:
        return None


def user_has_employee_or_is_exempt(user):
    """
    Retourne True si l'utilisateur est admin/superuser OU s'il a une fiche salarié.
    Utile pour les vues RH, pointage, chantiers.
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    try:
        if user.profile.role in ('superadmin', 'admin'):
            return True
    except Exception:
        pass
    return get_employee_for_user(user) is not None


def _get_user_access(user, company):
    """Retourne le UserCompanyAccess ou None."""
    try:
        return UserCompanyAccess.objects.select_related('role').get(user=user, company=company, is_active=True)
    except UserCompanyAccess.DoesNotExist:
        return None


def _is_company_admin(access_obj):
    return access_obj and access_obj.role and access_obj.role.code in ('superadmin', 'admin')


def user_has_module_access(user, company, module_code):
    """Vérifie si l'utilisateur a accès au module (au moins en lecture)."""
    if user.is_superuser:
        return True
    access = _get_user_access(user, company)
    if not access:
        return False
    if _is_company_admin(access):
        return True

    try:
        module = ERPModule.objects.get(code=module_code, is_active=True)
    except ERPModule.DoesNotExist:
        return False

    # Override explicite
    override = UserPermissionOverride.objects.filter(
        user=user, company=company, module=module, view__isnull=True, action__isnull=True
    ).first()
    if override is not None:
        return override.allowed

    # Permission du rôle
    if access.role:
        perm = RolePermission.objects.filter(
            role=access.role, module=module, view__isnull=True, action__isnull=True
        ).first()
        if perm is not None:
            return perm.allowed

    return False


def user_has_view_access(user, company, view_code):
    """Vérifie l'accès à une vue précise."""
    if user.is_superuser:
        return True
    access = _get_user_access(user, company)
    if not access:
        return False
    if _is_company_admin(access):
        return True

    try:
        erp_view = ERPView.objects.select_related('module').get(code=view_code, is_active=True)
    except ERPView.DoesNotExist:
        # Si la vue n'est pas enregistrée, on vérifie l'accès module
        return False

    module = erp_view.module

    # Override explicite sur la vue
    override = UserPermissionOverride.objects.filter(
        user=user, company=company, module=module, view=erp_view, action__isnull=True
    ).first()
    if override is not None:
        return override.allowed

    # Permission de rôle sur la vue
    if access.role:
        perm = RolePermission.objects.filter(
            role=access.role, module=module, view=erp_view, action__isnull=True
        ).first()
        if perm is not None:
            return perm.allowed

    # Fallback : accès module
    return user_has_module_access(user, company, module.code)


def user_has_action_access(user, company, module_code, action_code):
    """Vérifie si l'utilisateur peut effectuer une action dans un module."""
    if user.is_superuser:
        return True
    access = _get_user_access(user, company)
    if not access:
        return False
    if _is_company_admin(access):
        return True

    try:
        module = ERPModule.objects.get(code=module_code, is_active=True)
        action = ERPAction.objects.get(code=action_code)
    except (ERPModule.DoesNotExist, ERPAction.DoesNotExist):
        return False

    # Override explicite
    override = UserPermissionOverride.objects.filter(
        user=user, company=company, module=module, action=action
    ).first()
    if override is not None:
        return override.allowed

    # Permission du rôle
    if access.role:
        perm = RolePermission.objects.filter(
            role=access.role, module=module, action=action
        ).first()
        if perm is not None:
            return perm.allowed

    return False


def get_user_modules(user, company):
    """Retourne la liste des modules accessibles à l'utilisateur."""
    if user.is_superuser:
        return ERPModule.objects.filter(is_active=True)

    access = _get_user_access(user, company)
    if not access:
        return ERPModule.objects.none()
    if _is_company_admin(access):
        return ERPModule.objects.filter(is_active=True)

    accessible_codes = set()
    if access.role:
        for perm in RolePermission.objects.filter(role=access.role, allowed=True, view__isnull=True, action__isnull=True).select_related('module'):
            accessible_codes.add(perm.module.code)

    # Overrides positifs
    for override in UserPermissionOverride.objects.filter(user=user, company=company, allowed=True, view__isnull=True, action__isnull=True).select_related('module'):
        accessible_codes.add(override.module.code)

    # Overrides négatifs
    for override in UserPermissionOverride.objects.filter(user=user, company=company, allowed=False, view__isnull=True, action__isnull=True).select_related('module'):
        accessible_codes.discard(override.module.code)

    return ERPModule.objects.filter(code__in=accessible_codes, is_active=True)


def get_user_sidebar_items(user, company):
    """Retourne un dict de modules avec leurs permissions pour la sidebar."""
    modules = get_user_modules(user, company)
    result = []
    for module in modules:
        result.append({
            'module': module,
            'can_create': user_has_action_access(user, company, module.code, 'create'),
            'can_edit': user_has_action_access(user, company, module.code, 'edit'),
            'can_delete': user_has_action_access(user, company, module.code, 'delete'),
            'can_export': user_has_action_access(user, company, module.code, 'export'),
            'can_admin': user_has_action_access(user, company, module.code, 'admin'),
        })
    return result


def log_access_attempt(user, company, module, view, action, allowed, reason=''):
    try:
        AccessLog.objects.create(
            user=user,
            company=company,
            module=module,
            view_code=view,
            action=action,
            allowed=allowed,
            reason=reason,
        )
    except Exception:
        pass
