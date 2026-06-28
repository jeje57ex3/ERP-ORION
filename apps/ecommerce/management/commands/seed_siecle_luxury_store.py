"""
python manage.py seed_siecle_luxury_store --company-id=1

Seed complet du magasin SIÈCLE : produits, programme fidélité,
codes d'affiliation, cartes cadeaux, tokens de démo.
"""
import secrets
from decimal import Decimal
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User


DEMO_PRODUCTS = [
    # Vêtements
    {
        'category': 'vetements', 'name': 'Hoodie Oversize SIÈCLE',
        'slug': 'hoodie-oversize-siecle', 'sku': 'SCL-HOOD-001',
        'short_description': 'Hoodie premium oversize inclusif.',
        'description': 'Coton lourd 380g/m². Coupe oversize. Disponible du XS au 5XL.',
        'price': Decimal('89.00'), 'stock_quantity': 50,
        'available_sizes': ['XS', 'S', 'M', 'L', 'XL', 'XXL', '3XL', '4XL', '5XL'],
        'is_popular': True, 'is_featured': True,
    },
    {
        'category': 'vetements', 'name': 'T-shirt Heavy Cotton SIÈCLE',
        'slug': 't-shirt-heavy-cotton-siecle', 'sku': 'SCL-TSH-001',
        'short_description': 'T-shirt 250g/m² coton lourd.',
        'description': 'Coupe boxy relaxée. Coton organique 250g/m². Du XS au 5XL.',
        'price': Decimal('49.00'), 'stock_quantity': 80,
        'available_sizes': ['XS', 'S', 'M', 'L', 'XL', 'XXL', '3XL', '4XL', '5XL'],
        'is_popular': True, 'is_featured': False,
    },
    {
        'category': 'vetements', 'name': 'Cargo Street SIÈCLE',
        'slug': 'cargo-street-siecle', 'sku': 'SCL-CRG-001',
        'short_description': 'Pantalon cargo streetwear premium.',
        'description': 'Multi-poches, coupe droite relaxée. Disponible de XS à 5XL.',
        'price': Decimal('119.00'), 'stock_quantity': 40,
        'available_sizes': ['XS', 'S', 'M', 'L', 'XL', 'XXL', '3XL', '4XL'],
        'is_popular': False, 'is_featured': True,
    },
    {
        'category': 'vetements', 'name': 'Veste Coach Premium SIÈCLE',
        'slug': 'veste-coach-premium-siecle', 'sku': 'SCL-VES-001',
        'short_description': 'Veste coach légère et minimaliste.',
        'description': 'Veste légère à fermeture éclair. Coupe ajustée. Nylon premium.',
        'price': Decimal('149.00'), 'stock_quantity': 30,
        'available_sizes': ['XS', 'S', 'M', 'L', 'XL', 'XXL'],
        'is_popular': False, 'is_featured': False,
    },
    # Montres
    {
        'category': 'montres', 'name': 'Montre Noir Mat SIÈCLE',
        'slug': 'montre-noir-mat-siecle', 'sku': 'SCL-WCH-001',
        'short_description': 'Montre premium cadran noir mat.',
        'description': 'Boîtier acier IP noir. Verre minéral. Résistance eau 3 ATM.',
        'price': Decimal('189.00'), 'stock_quantity': 25,
        'available_sizes': [], 'is_popular': True, 'is_featured': True,
        'compare_at_price': Decimal('249.00'),
    },
    {
        'category': 'montres', 'name': 'Montre Argent Urbain SIÈCLE',
        'slug': 'montre-argent-urbain-siecle', 'sku': 'SCL-WCH-002',
        'short_description': 'Montre brossée argent, édition urbaine.',
        'description': 'Boîtier acier brossé argent. Cadran blanc. Bracelet cuir.',
        'price': Decimal('229.00'), 'stock_quantity': 20,
        'available_sizes': [], 'is_popular': True, 'is_featured': False,
    },
    {
        'category': 'montres', 'name': 'Montre Beige Edition SIÈCLE',
        'slug': 'montre-beige-edition-siecle', 'sku': 'SCL-WCH-003',
        'short_description': 'Édition limitée beige luxe.',
        'description': 'Cadran beige crème. Bracelet cuir beige. Édition limitée.',
        'price': Decimal('349.00'), 'stock_quantity': 8,
        'available_sizes': [], 'is_popular': True, 'is_featured': True,
        'compare_at_price': Decimal('399.00'),
    },
    # Maquillage
    {
        'category': 'maquillage', 'name': 'Lip Matte Noir',
        'slug': 'lip-matte-noir', 'sku': 'SCL-MKP-001',
        'short_description': 'Rouge à lèvres mat noir profond.',
        'description': 'Formule longue tenue 16h. Noir profond mat. Vegan & cruelty-free.',
        'price': Decimal('28.00'), 'stock_quantity': 100,
        'available_sizes': [], 'is_popular': True, 'is_featured': False,
    },
    {
        'category': 'maquillage', 'name': 'Palette Urban Nude',
        'slug': 'palette-urban-nude', 'sku': 'SCL-MKP-002',
        'short_description': 'Palette ombres à paupières nude urbaines.',
        'description': '12 teintes nude-gris. Pigmentation ultra-intense. Vegan.',
        'price': Decimal('45.00'), 'stock_quantity': 60,
        'available_sizes': [], 'is_popular': True, 'is_featured': True,
    },
    {
        'category': 'maquillage', 'name': 'Gloss Silver Touch',
        'slug': 'gloss-silver-touch', 'sku': 'SCL-MKP-003',
        'short_description': 'Gloss lèvres argenté irisé.',
        'description': 'Gloss haute brillance, reflet argenté. Hydratant 8h. Vegan.',
        'price': Decimal('22.00'), 'stock_quantity': 120,
        'available_sizes': [], 'is_popular': False, 'is_featured': False,
    },
    {
        'category': 'maquillage', 'name': 'Foundation Nude Satin',
        'slug': 'foundation-nude-satin', 'sku': 'SCL-MKP-004',
        'short_description': 'Fond de teint satin couvrance modulable.',
        'description': '24 teintes inclusives, SPF15, tenue 24h, vegan.',
        'price': Decimal('38.00'), 'stock_quantity': 80,
        'available_sizes': [], 'is_popular': True, 'is_featured': True,
    },
]

