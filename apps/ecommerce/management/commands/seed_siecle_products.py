"""
python manage.py seed_siecle_products --company-id=1

Cree les produits de demonstration SIECLE dans la boutique.
"""
from decimal import Decimal
from django.core.management.base import BaseCommand, CommandError


DEMO_PRODUCTS = [
    # Vetements
    {
        'category':          'vetements',
        'name':              'Hoodie Oversize SIECLE',
        'slug':              'hoodie-oversize-siecle',
        'short_description': 'Hoodie premium oversize inclusif.',
        'description':       'Coton lourd 380g/m². Coupe oversize. Disponible du XS au 5XL.',
        'price':             Decimal('89.00'),
        'stock_quantity':    50,
        'available_sizes':   ['XS', 'S', 'M', 'L', 'XL', 'XXL', '3XL', '4XL', '5XL'],
        'is_popular':        True,
        'is_featured':       True,
        'sku':               'SCL-HOOD-001',
        'meta_title':        'Hoodie Oversize SIECLE — Streetwear Premium',
        'meta_description':  'Hoodie oversize coton lourd premium, tailles XS au 5XL.',
    },
    {
        'category':          'vetements',
        'name':              'T-shirt Heavy Cotton SIECLE',
        'slug':              't-shirt-heavy-cotton-siecle',
        'short_description': 'T-shirt 250g/m² coton lourd.',
        'description':       'Coupe boxy relaxee. Coton organique 250g/m². Du XS au 5XL.',
        'price':             Decimal('49.00'),
        'stock_quantity':    80,
        'available_sizes':   ['XS', 'S', 'M', 'L', 'XL', 'XXL', '3XL', '4XL', '5XL'],
        'is_popular':        True,
        'is_featured':       False,
        'sku':               'SCL-TSH-001',
        'meta_title':        'T-shirt Heavy Cotton SIECLE',
        'meta_description':  'T-shirt oversize coton lourd premium inclusif.',
    },
    {
        'category':          'vetements',
        'name':              'Cargo Street SIECLE',
        'slug':              'cargo-street-siecle',
        'short_description': 'Pantalon cargo streetwear premium.',
        'description':       'Multi-poches, coupe droite relaxee. Disponible de XS a 5XL.',
        'price':             Decimal('119.00'),
        'stock_quantity':    40,
        'available_sizes':   ['XS', 'S', 'M', 'L', 'XL', 'XXL', '3XL', '4XL'],
        'is_popular':        False,
        'is_featured':       False,
        'sku':               'SCL-CRG-001',
        'meta_title':        'Cargo Street SIECLE — Streetwear Premium',
        'meta_description':  'Pantalon cargo streetwear premium inclusif.',
    },
    {
        'category':          'vetements',
        'name':              'Veste Noire SIECLE',
        'slug':              'veste-noire-siecle',
        'short_description': 'Veste technique noire premium.',
        'description':       'Veste technique streetwear ultra premium. Coupe oversized. XS-5XL.',
        'price':             Decimal('189.00'),
        'stock_quantity':    25,
        'available_sizes':   ['XS', 'S', 'M', 'L', 'XL', 'XXL', '3XL', '4XL'],
        'is_popular':        True,
        'is_featured':       True,
        'sku':               'SCL-JKT-001',
        'meta_title':        'Veste Noire SIECLE — Streetwear Premium',
        'meta_description':  'Veste noire technique premium streetwear.',
    },
    # Montres
    {
        'category':          'montres',
        'name':              'Montre Minimal Black',
        'slug':              'montre-minimal-black',
        'short_description': 'Montre minimaliste cadran noir.',
        'description':       'Cadran noir mat. Bracelet cuir noir. Mouvement quartz japonais.',
        'price':             Decimal('249.00'),
        'stock_quantity':    15,
        'available_sizes':   [],
        'is_popular':        True,
        'is_featured':       True,
        'sku':               'SCL-WCH-001',
        'meta_title':        'Montre Minimal Black SIECLE',
        'meta_description':  'Montre minimaliste streetwear cadran noir premium.',
    },
    {
        'category':          'montres',
        'name':              'Montre Argent Urbain',
        'slug':              'montre-argent-urbain',
        'short_description': 'Montre argent brossee urbaine.',
        'description':       'Cadran blanc/argent. Bracelet milanais. Edition urbaine.',
        'price':             Decimal('299.00'),
        'stock_quantity':    10,
        'available_sizes':   [],
        'is_popular':        False,
        'is_featured':       False,
        'sku':               'SCL-WCH-002',
        'meta_title':        'Montre Argent Urbain SIECLE',
        'meta_description':  'Montre brossee argent edition urbaine premium.',
    },
    {
        'category':          'montres',
        'name':              'Montre Beige Edition',
        'slug':              'montre-beige-edition',
        'short_description': 'Edition limitee beige luxe.',
        'description':       'Cadran beige creme. Bracelet cuir beige. Edition limitee.',
        'price':             Decimal('349.00'),
        'compare_at_price':  Decimal('399.00'),
        'stock_quantity':    8,
        'available_sizes':   [],
        'is_popular':        True,
        'is_featured':       True,
        'sku':               'SCL-WCH-003',
        'meta_title':        'Montre Beige Edition SIECLE',
        'meta_description':  'Edition limitee montre beige luxe streetwear.',
    },
    # Maquillage
    {
        'category':          'maquillage',
        'name':              'Lip Matte Noir',
        'slug':              'lip-matte-noir',
        'short_description': 'Rouge a levres mat noir profond.',
        'description':       'Formule longue tenue 16h. Noir profond mat. Vegan & cruelty-free.',
        'price':             Decimal('28.00'),
        'stock_quantity':    100,
        'available_sizes':   [],
        'is_popular':        True,
        'is_featured':       False,
        'sku':               'SCL-MKP-001',
        'meta_title':        'Lip Matte Noir SIECLE',
        'meta_description':  'Rouge a levres mat noir vegan longue tenue.',
    },
    {
        'category':          'maquillage',
        'name':              'Palette Urban Nude',
        'slug':              'palette-urban-nude',
        'short_description': 'Palette ombres a paupieres nude urbaines.',
        'description':       '12 teintes nude-gris. Pigmentation ultra-intense. Vegan.',
        'price':             Decimal('45.00'),
        'stock_quantity':    60,
        'available_sizes':   [],
        'is_popular':        True,
        'is_featured':       True,
        'sku':               'SCL-MKP-002',
        'meta_title':        'Palette Urban Nude SIECLE',
        'meta_description':  'Palette maquillage streetwear 12 teintes nude premium.',
    },
    {
        'category':          'maquillage',
        'name':              'Gloss Silver Touch',
        'slug':              'gloss-silver-touch',
        'short_description': 'Gloss levres argente irise.',
        'description':       'Gloss haute brillance, reflet argente. Hydratant 8h. Vegan.',
        'price':             Decimal('22.00'),
        'stock_quantity':    120,
        'available_sizes':   [],
        'is_popular':        False,
        'is_featured':       False,
        'sku':               'SCL-MKP-003',
        'meta_title':        'Gloss Silver Touch SIECLE',
        'meta_description':  'Gloss levres argente streetwear irise hydratant.',
    },
]


