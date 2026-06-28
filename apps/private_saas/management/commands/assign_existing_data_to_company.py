"""
python manage.py assign_existing_data_to_company --company-id=1
Rattache toutes les données sans company à l'entreprise donnée.
"""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Rattache les données existantes sans company à une entreprise'

    def add_arguments(self, parser):
        parser.add_argument('--company-id', type=int, required=True, help='ID de l\'entreprise cible')
        parser.add_argument('--dry-run', action='store_true', help='Simuler sans modifier')

    def handle(self, *args, **options):
        from apps.core.models import Company

        try:
            company = Company.objects.get(pk=options['company_id'])
        except Company.DoesNotExist:
            raise CommandError(f'Entreprise ID {options["company_id"]} introuvable.')

        dry_run = options['dry_run']

        self.stdout.write(f'\n{"[SIMULATION] " if dry_run else ""}Rattachement données → {company.name}\n')

        models_to_assign = [
            ('apps.crm',       'Customer',   'Clients'),
            ('apps.crm',       'Prospect',   'Prospects'),
            ('apps.sales',     'Quote',      'Devis'),
            ('apps.sales',     'Order',      'Commandes'),
            ('apps.sales',     'Invoice',    'Factures'),
            ('apps.purchases', 'Supplier',   'Fournisseurs'),
            ('apps.inventory', 'Product',    'Produits'),
            ('apps.inventory', 'Warehouse',  'Entrepôts'),
            ('apps.btp',       'BTPProject', 'Chantiers'),
            ('apps.hr',        'Employee',   'Salariés'),
            ('apps.documents', 'Document',   'Documents'),
            ('apps.websites',  'Website',    'Sites web'),
        ]

        total_updated = 0
        from django.apps import apps as django_apps

        for app_label, model_name, label in models_to_assign:
            try:
                parts = app_label.split('.')
                short_label = parts[-1]
                Model = django_apps.get_model(short_label, model_name)
                if not hasattr(Model, 'company_id'):
                    self.stdout.write(f'  ~ {label} : pas de champ company, ignoré')
                    continue
                qs = Model.objects.filter(company__isnull=True)
                count = qs.count()
                if count == 0:
                    self.stdout.write(f'  - {label} : rien à rattacher')
                    continue
                if not dry_run:
                    qs.update(company=company)
                self.stdout.write(self.style.SUCCESS(f'  ✓ {label} : {count} enregistrement(s) rattaché(s)'))
                total_updated += count
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'  ! {label} ({model_name}) : {e}'))

        self.stdout.write(f'\n{"[SIMULATION] " if dry_run else ""}Total : {total_updated} enregistrements rattachés à {company.name}\n')
