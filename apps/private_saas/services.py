"""
apps/private_saas/services.py — Services de gestion SaaS privé multi-entreprises
"""
import secrets
import string
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.text import slugify


def create_private_company(name: str, company_type: str = 'generic', created_by=None):
    """
    Crée une entreprise privée complète :
    1. PrivateCompany (= core.Company)
    2. Seed des modules selon le type
    Retourne l'instance Company créée.
    """
    from apps.core.models import Company
    from .models import ALL_MODULE_CODES

    slug = slugify(name)
    base_slug = slug
    i = 1
    while Company.objects.filter(slug=slug).exists():
        slug = f'{base_slug}-{i}'
        i += 1

    company = Company.objects.create(
        name=name,
        legal_name=name,
        slug=slug,
        sector=company_type,
        status='active',
        is_active=True,
        currency='EUR',
        timezone='Europe/Paris',
    )

    seed_company_modules(company, company_type, user=created_by)
    return company


def seed_company_modules(company, company_type: str = 'generic', user=None):
    """Initialise tous les CompanyModule pour une entreprise."""
    from .models import CompanyModule, DEFAULT_MODULES_BY_TYPE, MODULE_LABELS, ALL_MODULE_CODES

    enabled_codes = set(DEFAULT_MODULES_BY_TYPE.get(company_type, DEFAULT_MODULES_BY_TYPE['generic']))
    now = timezone.now()

    for code in ALL_MODULE_CODES:
        is_enabled = code in enabled_codes
        obj, created = CompanyModule.objects.get_or_create(
            company=company,
            module_code=code,
            defaults={
                'module_name': MODULE_LABELS.get(code, code),
                'is_enabled': is_enabled,
                'enabled_at': now if is_enabled else None,
                'enabled_by': user if is_enabled else None,
            },
        )
        if not created and obj.is_enabled != is_enabled:
            obj.is_enabled = is_enabled
            obj.save(update_fields=['is_enabled'])


def create_company_admin(company, email: str, password: str = None):
    """
    Crée un utilisateur administrateur et le rattache à l'entreprise.
    Retourne (user, password, created).
    """
    username = email.split('@')[0]
    base = username
    i = 1
    while User.objects.filter(username=username).exists():
        username = f'{base}{i}'
        i += 1

    if not password:
        chars = string.ascii_letters + string.digits + '!@#$%'
        password = ''.join(secrets.choice(chars) for _ in range(14))

    user, created = User.objects.get_or_create(
        email=email,
        defaults={'username': username, 'is_active': True},
    )
    if created:
        user.set_password(password)
        user.save()

    _link_user_to_company(user, company, role='admin')
    return user, password, created


def _link_user_to_company(user, company, role: str = 'admin'):
    """Rattache un utilisateur à une entreprise via UserCompanyAccess ou CompanyAccess."""
    try:
        from apps.access_control.models import UserCompanyAccess
        UserCompanyAccess.objects.get_or_create(
            user=user,
            company=company,
            defaults={'role': role, 'is_active': True, 'can_switch_company': True},
        )
        return
    except Exception:
        pass
    try:
        from apps.core.models import CompanyAccess
        CompanyAccess.objects.get_or_create(
            user=user,
            company=company,
            defaults={'role': role},
        )
    except Exception:
        pass


def activate_company(company):
    company.status = 'active'
    company.is_active = True
    company.save(update_fields=['status', 'is_active'])


def archive_company(company):
    company.status = 'archived'
    company.is_active = False
    company.save(update_fields=['status', 'is_active'])


def get_enabled_modules_for_company(company) -> list:
    from .models import CompanyModule
    return list(
        CompanyModule.objects.filter(company=company, is_enabled=True)
        .values_list('module_code', flat=True)
    )


def user_can_access_company(user, company) -> bool:
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


def get_accessible_companies(user):
    """Retourne les entreprises accessibles par un utilisateur."""
    from apps.core.models import Company
    if user.is_superuser:
        return Company.objects.filter(is_active=True).order_by('name')
    try:
        from apps.access_control.models import UserCompanyAccess
        company_ids = UserCompanyAccess.objects.filter(
            user=user, is_active=True
        ).values_list('company_id', flat=True)
        return Company.objects.filter(id__in=company_ids, is_active=True).order_by('name')
    except Exception:
        try:
            return user.profile.companies.filter(is_active=True).order_by('name')
        except Exception:
            return Company.objects.none()


def assign_all_data_to_company(company):
    """
    Rattache toutes les données existantes sans company à l'entreprise donnée.
    Utilisé lors de la migration initiale.
    """
    results = {}
    models_to_assign = [
        ('apps.crm', 'Customer'),
        ('apps.crm', 'Prospect'),
        ('apps.sales', 'Quote'),
        ('apps.sales', 'Order'),
        ('apps.sales', 'Invoice'),
        ('apps.purchases', 'Supplier'),
        ('apps.inventory', 'Product'),
        ('apps.inventory', 'Warehouse'),
        ('apps.btp', 'BTPProject'),
        ('apps.hr', 'Employee'),
        ('apps.documents', 'Document'),
        ('apps.websites', 'Website'),
        ('apps.ecommerce', 'OnlineOrder'),
    ]
    for app, model_name in models_to_assign:
        try:
            from django.apps import apps as django_apps
            Model = django_apps.get_model(app, model_name)
            if hasattr(Model, 'company_id'):
                updated = Model.objects.filter(company__isnull=True).update(company=company)
                results[f'{app}.{model_name}'] = updated
        except Exception as e:
            results[f'{app}.{model_name}'] = f'erreur: {e}'
    return results
