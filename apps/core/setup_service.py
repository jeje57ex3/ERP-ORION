"""
Service pour l'assistant de premier accès (/setup/) — crée la première
Company et le premier compte administrateur. Remplace l'ancienne création
du superadmin faite par le wizard console de l'appliance Proxmox
(deployment/proxmox-appliance/provisioning/first-boot-wizard.sh).
"""
from django.contrib.auth.models import User
from django.db import transaction

from .models import Company


def complete_initial_setup(*, company_name, admin_email, admin_password, timezone):
    """
    Crée la première Company + le premier superutilisateur, et les relie.
    Ne doit être appelée que lorsque aucune Company n'existe encore
    (garde assurée par SetupRequiredMiddleware / SetupView).

    Retourne l'utilisateur créé (déjà lié à son profil et à son entreprise).
    """
    with transaction.atomic():
        company = Company.objects.create(name=company_name, timezone=timezone)
        # CompanySettings est créé automatiquement par le signal post_save
        # (apps/core/signals.py::create_company_settings).

        user = User.objects.create_superuser(
            username='admin',
            email=admin_email,
            password=admin_password,
        )
        # UserProfile est créé automatiquement par le signal post_save
        # (apps/accounts/signals.py::create_user_profile).
        profile = user.profile
        profile.companies.add(company)
        profile.current_company = company
        profile.role = 'superadmin'
        profile.timezone = timezone
        profile.save(update_fields=['current_company', 'role', 'timezone'])

        try:
            from apps.access_control.models import UserCompanyAccess
            UserCompanyAccess.objects.get_or_create(
                user=user, company=company,
                defaults={'is_active': True, 'can_switch_company': True},
            )
        except Exception:
            pass  # module access_control non installé/migré : pas bloquant

    return user
