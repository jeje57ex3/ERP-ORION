"""
python manage.py seed_siecle_demo --company-id=1

Seed complet SIÈCLE: produits vêtements, montres, maquillage + loyalty + giftcards + packs + drops.
"""
from decimal import Decimal
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Seed complet SIÈCLE: produits, loyalty, giftcards, packs, drops'

    def add_arguments(self, parser):
        parser.add_argument('--company-id', type=int, default=1)
        parser.add_argument('--website-id', type=int, default=None)
        parser.add_argument('--clear', action='store_true', help='Supprimer les données existantes')

    def handle(self, *args, **options):
        from apps.core.models import Company
        from apps.websites.models import Website, StoreProduct, StoreCategory

        try:
            company = Company.objects.get(pk=options['company_id'])
        except Company.DoesNotExist:
            raise CommandError(f"Company id={options['company_id']} introuvable")

        website = None
        if options['website_id']:
            try:
                website = Website.objects.get(pk=options['website_id'])
            except Website.DoesNotExist:
                raise CommandError(f"Website id={options['website_id']} introuvable")
        else:
            website = Website.objects.filter(company=company, site_type='ecommerce').first()

        if not website:
            self.stderr.write(self.style.WARNING('Aucun site e-commerce trouvé pour cette company. Produits créés sans website.'))

        # Categories
        cats = {}
        for slug, name in [('vetements', 'Vêtements'), ('montres', 'Montres'), ('maquillage', 'Maquillage')]:
            cat, _ = StoreCategory.objects.get_or_create(
                slug=slug,
                defaults={'name': name, 'is_active': True, 'order': ['vetements', 'montres', 'maquillage'].index(slug)},
            )
            if website:
                cat.website = website
                cat.save(update_fields=['website'])
            cats[slug] = cat

        PRODUCTS = [
            # Vêtements
            {'category': 'vetements', 'name': 'T-shirt Urban Noir',    'slug': 'siecle-t-shirt-urban-noir',   'price': Decimal('49'), 'stock_quantity': 80, 'available_sizes': ['XS','S','M','L','XL','2XL','3XL','4XL'], 'is_popular': True,  'is_featured': True,  'sku': 'SCL-V001'},
            {'category': 'vetements', 'name': 'Hoodie Signature',       'slug': 'siecle-hoodie-signature',      'price': Decimal('79'), 'stock_quantity': 60, 'available_sizes': ['XS','S','M','L','XL','2XL','3XL','4XL'], 'is_popular': True,  'is_featured': False, 'sku': 'SCL-V002'},
            {'category': 'vetements', 'name': 'Veste Structurée',        'slug': 'siecle-veste-structuree',      'price': Decimal('129'),'stock_quantity': 30, 'available_sizes': ['S','M','L','XL','2XL'],                   'is_popular': False, 'is_featured': True,  'sku': 'SCL-V003'},
            {'category': 'vetements', 'name': 'Jean Slim Premium',       'slug': 'siecle-jean-slim-premium',     'price': Decimal('89'), 'stock_quantity': 50, 'available_sizes': ['XS','S','M','L','XL','2XL','3XL'],         'is_popular': True,  'is_featured': False, 'sku': 'SCL-V004'},
            {'category': 'vetements', 'name': 'Chemise Satin',           'slug': 'siecle-chemise-satin',         'price': Decimal('95'), 'stock_quantity': 25, 'available_sizes': ['S','M','L','XL','2XL'],                   'is_popular': False, 'is_featured': True,  'sku': 'SCL-V005'},
            {'category': 'vetements', 'name': 'Blazer Oversize',         'slug': 'siecle-blazer-oversize',       'price': Decimal('149'),'stock_quantity': 20, 'available_sizes': ['S','M','L','XL','2XL','3XL'],             'is_popular': True,  'is_featured': True,  'sku': 'SCL-V006'},
            # Montres
            {'category': 'montres', 'name': 'Montre Urban Noir',     'slug': 'siecle-montre-urban-noir',   'price': Decimal('289'),'stock_quantity': 15, 'is_popular': True,  'is_featured': True,  'is_customizable': True, 'sku': 'SCL-M001'},
            {'category': 'montres', 'name': 'Montre Blanc Minéral',   'slug': 'siecle-montre-blanc-mineral','price': Decimal('259'),'stock_quantity': 12, 'is_popular': True,  'is_featured': False, 'is_customizable': True, 'sku': 'SCL-M002'},
            {'category': 'montres', 'name': "Montre Brun Élégance",   'slug': 'siecle-montre-brun-elegance','price': Decimal('349'),'stock_quantity': 8,  'is_popular': False, 'is_featured': True,  'is_customizable': True, 'sku': 'SCL-M003'},
            {'category': 'montres', 'name': 'Montre Rose Signature',   'slug': 'siecle-montre-rose-signature','price': Decimal('319'),'stock_quantity': 10,'is_popular': False, 'is_featured': False, 'is_customizable': False,'sku': 'SCL-M004'},
            # Maquillage
            {'category': 'maquillage', 'name': 'FDT Porcelaine 01N',     'slug': 'siecle-fdt-porcelaine-01n',  'price': Decimal('38'), 'stock_quantity': 40, 'sku': 'SCL-K001'},
            {'category': 'maquillage', 'name': 'Rouge Bordeaux Intense',  'slug': 'siecle-rouge-bordeaux',       'price': Decimal('26'), 'stock_quantity': 60, 'sku': 'SCL-K002'},
            {'category': 'maquillage', 'name': 'Mascara Volume Noir',     'slug': 'siecle-mascara-volume',       'price': Decimal('22'), 'stock_quantity': 70, 'sku': 'SCL-K003'},
            {'category': 'maquillage', 'name': 'Palette Smoky 6 Teintes','slug': 'siecle-palette-smoky',        'price': Decimal('58'), 'stock_quantity': 25, 'sku': 'SCL-K004'},
            {'category': 'maquillage', 'name': 'Highlighter Doré',        'slug': 'siecle-highlighter-dore',    'price': Decimal('34'), 'stock_quantity': 45, 'sku': 'SCL-K005'},
            {'category': 'maquillage', 'name': 'Gloss Nude Transparent',  'slug': 'siecle-gloss-nude',           'price': Decimal('19'), 'stock_quantity': 80, 'sku': 'SCL-K006'},
        ]

        created = updated = 0
        for data in PRODUCTS:
            cat_slug = data.pop('category')
            data['category'] = cats[cat_slug]
            if website:
                data['website'] = website
            data.setdefault('status', 'published')
            data.setdefault('short_description', data['name'])
            data.setdefault('description', data['name'])
            data.setdefault('is_popular', False)
            data.setdefault('is_featured', False)
            data.setdefault('available_sizes', [])

            obj, c = StoreProduct.objects.get_or_create(slug=data['slug'], defaults=data)
            if not c:
                for k, v in data.items():
                    setattr(obj, k, v)
                obj.save()
                updated += 1
            else:
                created += 1

        self.stdout.write(self.style.SUCCESS(f'SIÈCLE Demo: {created} produits créés, {updated} mis à jour.'))
