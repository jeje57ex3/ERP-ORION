"""
python manage.py seed_siecle_watch_customizer --company-id=1

Creates:
  - A watch product (Montre SIÈCLE Signature, 199 €, personnalisable)
  - ProductCustomizationOption rows for case / dial / hands / strap
  - Links to the first Website belonging to the given company
"""
from django.core.management.base import BaseCommand, CommandError
from decimal import Decimal


CUSTOMIZATION_OPTIONS = {
    'case': [
        {'code': 'case_black_steel', 'label': 'Acier noir',       'color': '#0B0B0B', 'material': 'metal',  'price_delta': '0.00',  'sort_order': 0},
        {'code': 'case_silver',      'label': 'Argent poli',      'color': '#C0C0C0', 'material': 'metal',  'price_delta': '20.00', 'sort_order': 1},
        {'code': 'case_gold',        'label': 'Doré champagne',   'color': '#C9A45C', 'material': 'metal',  'price_delta': '35.00', 'sort_order': 2},
        {'code': 'case_beige',       'label': 'Beige sable',      'color': '#D8C7A3', 'material': 'metal',  'price_delta': '25.00', 'sort_order': 3},
    ],
    'dial': [
        {'code': 'dial_black',      'label': 'Noir profond',    'color': '#000000', 'material': 'matte', 'price_delta': '0.00',  'sort_order': 0},
        {'code': 'dial_white',      'label': 'Blanc cassé',     'color': '#F5F1E8', 'material': 'matte', 'price_delta': '10.00', 'sort_order': 1},
        {'code': 'dial_grey',       'label': 'Gris anthracite', 'color': '#222222', 'material': 'matte', 'price_delta': '10.00', 'sort_order': 2},
        {'code': 'dial_champagne',  'label': 'Champagne',       'color': '#D8C7A3', 'material': 'satin', 'price_delta': '20.00', 'sort_order': 3},
    ],
    'hands': [
        {'code': 'hands_silver', 'label': 'Argent', 'color': '#C0C0C0', 'material': 'metal', 'price_delta': '0.00',  'sort_order': 0},
        {'code': 'hands_gold',   'label': 'Doré',   'color': '#C9A45C', 'material': 'metal', 'price_delta': '10.00', 'sort_order': 1},
        {'code': 'hands_black',  'label': 'Noir',   'color': '#0B0B0B', 'material': 'metal', 'price_delta': '5.00',  'sort_order': 2},
        {'code': 'hands_white',  'label': 'Blanc',  'color': '#FFFFFF', 'material': 'gloss', 'price_delta': '5.00',  'sort_order': 3},
    ],
    'strap': [
        {'code': 'strap_black_leather', 'label': 'Cuir noir',     'color': '#050505', 'material': 'leather', 'price_delta': '0.00',  'sort_order': 0},
        {'code': 'strap_brown_leather', 'label': 'Cuir brun',     'color': '#3A2417', 'material': 'leather', 'price_delta': '15.00', 'sort_order': 1},
        {'code': 'strap_beige',         'label': 'Beige premium', 'color': '#D8C7A3', 'material': 'leather', 'price_delta': '20.00', 'sort_order': 2},
        {'code': 'strap_steel',         'label': 'Maille acier',  'color': '#A8A8A8', 'material': 'metal',   'price_delta': '35.00', 'sort_order': 3},
    ],
}


class Command(BaseCommand):
    help = 'Seed SIÈCLE watch configurator: demo watch + customization options'

    def add_arguments(self, parser):
        parser.add_argument('--company-id', type=int, required=True, help='Company ID to seed for')

    def handle(self, *args, **options):
        from apps.core.models import Company
        from apps.websites.models import (
            Website, StoreCategory, StoreProduct, ProductCustomizationOption,
        )

        company_id = options['company_id']
        try:
            company = Company.objects.get(pk=company_id)
        except Company.DoesNotExist:
            raise CommandError(f'Company #{company_id} introuvable.')

        self.stdout.write(f'\n⚙  Seed SIÈCLE Watch Configurator — Company: {company.name}\n')

        # Get or find a suitable website
        site = Website.objects.filter(company=company).first()
        if not site:
            raise CommandError(f'Aucun site associé à la Company #{company_id}.')

        self.stdout.write(f'   Site : {site.name} (slug={site.slug})')

        # Category
        cat, _ = StoreCategory.objects.get_or_create(
            slug='montres',
            website=site,
            defaults={'name': 'Montres'},
        )
        self.stdout.write(f'   Catégorie : {cat.name}')

        # Product
        product, created = StoreProduct.objects.get_or_create(
            slug='montre-siecle-signature',
            website=site,
            defaults={
                'name':             'Montre SIÈCLE Signature',
                'category':         cat,
                'short_description':'Une montre personnalisable, pensée pour durer.',
                'description': (
                    'La SIÈCLE Signature est notre pièce iconique. '
                    'Choisissez votre boîtier, votre cadran, vos aiguilles et votre bracelet '
                    'pour créer une montre qui vous ressemble.'
                ),
                'price':            Decimal('199.00'),
                'stock_quantity':   50,
                'status':           'published',
                'is_customizable':  True,
                'is_featured':      True,
                'meta_title':       'Montre SIÈCLE Signature — Personnalisation 3D',
                'meta_description': 'Créez votre montre unique avec le configurateur SIÈCLE.',
            },
        )
        action = 'Créé' if created else 'Déjà existant'
        self.stdout.write(f'   Produit : {product.name} ({action})')

        # Ensure it's marked personnalisable
        if not product.is_customizable:
            product.is_customizable = True
            product.save(update_fields=['is_customizable'])

        # Seed customization options
        total_opts = 0
        for group, options_list in CUSTOMIZATION_OPTIONS.items():
            for opt_data in options_list:
                obj, created = ProductCustomizationOption.objects.get_or_create(
                    product=product,
                    group=group,
                    code=opt_data['code'],
                    defaults={
                        'company':     company,
                        'label':       opt_data['label'],
                        'color':       opt_data['color'],
                        'material':    opt_data['material'],
                        'price_delta': Decimal(opt_data['price_delta']),
                        'sort_order':  opt_data['sort_order'],
                        'is_active':   True,
                    },
                )
                if created:
                    total_opts += 1

        self.stdout.write(f'   Options créées : {total_opts} (sur {sum(len(v) for v in CUSTOMIZATION_OPTIONS.values())} total)')
        self.stdout.write(self.style.SUCCESS('\n✓ Seed terminé avec succès.\n'))
        self.stdout.write(f'  → Accédez au configurateur sur /montres/{product.slug}\n')
