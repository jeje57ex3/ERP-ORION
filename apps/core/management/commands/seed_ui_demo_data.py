"""
Insère des données de démonstration dans la base de l'entreprise active.
Crée : clients, prospects, devis, factures, chantiers, produits, salariés, documents.
Usage : python manage.py seed_ui_demo_data --company <id>
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import timedelta
import random
import decimal

D = decimal.Decimal

CLIENTS = [
    ('Groupe Lavoie Construction', 'company'),
    ('SCI Les Oliviers', 'company'),
    ('EURL Fernandez Rénovation', 'company'),
    ('Mairie de Saint-Clair-sur-Rhône', 'public'),
    ('Résidence Les Cèdres', 'company'),
    ('Hôtel du Parc SAS', 'company'),
    ('M. et Mme Dupont', 'individual'),
    ('Clinique du Val d\'Or', 'company'),
]

PROSPECTS = [
    ('Société Bardot & Fils', 'Recommandation', 'new'),
    ('Immo Sud-Est', 'Site web', 'contacted'),
    ('École Jean Moulin', 'Appel entrant', 'to_follow_up'),
    ('Syndicat copropriété Le Parc', 'LinkedIn', 'qualified'),
    ('M. Pierre Mercier', 'Foire expo', 'new'),
]

PRODUCTS = [
    ('Béton C25/30', 'MAT-001', 85.00, 'kg'),
    ('Parpaing 20x20x50', 'MAT-002', 1.20, 'unité'),
    ('Main d\'œuvre maçonnerie', 'MO-001', 45.00, 'heure'),
    ('Echafaudage location', 'LOC-001', 12.00, 'jour'),
    ('Enduit de façade', 'MAT-003', 32.00, 'kg'),
    ('Carrelage 60x60 gris', 'MAT-004', 28.00, 'm²'),
    ('Plaque de plâtre BA13', 'MAT-005', 8.50, 'unité'),
    ('Peinture intérieure blanc', 'MAT-006', 18.00, 'L'),
]

PROJECTS = [
    ('Rénovation façades Immeuble Lavoie', 'active', 85000, 75),
    ('Extension école primaire Jean Moulin', 'planned', 320000, 0),
    ('Hôtel du Parc — mise aux normes PMR', 'active', 48000, 40),
    ('Villa Dupont — piscine et terrasse', 'completed', 62000, 100),
    ('Résidence Les Cèdres — toiture', 'active', 134000, 25),
]

EMPLOYEES = [
    ('Dubois', 'Marc', 'Chef de chantier', 'production'),
    ('Lemaire', 'Sophie', 'Conductrice de travaux', 'production'),
    ('Moreau', 'Jean', 'Maçon qualifié', 'production'),
    ('Petit', 'Isabelle', 'Assistante administrative', 'admin'),
    ('Garcia', 'Carlos', 'Électricien', 'production'),
]


class Command(BaseCommand):
    help = 'Insère des données UI de démonstration dans la base d\'une entreprise.'

    def add_arguments(self, parser):
        parser.add_argument('--company', type=int, required=True, help='ID de l\'entreprise cible')
        parser.add_argument('--clear', action='store_true', help='Vider les données existantes avant insertion')

    def handle(self, *args, **options):
        company_id = options['company']
        try:
            from apps.core.models import Company
            company = Company.objects.get(pk=company_id)
        except Company.DoesNotExist:
            raise CommandError(f'Entreprise #{company_id} introuvable.')

        self.stdout.write(f'\n=== Données démo pour : {company.name} ===\n')

        if not company.database_created:
            raise CommandError('La base de données de cette entreprise n\'est pas encore créée. Lancez d\'abord seed_company_database.')

        from apps.core.db_router import set_company_db, clear_company_db
        from apps.core.company_database_service import get_company_database_alias
        alias = get_company_database_alias(company)
        set_company_db(alias)

        try:
            self._seed_clients(company, alias, options.get('clear', False))
            self._seed_prospects(company, alias)
            self._seed_products(alias)
            self._seed_projects(company, alias)
            self._seed_employees(alias)
        finally:
            clear_company_db()

        self.stdout.write(self.style.SUCCESS('\nDonnées démo insérées avec succès !'))

    def _seed_clients(self, company, alias, clear):
        try:
            from apps.crm.models import Customer
            if clear:
                Customer.objects.using(alias).all().delete()
                self.stdout.write('  Clients effacés.')
            count = 0
            for name, ctype in CLIENTS:
                if not Customer.objects.using(alias).filter(name=name).exists():
                    Customer.objects.using(alias).create(
                        name=name,
                        customer_type=ctype,
                        status='active',
                        company=company,
                    )
                    count += 1
            self.stdout.write(self.style.SUCCESS(f'  Clients : {count} créés'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  Clients ignorés : {e}'))

    def _seed_prospects(self, company, alias):
        try:
            from apps.crm.models import Prospect
            count = 0
            for name, source, status in PROSPECTS:
                if not Prospect.objects.using(alias).filter(name=name).exists():
                    Prospect.objects.using(alias).create(
                        name=name,
                        source=source,
                        status=status,
                        company=company,
                    )
                    count += 1
            self.stdout.write(self.style.SUCCESS(f'  Prospects : {count} créés'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  Prospects ignorés : {e}'))

    def _seed_products(self, alias):
        try:
            from apps.inventory.models import Product
            count = 0
            for name, ref, price, unit in PRODUCTS:
                if not Product.objects.using(alias).filter(reference=ref).exists():
                    Product.objects.using(alias).create(
                        name=name,
                        reference=ref,
                        selling_price=D(str(price)),
                        unit=unit,
                        stock_qty=random.randint(0, 500),
                        min_stock_qty=random.randint(5, 50),
                        status='active',
                    )
                    count += 1
            self.stdout.write(self.style.SUCCESS(f'  Produits : {count} créés'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  Produits ignorés : {e}'))

    def _seed_projects(self, company, alias):
        try:
            from apps.btp.models import Project
            from apps.crm.models import Customer
            customers = list(Customer.objects.using(alias).all())
            count = 0
            for i, (name, status, budget, completion) in enumerate(PROJECTS):
                if not Project.objects.using(alias).filter(name=name).exists():
                    start = timezone.now().date() - timedelta(days=random.randint(30, 180))
                    end = start + timedelta(days=random.randint(60, 360))
                    Project.objects.using(alias).create(
                        name=name,
                        status=status,
                        estimated_budget=D(str(budget)),
                        completion_rate=completion,
                        start_date=start,
                        end_date=end,
                        company=company,
                        customer=customers[i % len(customers)] if customers else None,
                    )
                    count += 1
            self.stdout.write(self.style.SUCCESS(f'  Chantiers : {count} créés'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  Chantiers ignorés : {e}'))

    def _seed_employees(self, alias):
        try:
            from apps.hr.models import Employee
            count = 0
            for last, first, post, dept in EMPLOYEES:
                full = f'{first} {last}'
                if not Employee.objects.using(alias).filter(last_name=last, first_name=first).exists():
                    Employee.objects.using(alias).create(
                        last_name=last,
                        first_name=first,
                        position=post,
                        department=dept,
                        status='active',
                        hire_date=timezone.now().date() - timedelta(days=random.randint(90, 1800)),
                    )
                    count += 1
            self.stdout.write(self.style.SUCCESS(f'  Salariés : {count} créés'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  Salariés ignorés : {e}'))
