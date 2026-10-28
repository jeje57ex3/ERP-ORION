from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Vérifie les DNS et SSL de tous les domaines actifs.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--company',
            type=int,
            help='ID entreprise (optionnel — vérifie tous si omis)',
        )

    def handle(self, *args, **options):
        from apps.domain_manager.models import CustomDomain
        from apps.domain_manager.services import verify_custom_domain

        qs = CustomDomain.objects.exclude(status='disabled').select_related('company')
        if options['company']:
            qs = qs.filter(company_id=options['company'])

        count = qs.count()
        if not count:
            self.stdout.write(self.style.WARNING('Aucun domaine à vérifier.'))
            return

        self.stdout.write(f'Vérification de {count} domaine(s)...')
        self.stdout.write('')

        ok, errors = 0, 0
        for domain in qs:
            verify_custom_domain(domain)
            domain.refresh_from_db()
            if domain.status in ['dns_valid', 'active']:
                self.stdout.write(self.style.SUCCESS(f'  ✓ {domain.domain} — {domain.get_status_display()}'))
                ok += 1
            else:
                self.stdout.write(self.style.WARNING(f'  ✗ {domain.domain} — {domain.get_status_display()} : {domain.last_error}'))
                errors += 1

        self.stdout.write('')
        self.stdout.write(f'Résultat : {ok} OK, {errors} en attente/erreur.')
        self.stdout.write(self.style.SUCCESS('Vérification terminée.'))
