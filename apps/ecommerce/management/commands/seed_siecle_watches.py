"""
python manage.py seed_siecle_watches --company-id=1

Seed les montres SIÈCLE avec options de personnalisation.
"""
from decimal import Decimal
from django.core.management.base import BaseCommand, CommandError

WATCHES = [
    {'name': 'Montre Urban Noir',    'slug': 'siecle-montre-urban-noir',    'price': Decimal('289'), 'is_customizable': True,  'sku': 'SCL-M001'},
    {'name': 'Montre Blanc Minéral', 'slug': 'siecle-montre-blanc-mineral', 'price': Decimal('259'), 'is_customizable': True,  'sku': 'SCL-M002'},
    {'name': "Montre Brun Élégance", 'slug': 'siecle-montre-brun-elegance', 'price': Decimal('349'), 'is_customizable': True,  'sku': 'SCL-M003'},
    {'name': 'Montre Rose Signature','slug': 'siecle-montre-rose-signature','price': Decimal('319'), 'is_customizable': False, 'sku': 'SCL-M004'},
]

CUSTOMIZATION_OPTIONS = {
    'case': [
        {'code': 'case_black_steel', 'label': 'Acier Noir',  'color': '#1a1a1a', 'price_delta': Decimal('0')},
        {'code': 'case_silver',      'label': 'Argent',       'color': '#C0C0C0', 'price_delta': Decimal('20')},
        {'code': 'case_gold',        'label': 'Doré',         'color': '#D4AF37', 'price_delta': Decimal('35')},
        {'code': 'case_beige',       'label': 'Beige Rosé',   'color': '#D8C7A3', 'price_delta': Decimal('25')},
    ],
    'dial': [
        {'code': 'dial_black',     'label': 'Noir Mat',    'color': '#111111', 'price_delta': Decimal('0')},
        {'code': 'dial_white',     'label': 'Blanc',       'color': '#ffffff', 'price_delta': Decimal('10')},
        {'code': 'dial_grey',      'label': 'Gris Ardoise','color': '#707070', 'price_delta': Decimal('10')},
        {'code': 'dial_champagne', 'label': 'Champagne',   'color': '#E8D5A3', 'price_delta': Decimal('20')},
    ],
    'hands': [
        {'code': 'hands_silver', 'label': 'Argentées', 'color': '#C0C0C0', 'price_delta': Decimal('0')},
        {'code': 'hands_gold',   'label': 'Dorées',    'color': '#D4AF37', 'price_delta': Decimal('10')},
        {'code': 'hands_black',  'label': 'Noires',    'color': '#111111', 'price_delta': Decimal('5')},
        {'code': 'hands_white',  'label': 'Blanches',  'color': '#ffffff', 'price_delta': Decimal('5')},
    ],
    'strap': [
        {'code': 'strap_black_leather',  'label': 'Cuir Noir',    'color': '#111111', 'price_delta': Decimal('0')},
        {'code': 'strap_brown_leather',  'label': 'Cuir Brun',    'color': '#5C3A1E', 'price_delta': Decimal('15')},
        {'code': 'strap_beige',          'label': 'Cuir Beige',   'color': '#D8C7A3', 'price_delta': Decimal('20')},
        {'code': 'strap_steel',          'label': 'Acier Milanais','color': '#808080', 'price_delta': Decimal('35')},
    ],
}


class Command(BaseCommand):
    help = 'Seed les montres SIÈCLE avec options de personnalisation'

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

        cat, _ = StoreCategory.objects.get_or_create(slug='montres', defaults={'name': 'Montres', 'is_active': True, 'order': 2})
        if website:
            cat.website = website
            cat.save(update_fields=['website'])

        created = 0
        for w in WATCHES:
            defaults = {**w, 'category': cat, 'status': 'published', 'stock_quantity': 10, 'short_description': w['name'], 'description': w['name'], 'is_popular': True, 'is_featured': True}
            if website:
                defaults['website'] = website
            obj, c = StoreProduct.objects.get_or_create(slug=w['slug'], defaults=defaults)
            if not c:
                for k, v in defaults.items():
                    setattr(obj, k, v)
                obj.save()
            else:
                created += 1

            # Customization options
            if getattr(obj, 'is_customizable', False):
                try:
                    from apps.websites.models import ProductCustomizationOption
                    for group, opts in CUSTOMIZATION_OPTIONS.items():
                        for i, opt in enumerate(opts):
                            ProductCustomizationOption.objects.get_or_create(
                                product=obj, code=opt['code'],
                                defaults={**opt, 'product': obj, 'group': group, 'sort_order': i, 'is_active': True}
                            )
                except Exception as e:
                    self.stderr.write(self.style.WARNING(f'CustomizationOption non disponible: {e}'))

        self.stdout.write(self.style.SUCCESS(f'{created} montres créées.'))
        self.stdout.write(self.style.SUCCESS('Montres SIÈCLE configurées avec options de personnalisation.'))