DEMO_GIFT_CARDS = [
    {'code': 'SCL-GIFT-50EUR', 'initial_amount': Decimal('50.00'), 'status': 'active'},
    {'code': 'SCL-GIFT-100EUR', 'initial_amount': Decimal('100.00'), 'status': 'active'},
    {'code': 'SCL-GIFT-200EUR', 'initial_amount': Decimal('200.00'), 'status': 'active'},
    {'code': 'SCL-GIFT-USED01', 'initial_amount': Decimal('50.00'), 'remaining_amount': Decimal('0.00'), 'status': 'used'},
]


class Command(BaseCommand):
    help = 'Seed complet du magasin SIÈCLE (produits, fidélité, affiliation, cartes cadeaux).'

    def add_arguments(self, parser):
        parser.add_argument('--company-id', type=int, required=True)
        parser.add_argument('--create-demo-user', action='store_true', help='Créer un utilisateur de démo')

    def handle(self, *args, **options):
        from apps.core.models import Company
        from apps.websites.models import (
            Website, StoreProduct, StoreCategory,
            LoyaltyAccount, AffiliateProgram, AffiliateCode,
            GiftCard, SiecleCustomerToken,
        )

        try:
            company = Company.objects.get(pk=options['company_id'])
        except Company.DoesNotExist:
            raise CommandError(f"Entreprise introuvable : id={options['company_id']}")

        site = Website.objects.filter(company=company, site_type='ecommerce', slug='siecle').first()
        if not site:
            raise CommandError("Site SIECLE introuvable. Lancez d'abord create_siecle_website.")

        self.stdout.write(self.style.MIGRATE_HEADING('\n── Produits ──'))
        self._seed_products(site, StoreCategory, StoreProduct)

        self.stdout.write(self.style.MIGRATE_HEADING('\n── Programme fidélité ──'))
        self._seed_loyalty(company, LoyaltyAccount)

        self.stdout.write(self.style.MIGRATE_HEADING('\n── Programme d\'affiliation ──'))
        self._seed_affiliate(company, AffiliateProgram, AffiliateCode)

        self.stdout.write(self.style.MIGRATE_HEADING('\n── Cartes cadeaux ──'))
        self._seed_gift_cards(GiftCard)

        if options.get('create_demo_user'):
            self.stdout.write(self.style.MIGRATE_HEADING('\n── Utilisateur de démo ──'))
            self._seed_demo_user(company, LoyaltyAccount, AffiliateCode, SiecleCustomerToken)

        self.stdout.write(self.style.SUCCESS('\n✓ Seed SIÈCLE terminé.'))

    def _seed_products(self, site, StoreCategory, StoreProduct):
        categories = {
            'vetements':  {'name': 'Vêtements',  'slug': 'vetements'},
            'montres':    {'name': 'Montres',    'slug': 'montres'},
            'maquillage': {'name': 'Maquillage', 'slug': 'maquillage'},
        }
        cat_objs = {}
        for slug, data in categories.items():
            obj, created = StoreCategory.objects.get_or_create(
                website=site, slug=slug, defaults={'name': data['name']}
            )
            cat_objs[slug] = obj
            status = 'Créée' if created else 'Existante'
            self.stdout.write(f'  Catégorie {status} : {obj.name}')

        created_count = 0
        for pdata in DEMO_PRODUCTS:
            cat_slug = pdata.pop('category')
            compare_at = pdata.pop('compare_at_price', None)
            cat = cat_objs.get(cat_slug)
            obj, created = StoreProduct.objects.get_or_create(
                website=site, slug=pdata['slug'],
                defaults={
                    **pdata, 'category': cat, 'status': 'published',
                    'compare_at_price': compare_at,
                    'meta_title': pdata['name'], 'meta_description': pdata['short_description'],
                }
            )
            if created:
                created_count += 1
                self.stdout.write(f'  Créé : {obj.name}')
            else:
                self.stdout.write(f'  Existe : {obj.name}')
            pdata['category'] = cat_slug

        self.stdout.write(self.style.SUCCESS(f'  → {created_count} produit(s) créé(s).'))

    def _seed_loyalty(self, company, LoyaltyAccount):
        _, created = LoyaltyAccount.objects.get_or_create(
            company=company,
            customer=None,
            customer_email='demo@siecle.fr',
            defaults={'points_balance': 750, 'lifetime_points': 750, 'tier': 'silver'},
        )
        status = 'Créé' if created else 'Existant'
        self.stdout.write(f'  Compte fidélité démo {status} (750 pts, Silver)')

    def _seed_affiliate(self, company, AffiliateProgram, AffiliateCode):
        prog, created = AffiliateProgram.objects.get_or_create(
            company=company,
            defaults={
                'is_active': True,
                'reward_type': 'points',
                'referrer_reward_value': Decimal('100'),
                'referred_reward_value': Decimal('10'),
            }
        )
        status = 'Créé' if created else 'Existant'
        self.stdout.write(f'  Programme d\'affiliation {status}')

        demo_code = 'SCL-DEMODEMO'
        code, created = AffiliateCode.objects.get_or_create(
            company=company,
            code=demo_code,
            defaults={'customer_email': 'demo@siecle.fr'},
        )
        status = 'Créé' if created else 'Existant'
        self.stdout.write(f'  Code affiliation démo {status} : {demo_code}')

    def _seed_gift_cards(self, GiftCard):
        created_count = 0
        for gcdata in DEMO_GIFT_CARDS:
            remaining = gcdata.get('remaining_amount', gcdata['initial_amount'])
            obj, created = GiftCard.objects.get_or_create(
                code=gcdata['code'],
                defaults={
                    'initial_amount': gcdata['initial_amount'],
                    'remaining_amount': remaining,
                    'status': gcdata['status'],
                }
            )
            if created:
                created_count += 1
                self.stdout.write(f'  Créée : {obj.code} ({obj.remaining_amount} €)')
            else:
                self.stdout.write(f'  Existe : {obj.code}')
        self.stdout.write(self.style.SUCCESS(f'  → {created_count} carte(s) cadeau créée(s).'))

    def _seed_demo_user(self, company, LoyaltyAccount, AffiliateCode, SiecleCustomerToken):
        user, created = User.objects.get_or_create(
            username='demo_siecle',
            defaults={
                'email': 'demo@siecle.fr',
                'first_name': 'Demo',
                'last_name': 'SIÈCLE',
            }
        )
        if created:
            user.set_password('demo1234!')
            user.save()
            self.stdout.write(f'  Utilisateur créé : demo@siecle.fr / demo1234!')
        else:
            self.stdout.write(f'  Utilisateur existant : {user.email}')

        LoyaltyAccount.objects.get_or_create(
            company=company, customer=user,
            defaults={'customer_email': user.email, 'points_balance': 750, 'lifetime_points': 750, 'tier': 'silver'}
        )

        AffiliateCode.objects.get_or_create(
            company=company, customer=user,
            defaults={'customer_email': user.email, 'code': 'SCL-DEMODEMO'}
        )

        token = SiecleCustomerToken.generate(user)
        self.stdout.write(f'  Token démo : {token.key}')
