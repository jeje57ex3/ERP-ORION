"""
apps/private_saas/module_access.py — Service central d'accès aux modules par entreprise.

Source de vérité unique pour savoir quels modules sont actifs pour une entreprise.
Utilise CompanyModule (modèle existant lié à core.Company).
"""
from django.utils import timezone


# Modules activés par défaut pour toute nouvelle entreprise
DEFAULT_COMPANY_MODULES = [
    "dashboard",
    "orders",
    "customers",
    "products",
    "inventory",
    "payments",
    "website_shop_settings",
    "orion_ai",
    "continuous_improvement",
    "idea_engine",
    "reports",
    "team",
    "internal_training",
    "work_planning",
    "site_customization",
]

# Tous les codes modules reconnus (synchronisé avec ALL_MODULE_CODES du modèle)
from apps.private_saas.models import ALL_MODULE_CODES as _ALL_MODULE_CODES

ALL_MODULE_CODES = _ALL_MODULE_CODES


def normalize_module_code(module_code: str) -> str:
    return str(module_code or "").strip().lower()


def seed_company_modules(company, enabled_modules=None, user=None, force_enable_defaults=False):
    """Crée les lignes CompanyModule manquantes pour une entreprise.

    Ne détruit pas les réglages existants sauf si force_enable_defaults=True.
    """
    if not company:
        return []

    from apps.private_saas.models import CompanyModule, MODULE_LABELS

    enabled_set = set(
        normalize_module_code(c)
        for c in (enabled_modules if enabled_modules is not None else DEFAULT_COMPANY_MODULES)
    )

    result = []
    for module_code in ALL_MODULE_CODES:
        should_enable = module_code in enabled_set

        obj, created = CompanyModule.objects.get_or_create(
            company=company,
            module_code=module_code,
            defaults={
                'module_name': MODULE_LABELS.get(module_code, module_code),
                'is_enabled': should_enable,
                'enabled_at': timezone.now() if should_enable else None,
                'enabled_by': user if should_enable else None,
            },
        )

        if not created and force_enable_defaults and should_enable and not obj.is_enabled:
            obj.is_enabled = True
            obj.enabled_by = user
            obj.enabled_at = timezone.now()
            obj.save(update_fields=['is_enabled', 'enabled_by', 'enabled_at'])

        result.append(obj)

    return result


def enable_company_module(company, module_code: str, user=None):
    """Active un module pour une entreprise."""
    module_code = normalize_module_code(module_code)
    from apps.private_saas.models import CompanyModule, MODULE_LABELS

    obj, _ = CompanyModule.objects.get_or_create(
        company=company,
        module_code=module_code,
        defaults={'module_name': MODULE_LABELS.get(module_code, module_code)},
    )
    obj.is_enabled = True
    obj.enabled_at = timezone.now()
    if user:
        obj.enabled_by = user
    obj.save(update_fields=['is_enabled', 'enabled_at', 'enabled_by'])
    return obj


def disable_company_module(company, module_code: str):
    """Désactive un module pour une entreprise."""
    module_code = normalize_module_code(module_code)
    from apps.private_saas.models import CompanyModule, MODULE_LABELS

    obj, _ = CompanyModule.objects.get_or_create(
        company=company,
        module_code=module_code,
        defaults={'module_name': MODULE_LABELS.get(module_code, module_code)},
    )
    obj.is_enabled = False
    obj.save(update_fields=['is_enabled'])
    return obj


def company_has_module(company, module_code: str) -> bool:
    """Retourne True si le module est activé pour l'entreprise. False si aucune entreprise."""
    if not company:
        return False
    module_code = normalize_module_code(module_code)
    try:
        from apps.private_saas.models import CompanyModule
        return CompanyModule.objects.filter(
            company=company,
            module_code=module_code,
            is_enabled=True,
        ).exists()
    except Exception:
        return False


def get_enabled_company_modules(company) -> set[str]:
    """Retourne l'ensemble des codes modules activés. Vide si pas d'entreprise."""
    if not company:
        return set()
    try:
        from apps.private_saas.models import CompanyModule
        return set(
            CompanyModule.objects.filter(company=company, is_enabled=True)
            .values_list('module_code', flat=True)
        )
    except Exception:
        return set()


def get_company_modules_map(company) -> dict[str, bool]:
    """Retourne {module_code: is_enabled} pour tous les modules d'une entreprise."""
    if not company:
        return {}
    try:
        from apps.private_saas.models import CompanyModule
        return {
            obj.module_code: obj.is_enabled
            for obj in CompanyModule.objects.filter(company=company)
        }
    except Exception:
        return {}


def debug_company_modules(company) -> dict:
    """Retourne un dict de debug avec modules activés/désactivés."""
    if not company:
        return {'company': None, 'enabled': [], 'disabled': []}

    try:
        from apps.private_saas.models import CompanyModule
        enabled, disabled = [], []
        for obj in CompanyModule.objects.filter(company=company).order_by('module_code'):
            (enabled if obj.is_enabled else disabled).append(obj.module_code)
        return {
            'company': company.name,
            'company_id': company.pk,
            'enabled': enabled,
            'disabled': disabled,
        }
    except Exception as e:
        return {'company': str(company), 'error': str(e), 'enabled': [], 'disabled': []}
