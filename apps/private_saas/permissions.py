"""
apps/private_saas/permissions.py — Permissions multi-entreprises Orion ERP
"""
from .models import ALL_MODULE_CODES


def company_has_module(company, module_code: str) -> bool:
    """Vérifie si un module est activé pour une entreprise."""
    if company is None:
        return True
    try:
        from .models import CompanyModule
        return CompanyModule.objects.filter(
            company=company, module_code=module_code, is_enabled=True
        ).exists()
    except Exception:
        return True


def user_can_access_module(user, company, module_code: str) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return company_has_module(company, module_code)


def get_enabled_modules(company) -> list:
    """Retourne la liste des codes de modules activés pour une entreprise."""
    if company is None:
        return list(ALL_MODULE_CODES)
    try:
        from .models import CompanyModule
        return list(
            CompanyModule.objects.filter(company=company, is_enabled=True)
            .values_list('module_code', flat=True)
        )
    except Exception:
        return list(ALL_MODULE_CODES)


def user_has_company_access(user, company) -> bool:
    if user.is_superuser:
        return True
    try:
        from apps.access_control.models import UserCompanyAccess
        return UserCompanyAccess.objects.filter(
            user=user, company=company, is_active=True
        ).exists()
    except Exception:
        pass
    try:
        from apps.core.models import CompanyAccess
        return CompanyAccess.objects.filter(user=user, company=company).exists()
    except Exception:
        return False


def user_has_action_permission(user, company, permission_code: str) -> bool:
    if user.is_superuser:
        return True
    try:
        from apps.access_control.models import UserCompanyAccess
        access = UserCompanyAccess.objects.filter(
            user=user, company=company, is_active=True
        ).first()
        if not access:
            return False
        return getattr(access, 'role', '') in ('admin', 'owner', 'manager')
    except Exception:
        return False


def filter_nav_modules(nav_modules: list, company, user=None) -> list:
    """
    Filtre la liste nav_modules (context processor) selon les modules
    activés pour l'entreprise.
    Les super admins voient tout. Les entrées sans module_code mappé sont conservées.
    """
    if user and user.is_superuser:
        return nav_modules

    if company is None:
        return nav_modules

    try:
        from .models import CompanyModule, MODULE_NAV_IDS
        enabled = set(
            CompanyModule.objects.filter(company=company, is_enabled=True)
            .values_list('module_code', flat=True)
        )
    except Exception:
        return nav_modules

    always_show = {'dashboard', 'erp_overview', 'settings'}
    super_admin_only = {'private_saas'}

    is_superuser = user and user.is_superuser

    filtered = []
    for module in nav_modules:
        mid = module.get('id', '')

        # Module réservé super admin
        if mid in super_admin_only or module.get('super_admin_only'):
            if is_superuser:
                filtered.append(module)
            continue

        if mid in always_show:
            filtered.append(module)
            continue

        # Cherche si ce nav_id est couvert par un module activé
        covered = False
        for code, nav_ids in MODULE_NAV_IDS.items():
            if mid in nav_ids and code in enabled:
                covered = True
                break
        if covered:
            filtered.append(module)

    return filtered
