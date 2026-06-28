from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = "Crée et migre la base de données dédiée d'une entreprise."

    def add_arguments(self, parser):
        parser.add_argument('company_id', type=int, help='ID de l\'entreprise')
        parser.add_argument('--skip-migrations', action='store_true', help='Ne pas lancer les migrations')
        parser.add_argument('--force', action='store_true', help='Recréer même si la base existe déjà')

    def handle(self, *args, **options):
        company_id = options['company_id']
        try:
            from apps.core.models import Company
            company = Company.objects.get(pk=company_id)
        except Company.DoesNotExist:
            raise CommandError(f'Entreprise #{company_id} introuvable.')

        self.stdout.write(f'\nEntreprise : {company.name}')
        self.stdout.write(f'Base cible : {company.database_name or "(non configurée)"}')

        if company.database_created and not options['force']:
            self.stdout.write(self.style.WARNING('Base déjà créée. Utilisez --force pour recréer.'))
            return

        try:
            from apps.core.company_database_service import (
                generate_company_database_name,
                create_company_database,
                run_company_migrations,
            )
        except ImportError as e:
            raise CommandError(f'Impossible d\'importer company_database_service : {e}')

        if not company.database_name:
            name = generate_company_database_name(company)
            company.database_name = name
            company.save(update_fields=['database_name'])
            self.stdout.write(f'Nom généré : {name}')

        self.stdout.write('Création de la base MySQL…')
        ok, msg = create_company_database(company)
        if ok:
            self.stdout.write(self.style.SUCCESS(f'  {msg}'))
        else:
            raise CommandError(f'Échec création : {msg}')

        if not options['skip_migrations']:
            self.stdout.write('Migrations en cours…')
            ok2, msg2 = run_company_migrations(company)
            if ok2:
                self.stdout.write(self.style.SUCCESS(f'  {msg2}'))
            else:
                self.stdout.write(self.style.WARNING(f'  Migrations partielles : {msg2}'))

        self.stdout.write(self.style.SUCCESS(f'\nBase {company.database_name} prête.'))
