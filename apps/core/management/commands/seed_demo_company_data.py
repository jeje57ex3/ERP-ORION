"""
Crée une entreprise de démonstration avec sa base dédiée et des données initiales.
Usage : python manage.py seed_demo_company_data [--reset]
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify
import random


DEMO_COMPANY = {
    'name': 'BTP Démo SARL',
    'legal_name': 'BTP Démo SARL',
    'siret': '12345678901234',
    'sector': 'btp',
    'city': 'Lyon',
    'address': '15 rue des Bâtisseurs',
    'postal_code': '69001',
    'email': 'contact@btp-demo.fr',
    'phone': '04 72 00 00 00',
}


class Command(BaseCommand):
    help = 'Crée une entreprise de démonstration avec base dédiée et données initiales.'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', help='Supprimer et recréer si elle existe déjà')

    def handle(self, *args, **options):
        from apps.core.models import Company

        existing = Company.objects.filter(name=DEMO_COMPANY['name']).first()
        if existing and not options['reset']:
            self.stdout.write(self.style.WARNING(
                f'Entreprise démo déjà existante (id={existing.pk}). Utilisez --reset pour recréer.'
            ))
            return

        if existing and options['reset']:
            self.stdout.write(f'Suppression de l\'entreprise démo existante (id={existing.pk})…')
            existing.delete()

        self.stdout.write('\n=== Création de l\'entreprise de démonstration ===\n')

        company = Company.objects.create(
            name=DEMO_COMPANY['name'],
            legal_name=DEMO_COMPANY['legal_name'],
            slug=slugify(DEMO_COMPANY['name']),
            siret=DEMO_COMPANY['siret'],
            sector=DEMO_COMPANY['sector'],
            status='active',
            database_host='127.0.0.1',
            database_user='root',
            database_password='',
            database_port=3306,
        )
        self.stdout.write(self.style.SUCCESS(f'Entreprise créée : {company.name} (id={company.pk})'))

        try:
            from apps.core.company_database_service import (
                generate_company_database_name,
                create_company_database,
                run_company_migrations,
            )
            db_name = generate_company_database_name(company)
            company.database_name = db_name
            company.save(update_fields=['database_name'])
            self.stdout.write(f'Nom base : {db_name}')

            ok, msg = create_company_database(company)
            if ok:
                self.stdout.write(self.style.SUCCESS(f'Base créée : {msg}'))
                ok2, msg2 = run_company_migrations(company)
                if ok2:
                    self.stdout.write(self.style.SUCCESS(f'Migrations : {msg2}'))
                else:
                    self.stdout.write(self.style.WARNING(f'Migrations partielles : {msg2}'))
            else:
                self.stdout.write(self.style.WARNING(f'Base non créée (XAMPP non démarré ?) : {msg}'))
                self.stdout.write('Données métier non insérées (base manquante).')
                return
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Impossible de créer la base : {e}'))
            self.stdout.write('Données métier ignorées.')
            return

        self.stdout.write(self.style.SUCCESS(f'\nEntreprise démo prête ! Base : {company.database_name}\n'))
        self.stdout.write('Lancez maintenant : python manage.py seed_ui_demo_data')