class Command(BaseCommand):
    help = 'Cree les produits de demonstration SIECLE.'

    def add_arguments(self, parser):
        parser.add_argument('--company-id', type=int, required=True)

    def handle(self, *args, **options):
        from apps.core.models import Company
        from apps.websites.models import Website, StoreProduct, StoreCategory

        try:
            company = Company.objects.get(pk=options['company_id'])
        except Company.DoesNotExist:
            raise CommandError(f"Entreprise introuvable : id={options['company_id']}")

        site = Website.objects.filter(company=company, site_type='ecommerce', slug='siecle').first()
        if not site:
            raise CommandError("Site SIECLE introuvable. Lancez d'abord create_siecle_website.")

        created_count = 0
        for pdata in DEMO_PRODUCTS:
            cat_slug = pdata.pop('category')
            compare_at = pdata.pop('compare_at_price', None)
            cat = StoreCategory.objects.filter(website=site, slug=cat_slug).first()

            obj, created = StoreProduct.objects.get_or_create(
                website=site, slug=pdata['slug'],
                defaults={
                    **pdata,
                    'category':        cat,
                    'status':          'published',
                    'compare_at_price': compare_at,
                }
            )
            if created:
                created_count += 1
                self.stdout.write(f'  Cree : {obj.name}')
            else:
                self.stdout.write(f'  Existe : {obj.name}')

            pdata['category'] = cat_slug  # restore for idempotency

        self.stdout.write(self.style.SUCCESS(f'\n{created_count} produit(s) SIECLE cree(s).'))
