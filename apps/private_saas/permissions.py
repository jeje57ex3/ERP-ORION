"""
apps/private_saas/permissions.py — Permissions multi-entreprises Orion ERP
"""
from .models import ALL_MODULE_CODES


def company_has_module(company, module_code: str) -> bool:
    """Vérifie si un module est activé pour une entreprise.

    Délègue à `module_access.company_has_module`, qui est la source de vérité
    employée par les décorateurs d'accès. Les deux implémentations avaient
    divergé sur le cas le plus important : sans entreprise, celle-ci répondait
    True — « pas d'entreprise, pas de filtre » — là où celle du contrôle
    d'accès répond False. Deux réponses opposées à la même question, et c'est
    la permissive qui alimentait le menu : un utilisateur sans entreprise
    active se voyait proposer tous les modules, y compris ceux que son
    exploitant n'a pas souscrits.

    Sans entreprise, aucune donnée métier ne peut être cloisonnée : refuser
    est la seule réponse cohérente.
    """
    from apps.private_saas.module_access import (
        company_has_module as _module_actif,
    )
    return _module_actif(company, module_code)


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
    est_super_admin = bool(user and getattr(user, 'is_superuser', False))

    if company is None:
        # Sans entreprise active, cette fonction renvoyait la liste ENTIERE.
        # Consequence : un utilisateur ordinaire voyait le menu Super Admin,
        # et tous les modules metier que son exploitant n'a pas souscrits.
        # On applique donc les memes regles qu'avec une entreprise, en
        # considerant qu'aucun module metier n'est actif -- ce qui est le cas,
        # puisqu'il n'y a pas d'entreprise pour les activer.
        always_show = {'dashboard', 'erp_overview', 'settings'}
        super_admin_only = {'private_saas'}
        sans_entreprise = []
        for module in nav_modules:
            mid = module.get('id', '')
            if mid in super_admin_only or module.get('super_admin_only'):
                if est_super_admin:
                    sans_entreprise.append(module)
                continue
            if mid in always_show:
                sans_entreprise.append(module)
        return sans_entreprise

    if est_super_admin:
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
