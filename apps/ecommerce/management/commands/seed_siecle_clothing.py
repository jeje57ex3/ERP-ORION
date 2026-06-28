"""
python manage.py seed_siecle_clothing --company-id=1

Seed les vêtements SIÈCLE (XS–4XL, toutes morphologies).
"""
from decimal import Decimal
from django.core.management.base import BaseCommand, CommandError

SIZES = ['XS', 'S', 'M', 'L', 'XL', 'XXL', '3XL', '4XL']
FITS  = ['Ajusté', 'Normal', 'Oversize']

CLOTHING = [
    {'name': 'T-shirt Urban Noir',        'slug': 'siecle-t-shirt-urban-noir',   'price': Decimal('49'),  'is_popular': True,  'is_featured': True,  'sku': 'SCL-V001'},
    {'name': 'Hoodie Signature',          'slug': 'siecle-hoodie-signature',      'price': Decimal('79'),  'is_popular': True,  'is_featured': False, 'sku': 'SCL-V002'},
    {'name': 'Veste Structurée',           'slug': 'siecle-veste-structuree',      'price': Decimal('129'), 'is_popular': False, 'is_featured': True,  'sku': 'SCL-V003'},
    {'name': 'Jean Slim Premium',          'slug': 'siecle-jean-slim-premium',     'price': Decimal('89'),  'is_popular': True,  'is_featured': False, 'sku': 'SCL-V004'},
    {'name': 'Chemise Satin',              'slug': 'siecle-chemise-satin',         'price': Decimal('95'),  'is_popular': False, 'is_featured': True,  'sku': 'SCL-V005'},
    {'name': 'Blazer Oversize',            'slug': 'siecle-blazer-oversize',       'price': Decimal('149'), 'is_popular': True,  'is_featured': True,  'sku': 'SCL-V006'},
    {'name': 'Pantalon Slim Noir',         'slug': 'siecle-pantalon-slim-noir',    'price': Decimal('79'),  'is_popular': False, 'is_featured': False, 'sku': 'SCL-V007'},
    {'name': 'Veste Evening',              'slug': 'siecle-veste-evening',         'price': Decimal('169'), 'is_popular': False, 'is_featured': True,  'sku': 'SCL-V008'},
    {'name': 'Tee Premium Blanc',          'slug': 'siecle-tee-premium-blanc',     'price': Decimal('45'),  'is_popular': True,  'is_featured': False, 'sku': 'SCL-V009'},
    {'name': 'Casquette Signature',        'slug': 'siecle-casquette-signature',   'price': Decimal('39'),  'is_popular': True,  'is_featured': False, 'sku': 'SCL-V010', 'available_sizes': ['Taille unique']},
    {'name': 'Chaussettes Logo x3',        'slug': 'siecle-chaussettes-logo',      'price': Decimal('19'),  'is_popular': False, 'is_featured': False, 'sku': 'SCL-V011', 'available_sizes': ['36-40', '41-45', '46+']},
    {'name': 'Ceinture Cuir',              'slug': 'siecle-ceinture-cuir',         'price': Decimal('49'),  'is_popular': False, 'is_featured': False, 'sku': 'SCL-V012', 'available_sizes': ['S/M', 'L/XL', 'XXL+']},
    {'name': 'Pochette Logo',              'slug': 'siecle-pochette-logo',          'price': Decimal('35'),  'is_popular': False, 'is_featured': False, 'sku': 'SCL-V013', 'available_sizes': []},
    {'name': 'Sac Tote SIÈCLE',           'slug': 'siecle-sac-tote',              'price': Decimal('55'),  'is_popular': False, 'is_featured': False, 'sku': 'SCL-V014', 'available_sizes': []},
]


class Command(BaseCommand):
    help = 'Seed les vêtements SIÈCLE (XS–4XL inclusif)'

    def add_arguments(self, parser):
        parser.add_argument('--company-id', type=int, default=1)
        parser.add_argument('--website-id', type=int, default=None)

    def handle(self, *args, **options):
        from apps.core.models import Company
        from apps.websites.models import StoreProduct, StoreCategory

        try:
            company = Company.objects.get(pk=options['company_id'])
        except Company.DoesNotExist:
            raise CommandError(f"Company id={options['company_id']} introuvable")

        website = None
        if options['website_id']:
            from apps.websites.models import Website
            website = Website.objects.filter(pk=options['website_id']).first()

        cat, _ = StoreCategory.objects.get_or_create(slug='vetements', defaults={'name': 'Vêtements', 'is_active': True, 'order': 1})
        if website:
            cat.website = website
            cat.save(update_fields=['website'])

        created = updated = 0
        for item in CLOTHING:
            sizes = item.pop('available_sizes', SIZES)
            defaults = {
                **item,
                'category': cat,
                'status': 'published',
                'stock_quantity': 50,
                'short_description': item['name'],
                'description': item['name'],
                'available_sizes': sizes,
            }
            if website:
                defaults['website'] = website

            obj, c = StoreProduct.objects.get_or_create(slug=item['slug'], defaults=defaults)
            if not c:
                for k, v in defaults.items():
                    setattr(obj, k, v)
                obj.save()
                updated += 1
            else:
                created += 1

        self.stdout.write(self.style.SUCCESS(f'Vêtements SIÈCLE: {created} créés, {updated} mis à jour.'))
        self.stdout.write(self.style.SUCCESS(f'Tailles disponibles: {SIZES}'))
