"""
python manage.py seed_siecle_drops --company-id=1

Seed les drops SIÈCLE.
"""
import datetime
from django.core.management.base import BaseCommand, CommandError

DROPS_DATA = [
    {
        'name':        'Capsule Automne 2025',
        'slug':        'drop-capsule-automne-2025',
        'description': 'Collection capsule automne, 50 pièces numérotées.',
        'drop_date':   datetime.date(2025, 11, 15),
        'is_private':  False,
        'is_active':   True,
        'min_tier':    'BRONZE',
    },
    {
        'name':        'Drop Privé Nuit',
        'slug':        'drop-prive-nuit-2025',
        'description': 'Accès exclusif membres GOLD et PLATINUM.',
        'drop_date':   datetime.date(2025, 12, 1),
        'is_private':  True,
        'is_active':   True,
        'min_tier':    'GOLD',
    },
    {
        'name':        'Capsule Hiver 2026',
        'slug':        'drop-capsule-hiver-2026',
        'description': 'Édition limitée hiver 2026, pièces numérotées.',
        'drop_date':   datetime.date(2026, 2, 1),
        'is_private':  False,
        'is_active':   True,
        'min_tier':    'SILVER',
    },
]


class Command(BaseCommand):
    help = 'Seed les drops SIÈCLE'

    def add_arguments(self, parser):
        parser.add_argument('--company-id', type=int, default=1)

    def handle(self, *args, **options):
        from apps.core.models import Company
        try:
            company = Company.objects.get(pk=options['company_id'])
        except Company.DoesNotExist:
            raise CommandError(f"Company id={options['company_id']} introuvable")

        created = 0
        try:
            from apps.websites.models import ProductDrop
            for data in DROPS_DATA:
                obj, c = ProductDrop.objects.get_or_create(
                    company=company, slug=data['slug'],
                    defaults={**data, 'company': company}
                )
                if c:
                    created += 1
            self.stdout.write(self.style.SUCCESS(f'{created} drops créés.'))
        except Exception as e:
            self.stderr.write(self.style.WARNING(f'ProductDrop non disponible: {e}'))
            self.stdout.write(f'Drops définis (en mémoire): {[d["name"] for d in DROPS_DATA]}')

        self.stdout.write(self.style.SUCCESS('Drops SIÈCLE configurés.'))
