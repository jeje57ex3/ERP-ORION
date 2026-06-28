"""
dashboard/permissions.py — Contrôle d'accès pour les widgets
"""


def user_has_module_access(user, company, module_code):
    if user.is_superuser:
        return True
    if not company:
        return False
    try:
        from apps.access_control.models import UserCompanyAccess, RolePermission, ERPModule
        uca = UserCompanyAccess.objects.filter(company=company, user=user, is_active=True).first()
        if uca and uca.is_company_admin:
            return True
        module = ERPModule.objects.filter(code=module_code, is_active=True).first()
        if not module:
            return True
        if uca and uca.role:
            perm = RolePermission.objects.filter(role=uca.role, module=module).exists()
            return perm
        from apps.access_control.models import UserPermissionOverride
        override = UserPermissionOverride.objects.filter(
            user=user, company=company, module=module, is_allowed=True
        ).exists()
        return override
    except Exception:
        return True


def user_can_see_accounting(user, company):
    if user.is_superuser:
        return True
    if not company:
        return False
    try:
        from apps.access_control.models import UserCompanyAccess
        uca = UserCompanyAccess.objects.filter(company=company, user=user, is_active=True).first()
        if uca and uca.is_company_admin:
            return True
    except Exception:
        pass
    return user_has_module_access(user, company, 'accounting')


def user_can_see_hr_data(user, company, employee=None):
    if user.is_superuser:
        return True
    if employee and employee.user == user:
        return True
    return user_has_module_access(user, company, 'hr')


def widget_is_accessible(user, company, widget):
    if not widget.is_active:
        return False
    if not widget.requires_permission:
        return True
    if user.is_superuser:
        return True
    module_code = widget.module_code or widget.permission_code
    if module_code:
        return user_has_module_access(user, company, module_code)
    return True
