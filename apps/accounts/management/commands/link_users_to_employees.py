"""
Commande de liaison automatique utilisateurs ↔ salariés par email.

Usage :
    python manage.py link_users_to_employees --dry-run
    python manage.py link_users_to_employees
    python manage.py link_users_to_employees --company-id=1
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

from apps.hr.models import Employee
from apps.accounts.services.user_employee_link_service import (
    is_user_exempt_from_employee_link,
    get_user_employee,
    link_user_to_employee,
)


class Command(BaseCommand):
    help = 'Lie automatiquement les utilisateurs non-admin à des salariés par email.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--company-id', type=int, default=None,
            help='Limiter la recherche à une entreprise (ID).',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Afficher les correspondances sans modifier la base.',
        )

    def handle(self, *args, **options):
        company_id = options.get('company_id')
        dry_run = options.get('dry_run')

        if dry_run:
            self.stdout.write(self.style.WARNING('— Mode DRY RUN — aucune modification —'))

        linked = 0
        missing = 0
        skipped = 0
        errors = 0

        for user in User.objects.select_related('profile').all():
            if is_user_exempt_from_employee_link(user):
                skipped += 1
                continue

            if get_user_employee(user):
                skipped += 1
                continue

            # Chercher un salarié avec le même email, non encore lié
            employees = Employee.objects.filter(
                email__iexact=user.email, user__isnull=True,
            )
            if company_id:
                employees = employees.filter(company_id=company_id)

            employee = employees.first()

            if not employee:
                missing += 1
                self.stdout.write(
                    self.style.WARNING(f'  ✗ Aucun salarié pour : {user.email}')
                )
                continue

            if dry_run:
                self.stdout.write(
                    f'  → [DRY RUN] {user.email} ↔ {employee.full_name} (id={employee.pk})'
                )
            else:
                try:
                    link_user_to_employee(user, employee)
                    linked += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'  ✓ {user.email} → {employee.full_name}')
                    )
                except Exception as exc:
                    errors += 1
                    self.stdout.write(
                        self.style.ERROR(f'  ✗ Erreur pour {user.email} : {exc}')
                    )

        self.stdout.write('')
        self.stdout.write(f'Résultat : liés={linked}  sans salarié={missing}  ignorés={skipped}  erreurs={errors}')
