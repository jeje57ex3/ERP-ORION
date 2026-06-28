"""
python manage.py seed_siecle_packs --company-id=1

Seed les packs premium SIÈCLE.
"""
from decimal import Decimal
from django.core.management.base import BaseCommand, CommandError

PACKS_DATA = [
    {'name': 'Pack Signature',  'slug': 'pack-signature',  'price': Decimal('189'), 'normal_price': Decimal('239'), 'points_bonus': 950,  'badge': 'Bestseller', 'product_slugs': ['siecle-t-shirt-urban-noir']},
    {'name': 'Pack Nuit',       'slug': 'pack-nuit',       'price': Decimal('219'), 'normal_price': Decimal('289'), 'points_bonus': 1100, 'badge': 'Soirée',    'product_slugs': []},
    {'name': 'Pack Minimal',    'slug': 'pack-minimal',    'price': Decimal('129'), 'normal_price': Decimal('159'), 'points_bonus': 650,  'badge': 'Essentiel', 'product_slugs': []},
    {'name': "Pack Élégance",   'slug': 'pack-elegance',   'price': Decimal('259'), 'normal_price': Decimal('349'), 'points_bonus': 1300, 'badge': 'Premium',   'product_slugs': ['siecle-chemise-satin']},
    {'name': 'Full SIÈCLE',     'slug': 'pack-full-siecle','price': Decimal('449'), 'normal_price': Decimal('629'), 'points_bonus': 2250, 'badge': 'Ultimate',  'product_slugs': ['siecle-t-shirt-urban-noir', 'siecle-montre-urban-noir']},
]


class Command(BaseCommand):
    help = 'Seed les packs premium SIÈCLE'

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
            from apps.websites.models import PremiumPack, PremiumPackItem, StoreProduct
            for pack_data in PACKS_DATA:
                slugs = pack_data.pop('product_slugs', [])
                obj, c = PremiumPack.objects.get_or_create(
                    company=company, slug=pack_data['slug'],
                    defaults={**pack_data, 'company': company, 'is_active': True}
                )
                for slug in slugs:
                    try:
                        product = StoreProduct.objects.get(slug=slug)
                        PremiumPackItem.objects.get_or_create(pack=obj, product=product)
                    except StoreProduct.DoesNotExist:
                        pass
                if c:
                    created += 1
            self.stdout.write(self.style.SUCCESS(f'{created} packs créés.'))
        except Exception as e:
            self.stderr.write(self.style.WARNING(f'PremiumPack non disponible: {e}'))
            self.stdout.write(f'Packs définis (en mémoire): {[p["name"] for p in PACKS_DATA]}')

        self.stdout.write(self.style.SUCCESS('Packs SIÈCLE configurés.'))
