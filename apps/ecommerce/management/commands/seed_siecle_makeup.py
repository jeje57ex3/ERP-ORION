"""
python manage.py seed_siecle_makeup --company-id=1

Seed les produits maquillage SIÈCLE BEAUTY (toutes carnations).
"""
from decimal import Decimal
from django.core.management.base import BaseCommand, CommandError

MAKEUP = [
    # Fonds de teint
    {'name': 'FDT Porcelaine 01N',     'slug': 'siecle-fdt-porcelaine-01n',    'price': Decimal('38'), 'sku': 'SCL-K001'},
    {'name': 'FDT Ivoire 01W',          'slug': 'siecle-fdt-ivoire-01w',        'price': Decimal('38'), 'sku': 'SCL-K002'},
    {'name': 'FDT Beige Rose 02N',      'slug': 'siecle-fdt-beige-rose-02n',    'price': Decimal('38'), 'sku': 'SCL-K003'},
    {'name': 'FDT Beige Doré 02W',     'slug': 'siecle-fdt-beige-dore-02w',    'price': Decimal('38'), 'sku': 'SCL-K004'},
    {'name': 'FDT Dorée 03N',           'slug': 'siecle-fdt-doree-03n',         'price': Decimal('38'), 'sku': 'SCL-K005'},
    {'name': 'FDT Caramel 03W',         'slug': 'siecle-fdt-caramel-03w',       'price': Decimal('38'), 'sku': 'SCL-K006'},
    {'name': 'FDT Caramel Profond 04W', 'slug': 'siecle-fdt-caramel-profond',   'price': Decimal('38'), 'sku': 'SCL-K007'},
    {'name': 'FDT Chocolat 05W',        'slug': 'siecle-fdt-chocolat-05w',      'price': Decimal('38'), 'sku': 'SCL-K008'},
    {'name': "FDT Ébène 06W",           'slug': 'siecle-fdt-ebene-06w',         'price': Decimal('38'), 'sku': 'SCL-K009'},
    # Lèvres
    {'name': 'Rouge Bordeaux Intense',  'slug': 'siecle-rouge-bordeaux',         'price': Decimal('26'), 'sku': 'SCL-K010', 'is_popular': True},
    {'name': 'Rouge à lèvres Nude',     'slug': 'siecle-rouge-nude',             'price': Decimal('24'), 'sku': 'SCL-K011'},
    {'name': 'Gloss Nude Transparent',  'slug': 'siecle-gloss-nude',             'price': Decimal('19'), 'sku': 'SCL-K012'},
    {'name': 'Gloss Beige',             'slug': 'siecle-gloss-beige',            'price': Decimal('19'), 'sku': 'SCL-K013'},
    # Yeux
    {'name': 'Mascara Volume Noir',     'slug': 'siecle-mascara-volume',         'price': Decimal('22'), 'sku': 'SCL-K014', 'is_popular': True},
    {'name': 'Mascara Naturel Brun',    'slug': 'siecle-mascara-naturel',        'price': Decimal('22'), 'sku': 'SCL-K015'},
    {'name': 'Eyeliner Noir Précision', 'slug': 'siecle-eyeliner-noir',          'price': Decimal('18'), 'sku': 'SCL-K016'},
    {'name': 'Palette Smoky 6 Teintes','slug': 'siecle-palette-smoky',          'price': Decimal('58'), 'sku': 'SCL-K017', 'is_popular': True, 'is_featured': True},
    # Teint
    {'name': 'Highlighter Doré',       'slug': 'siecle-highlighter-dore',       'price': Decimal('34'), 'sku': 'SCL-K018'},
    {'name': 'Highlighter Bronze',      'slug': 'siecle-highlighter-bronze',     'price': Decimal('34'), 'sku': 'SCL-K019'},
    {'name': 'Blush Terracotta',        'slug': 'siecle-blush-terracotta',       'price': Decimal('28'), 'sku': 'SCL-K020'},
    {'name': 'Bronzeur Ambre',          'slug': 'siecle-bronzeur-ambre',         'price': Decimal('36'), 'sku': 'SCL-K021'},
    {'name': 'Poudre Banane',           'slug': 'siecle-poudre-banane',          'price': Decimal('32'), 'sku': 'SCL-K022'},
    {'name': 'Primer Illuminateur',     'slug': 'siecle-primer-illuminateur',    'price': Decimal('29'), 'sku': 'SCL-K023'},
    {'name': 'BB Cream Légère SPF',    'slug': 'siecle-bb-cream-spf',           'price': Decimal('33'), 'sku': 'SCL-K024'},
]


class Command(BaseCommand):
    help = 'Seed les produits maquillage SIÈCLE BEAUTY (toutes carnations)'

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

        cat, _ = StoreCategory.objects.get_or_create(slug='maquillage', defaults={'name': 'Maquillage', 'is_active': True, 'order': 3})
        if website:
            cat.website = website
            cat.save(update_fields=['website'])

        created = updated = 0
        for item in MAKEUP:
            defaults = {
                **item,
                'category': cat,
                'status': 'published',
                'stock_quantity': 60,
                'short_description': item['name'],
                'description': item['name'],
                'is_popular': item.get('is_popular', False),
                'is_featured': item.get('is_featured', False),
                'available_sizes': [],
            }
            for k in ('is_popular', 'is_featured'):
                defaults.pop(k, None)
            defaults['is_popular'] = item.get('is_popular', False)
            defaults['is_featured'] = item.get('is_featured', False)
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

        self.stdout.write(self.style.SUCCESS(f'Maquillage SIÈCLE BEAUTY: {created} produits créés, {updated} mis à jour.'))
        self.stdout.write(self.style.SUCCESS('Toutes carnations couvertes (9 teintes de fond de teint).'))
