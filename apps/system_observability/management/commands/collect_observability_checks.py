"""
manage.py collect_observability_checks
Exécute les checks d'observabilité (base de données, cache, stockage,
mémoire, CPU, e-mail, file d'attente, API externe) pour une ou toutes les
entreprises, et enregistre le résultat via record_health_check(). Sans
cette commande, le tableau de bord Observabilité système reste vide —
rien d'autre dans le code n'appelle record_health_check().

Usage :
    python manage.py collect_observability_checks
    python manage.py collect_observability_checks --company-id 3
"""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Exécute les checks d'observabilité système pour les entreprises actives."

    def add_arguments(self, parser):
        parser.add_argument('--company-id', type=int, default=None,
                             help="N'exécuter les checks que pour cette entreprise.")

    def handle(self, *args, **options):
        from apps.core.models import Company
        from apps.system_observability.services import run_all_checks

        company_id = options.get('company_id')
        if company_id:
            try:
                companies = [Company.objects.get(pk=company_id)]
            except Company.DoesNotExist:
                raise CommandError(f'Entreprise ID={company_id} introuvable.')
        else:
            companies = list(Company.objects.filter(is_active=True))

        if not companies:
            self.stdout.write(self.style.WARNING('Aucune entreprise active trouvée.'))
            return

        for company in companies:
            results = run_all_checks(company)
            self.stdout.write(f'\n{company.name} :')
            for check in results:
                icon = {
                    'ok': self.style.SUCCESS('OK'),
                    'warning': self.style.WARNING('WARN'),
                    'critical': self.style.ERROR('CRIT'),
                    'unknown': self.style.WARNING('?'),
                }.get(check.status, check.status)
                self.stdout.write(f'  {check.get_check_type_display():<20s} {icon}  {check.message}')

        self.stdout.write(self.style.SUCCESS(
            f'\n{len(companies)} entreprise(s) vérifiée(s).'
        ))
