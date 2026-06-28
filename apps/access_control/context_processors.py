"""
access_control/context_processors.py
Injecte les modules accessibles et permissions dans chaque template.
"""
from .services import get_user_modules, get_user_sidebar_items, user_has_action_access


def available_modules(request):
    if not request.user.is_authenticated:
        return {'available_modules': [], 'sidebar_items': []}
    company = getattr(request, 'current_company', None)
    if not company:
        return {'available_modules': [], 'sidebar_items': []}
    modules = get_user_modules(request.user, company)
    sidebar = get_user_sidebar_items(request.user, company)
    return {
        'available_modules': modules,
        'sidebar_items': sidebar,
    }


def current_company_permissions(request):
    """Expose un dict de permissions rapides pour les templates."""
    if not request.user.is_authenticated:
        return {'perms_map': {}}
    company = getattr(request, 'current_company', None)
    if not company:
        return {'perms_map': {}}

    modules_to_check = [
        'dashboard', 'crm', 'sales', 'accounting', 'purchases', 'inventory',
        'btp', 'hr', 'payroll', 'documents', 'support', 'ecommerce',
        'commerce', 'production', 'audio', 'websites', 'reporting', 'settings',
    ]
    perms_map = {}
    for mod in modules_to_check:
        from .services import user_has_module_access
        perms_map[mod] = user_has_module_access(request.user, company, mod)

    return {'perms_map': perms_map}
