"""
Commande de seed LUNEA — données de démonstration complètes.
"""
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal


class Command(BaseCommand):
    help = 'Seed LUNEA — produits, teintes, routines, cartes cadeaux, paliers, échantillons'

    def handle(self, *args, **options):
        from apps.core.models import Company
        from apps.lunea.models import (
            ProductCategory, LuneaProduct, ProductShade, CartGiftThreshold,
            SampleProduct, BeautyRoutine, BeautyRoutineItem, LoyaltyTier,
            GiftCardDesign, BeautyBlogCategory, BeautyBlogPost, MakeupLook,
            NewsletterSubscriber,
        )

        company = Company.objects.filter(is_active=True).first()
        if not company:
            self.stderr.write('Aucune entreprise active trouvée.')
            return

        self.stdout.write(f'Seed LUNEA pour : {company.name}')

        # ── Catégories ────────────────────────────────────────────────────────
        cats = {}
        for name, slug in [
            ('Teint', 'teint'), ('Lèvres', 'levres'),
            ('Yeux', 'yeux'), ('Accessoires', 'accessoires'),
        ]:
            c, _ = ProductCategory.objects.get_or_create(company=company, slug=slug, defaults={'name': name})
            cats[slug] = c
        self.stdout.write('[OK] Catégories créées')

        # ── Produits ──────────────────────────────────────────────────────────
        PRODUCTS = [
            {
                'name': 'Fond de Teint Lumière', 'category': 'teint',
                'price': Decimal('38.00'), 'short_description': 'Un fond de teint lumineux longue tenue pour un éclat naturel.',
                'finish': 'luminous', 'coverage': 'medium', 'is_best_seller': True,
                'loyalty_points': 38, 'has_shades': True, 'hold_hours': 24,
                'skin_types': 'all,dry,combination',
                'shades': [
                    ('Ivoire Lunaire', '#f5e8d5', 'cool', 'very_fair,fair'),
                    ('Beige Rosé', '#e8d0b8', 'cool', 'fair,medium'),
                    ('Sable Doré', '#d4b08a', 'warm', 'medium,tan'),
                    ('Miel Chaud', '#c49868', 'warm', 'tan'),
                    ('Caramel Doux', '#b0814a', 'warm', 'tan,dark'),
                    ('Ébène Lumière', '#8a5c35', 'neutral', 'dark,deep'),
                ],
            },
            {
                'name': 'Correcteur Éclat', 'category': 'teint',
                'price': Decimal('24.00'), 'short_description': 'Correcteur haute couvrance pour effacer les imperfections.',
                'finish': 'natural', 'coverage': 'full', 'is_new': True,
                'loyalty_points': 24, 'has_shades': True,
                'skin_types': 'all',
                'shades': [
                    ('Ivoire Lunaire', '#f5e8d5', 'cool', 'very_fair,fair'),
                    ('Beige Rosé', '#e8d0b8', 'cool', 'fair,medium'),
                    ('Sable Doré', '#d4b08a', 'warm', 'medium,tan'),
                    ('Caramel Doux', '#b0814a', 'warm', 'dark'),
                ],
            },
            {
                'name': 'Poudre Voile Lunaire', 'category': 'teint',
                'price': Decimal('28.00'), 'short_description': 'Poudre fixante voile invisible pour un fini poudré parfait.',
                'finish': 'matte', 'coverage': 'light', 'is_best_seller': True,
                'loyalty_points': 28, 'has_shades': True,
                'skin_types': 'oily,combination',
                'shades': [
                    ('Translucide', '#f8f0e6', 'neutral', 'very_fair,fair,medium'),
                    ('Sable Rosé', '#e8d0b8', 'cool', 'medium,tan'),
                    ('Doré Chaud', '#c49868', 'warm', 'tan,dark'),
                ],
            },
            {
                'name': 'Rouge à Lèvres Éclipse', 'category': 'levres',
                'price': Decimal('22.00'), 'short_description': 'Rouge à lèvres longue tenue aux teintes intenses et lumineuses.',
                'finish': 'satin', 'coverage': 'full', 'is_best_seller': True,
                'loyalty_points': 22, 'has_shades': True, 'hold_hours': 8,
                'skin_types': 'all',
                'shades': [
                    ('Rose Brume', '#e8c8bf', 'cool', 'very_fair,fair'),
                    ('Nude Céleste', '#d4a898', 'neutral', 'fair,medium'),
                    ('Rouge Éclipse', '#c0392b', 'cool', 'all'),
                    ('Mauve Astral', '#9b7fa8', 'cool', 'fair,medium,tan'),
                    ('Corail Soleil', '#e8735a', 'warm', 'medium,tan'),
                    ('Bordeaux Nuit', '#7d1f2e', 'cool', 'tan,dark,deep'),
                ],
            },
            {
                'name': 'Gloss Rosé', 'category': 'levres',
                'price': Decimal('18.00'), 'short_description': 'Gloss repulpant effet volume pour des lèvres brillantes.',
                'finish': 'dewy', 'coverage': 'light', 'is_new': True,
                'loyalty_points': 18, 'has_shades': True,
                'skin_types': 'all',
                'shades': [
                    ('Rose Nacré', '#f0c8c0', 'cool', 'very_fair,fair'),
                    ('Nude Shimmer', '#d4a898', 'neutral', 'fair,medium,tan'),
                    ('Framboise', '#e0607a', 'cool', 'all'),
                ],
            },
            {
                'name': 'Mascara Nuit', 'category': 'yeux',
                'price': Decimal('20.00'), 'short_description': 'Mascara volume extrême pour un regard intense et dramatique.',
                'finish': 'matte', 'coverage': 'buildable', 'is_best_seller': True,
                'loyalty_points': 20, 'hold_hours': 16,
                'skin_types': 'all',
                'shades': [],
            },
            {
                'name': 'Palette Aurore', 'category': 'yeux',
                'price': Decimal('45.00'), 'short_description': 'Palette 12 teintes fards à paupières dorées et rosées.',
                'finish': 'satin', 'coverage': 'buildable', 'is_new': True,
                'loyalty_points': 45,
                'skin_types': 'all',
                'shades': [],
            },
            {
                'name': 'Blush Sable Rose', 'category': 'teint',
                'price': Decimal('26.00'), 'short_description': 'Blush poudre aux reflets rosés pour des joues naturellement colorées.',
                'finish': 'satin', 'coverage': 'light', 'is_best_seller': True,
                'loyalty_points': 26,
                'skin_types': 'all',
                'shades': [
                    ('Sable Rose', '#e8c0b0', 'cool', 'very_fair,fair,medium'),
                    ('Pêche Dorée', '#e8a880', 'warm', 'medium,tan'),
                    ('Brique Terracotta', '#c87858', 'warm', 'tan,dark'),
                ],
            },
            {
                'name': 'Highlighter Champagne', 'category': 'teint',
                'price': Decimal('30.00'), 'short_description': 'Enlumineur poudre pour un éclat doré et lumineux.',
                'finish': 'luminous', 'coverage': 'light', 'is_best_seller': True,
                'loyalty_points': 30, 'has_shades': True,
                'skin_types': 'all',
                'shades': [
                    ('Champagne', '#d7b98c', 'warm', 'very_fair,fair,medium'),
                    ('Rose Gold', '#c9a0a0', 'neutral', 'medium,tan'),
                    ('Or Chaud', '#c8a050', 'warm', 'tan,dark,deep'),
                ],
            },
            {
                'name': 'Pinceau Teint', 'category': 'accessoires',
                'price': Decimal('25.00'), 'short_description': 'Pinceau fond de teint kabuki pour une application parfaite.',
                'loyalty_points': 25,
                'skin_types': 'all',
                'shades': [],
            },
            {
                'name': 'Éponge Douceur', 'category': 'accessoires',
                'price': Decimal('12.00'), 'short_description': 'Éponge beauté latex-free pour un fondu impeccable.',
                'loyalty_points': 12,
                'skin_types': 'all',
                'shades': [],
            },
            {
                'name': 'Trousse LUNEA', 'category': 'accessoires',
                'price': Decimal('35.00'), 'short_description': 'Trousse maquillage LUNEA en coton doux format voyage.',
                'loyalty_points': 35,
                'skin_types': 'all',
                'shades': [],
            },
        ]

        created_products = {}
        for pdata in PRODUCTS:
            shades_data = pdata.pop('shades', [])
            cat = cats.get(pdata.pop('category'))
            p, created = LuneaProduct.objects.get_or_create(
                company=company,
                slug=slugify(pdata['name']),
                defaults={**pdata, 'category': cat, 'is_new': pdata.get('is_new', False)},
            )
            if created:
                for shade_name, hex_color, undertone, skin_tones in shades_data:
                    ProductShade.objects.get_or_create(
                        product=p, name=shade_name,
                        defaults={'hex_color': hex_color, 'undertone': undertone,
                                  'recommended_skin_tones': skin_tones, 'stock': 50}
                    )
            created_products[p.slug] = p

        self.stdout.write(f'[OK] {len(PRODUCTS)} produits créés')

        # ── Paliers cadeaux ───────────────────────────────────────────────────
        thresholds = [
            (Decimal('50'), "Échantillon offert", False, 1),
            (Decimal('80'), "Livraison offerte", True, 2),
            (Decimal('120'), "Mini rouge à lèvres offert", False, 3),
            (Decimal('180'), "Trousse LUNEA offerte", False, 4),
        ]
        for amount, desc, is_shipping, order in thresholds:
            CartGiftThreshold.objects.get_or_create(
                company=company, amount=amount,
                defaults={'description': desc, 'is_free_shipping': is_shipping, 'order': order}
            )
        self.stdout.write('[OK] Paliers cadeaux créés')

        # ── Échantillons ──────────────────────────────────────────────────────
        fdt = created_products.get('fond-de-teint-lumiere')
        rouge = created_products.get('rouge-a-levres-eclipse')
        mascara = created_products.get('mascara-nuit')
        poudre = created_products.get('poudre-voile-lunaire')

        samples_data = [
            (fdt, 'Ivoire Lunaire', 'Fond de teint teinte claire'),
            (fdt, 'Sable Doré', 'Fond de teint teinte medium'),
            (rouge, 'Nude Céleste', 'Rouge à lèvres nude'),
            (mascara, '', 'Mascara volume'),
            (poudre, 'Translucide', 'Poudre compacte'),
        ]
        for product, shade, desc in samples_data:
            if product:
                SampleProduct.objects.get_or_create(
                    company=company, product=product, shade_name=shade,
                    defaults={'description': desc, 'stock': 100, 'min_order_amount': Decimal('50')}
                )
        self.stdout.write('[OK] Échantillons créés')

        # ── Niveaux fidélité ──────────────────────────────────────────────────
        tiers = [
            ('Lunea Classic', 'lunea-classic', 0, '#c9a45c', 1),
            ('Lunea Glow', 'lunea-glow', 250, '#d4a8c4', 2),
            ('Lunea Muse', 'lunea-muse', 750, '#b99aaa', 3),
            ('Lunea Éclipse', 'lunea-eclipse', 1500, '#3a2a1f', 4),
        ]
        for name, slug, min_pts, color, order in tiers:
            LoyaltyTier.objects.get_or_create(
                company=company, slug=slug,
                defaults={'name': name, 'min_points': min_pts, 'color': color, 'order': order}
            )
        self.stdout.write('[OK] Niveaux fidélité créés')

        # ── Routines ──────────────────────────────────────────────────────────
        routines_data = [
            ('Routine Teint Parfait', 'routine-teint-parfait', 'La routine teint essentielle pour un fond de teint parfait.', 15, False),
            ('Routine Éclat Naturel', 'routine-eclat-naturel', 'Révélez votre éclat naturel en quelques gestes.', 10, False),
            ('Routine Lèvres Signature', 'routine-levres-signature', 'Un rouge à lèvres parfait pour sublimer votre sourire.', 5, True),
            ('Routine Regard Intense', 'routine-regard-intense', 'Un regard profond et intense avec mascara et palette.', 20, False),
            ('Routine Nude Quotidien', 'routine-nude-quotidien', 'La routine nude parfaite pour tous les jours.', 8, True),
            ('Routine Soirée Lunaire', 'routine-soiree-lunaire', 'Préparez-vous pour briller lors de vos soirées.', 30, False),
        ]
        for rname, rslug, rdesc, rdur, rquick in routines_data:
            r, _ = BeautyRoutine.objects.get_or_create(
                company=company, slug=rslug,
                defaults={'name': rname, 'description': rdesc, 'duration_minutes': rdur, 'is_quick': rquick}
            )
            if r.items.count() == 0 and fdt:
                BeautyRoutineItem.objects.create(routine=r, product=fdt, step=1, quantity=1)
        self.stdout.write('[OK] Routines créées')

        # ── Designs cartes cadeaux ────────────────────────────────────────────
        for gname, gslug, gcolor in [
            ('Lunea Crème', 'lunea-creme', '#faf6ef'),
            ('Lunea Rose', 'lunea-rose', '#e8c8bf'),
            ('Lunea Nuit', 'lunea-nuit', '#3a2a1f'),
            ('Lunea Champagne', 'lunea-champagne', '#d7b98c'),
        ]:
            GiftCardDesign.objects.get_or_create(
                company=company, slug=gslug,
                defaults={'name': gname, 'primary_color': gcolor}
            )
        self.stdout.write('[OK] Designs cartes cadeaux créés')

        # ── Blog beauté ───────────────────────────────────────────────────────
        blog_cat, _ = BeautyBlogCategory.objects.get_or_create(
            company=company, slug='conseils-beaute',
            defaults={'name': 'Conseils beauté'}
        )
        articles = [
            ('Comment choisir son fond de teint', 'comment-choisir-son-fond-de-teint',
             'Tout savoir pour choisir le fond de teint parfait selon votre carnation et vos besoins.'),
            ('Quel rouge à lèvres selon son sous-ton', 'rouge-a-levres-sous-ton',
             'Le guide complet pour choisir la teinte lèvres parfaite selon votre sous-ton.'),
            ('Routine teint lumineux en 5 minutes', 'routine-teint-lumineux-5-minutes',
             'La routine beauté express pour un teint parfait même les matins pressés.'),
            ('Maquillage naturel quotidien', 'maquillage-naturel-quotidien',
             'Comment créer un maquillage naturel et lumineux pour tous les jours.'),
            ('Comment faire tenir son maquillage', 'faire-tenir-son-maquillage',
             'Nos conseils et astuces pour un maquillage longue tenue toute la journée.'),
        ]
        for title, slug, excerpt in articles:
            BeautyBlogPost.objects.get_or_create(
                company=company, slug=slug,
                defaults={
                    'title': title, 'excerpt': excerpt,
                    'content': excerpt + '\n\nContenu complet à venir.',
                    'category': blog_cat, 'is_published': True,
                    'published_at': timezone.now(),
                }
            )
        self.stdout.write('[OK] Articles blog créés')

        self.stdout.write(self.style.SUCCESS('\nSeed LUNEA termine avec succes!'))
        self.stdout.write(f'   Entreprise : {company.name}')
        self.stdout.write(f'   Produits : {LuneaProduct.objects.filter(company=company).count()}')
        self.stdout.write(f'   Routines : {BeautyRoutine.objects.filter(company=company).count()}')
