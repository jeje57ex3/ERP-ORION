"""
python manage.py create_siecle_website --company-id=1

Cree automatiquement le site e-commerce SIECLE complet :
- Theme SIECLE Dark Luxury
- Site Website (type=ecommerce)
- Categories : Vetements, Montres, Maquillage
- Pages (accueil, boutique, produit, panier, checkout, succes, echec, CGV, ML, confidentialite)
- Menus header + footer
- Parametres Stripe depuis settings
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify


class Command(BaseCommand):
    help = 'Cree le site e-commerce SIECLE complet.'

    def add_arguments(self, parser):
        parser.add_argument('--company-id', type=int, required=True)
        parser.add_argument('--domain', type=str, default='siecle.orion.local')
        parser.add_argument('--publish', action='store_true')

    def handle(self, *args, **options):
        from apps.core.models import Company
        from apps.websites.models import (
            Website, WebsiteTheme, WebsitePage, WebsiteMenu, WebsiteMenuItem, StoreCategory
        )

        try:
            company = Company.objects.get(pk=options['company_id'])
        except Company.DoesNotExist:
            raise CommandError(f"Entreprise introuvable : id={options['company_id']}")

        self.stdout.write(f'\nCreation du site SIECLE pour : {company.name}')

        # ── Theme ─────────────────────────────────────────────────────────────
        theme, _ = WebsiteTheme.objects.get_or_create(
            company=company, name='SIECLE Dark Luxury',
            defaults={
                'primary_color':    '#000000',
                'secondary_color':  '#FFFFFF',
                'accent_color':     '#D8C7A3',
                'background_color': '#000000',
                'text_color':       '#FFFFFF',
                'button_color':     '#FFFFFF',
                'header_bg_color':  '#000000',
                'footer_bg_color':  '#111111',
                'footer_text_color':'#B8B8B8',
                'font_primary':     'Inter',
                'font_secondary':   'Montserrat',
                'button_style':     'square',
                'mode':             'dark',
            }
        )
        self.stdout.write(f'  Theme : {theme.name}')

        # ── Site ──────────────────────────────────────────────────────────────
        slug = 'siecle'
        site, created = Website.objects.get_or_create(
            company=company, site_type='ecommerce', slug=slug,
            defaults={
                'name':             'SIECLE',
                'theme':            theme,
                'status':           'published' if options['publish'] else 'draft',
                'is_published':     options['publish'],
                'is_active':        True,
                'meta_title':       'SIECLE — Streetwear premium inclusif',
                'meta_description': 'Decouvrez SIECLE, une marque streetwear premium inclusive pour toutes les morphologies.',
                'show_powered_by_orion': False,
            }
        )
        action = 'Cree' if created else 'Existant'
        self.stdout.write(f'  Site : {action} — {site.name}')

        # ── Categories boutique ────────────────────────────────────────────────
        categories_def = [
            ('Vetements',   'vetements',  'Hoodies, t-shirts, cargos, vestes streetwear premium.', 1),
            ('Montres',     'montres',    'Montres urbaines minimalistes au design premium.', 2),
            ('Maquillage',  'maquillage', 'Maquillage streetwear : lipsticks, palettes, gloss.', 3),
        ]
        cats = {}
        for name, cat_slug, desc, order in categories_def:
            cat, cat_created = StoreCategory.objects.get_or_create(
                website=site, slug=cat_slug,
                defaults={'name': name, 'description': desc, 'order': order, 'is_active': True}
            )
            cats[cat_slug] = cat
            self.stdout.write(f'  Categorie : {"C" if cat_created else "E"} — {cat.name}')

        # ── Pages ─────────────────────────────────────────────────────────────
        pages_def = [
            ('Accueil',                'accueil',       'home',    True,  1),
            ('Boutique',               'boutique',      'store',   False, 2),
            ('Produit',                'produit',       'product', False, 3),
            ('Panier',                 'panier',        'cart',    False, 4),
            ('Checkout',               'checkout',      'checkout',False, 5),
            ('Paiement reussi',        'succes',        'custom',  False, 6),
            ('Paiement echoue',        'echec',         'custom',  False, 7),
            ('Mentions legales',       'mentions-legales','legal', False, 8),
            ('CGV',                    'cgv',           'custom',  False, 9),
            ('Confidentialite',        'confidentialite','privacy',False, 10),
        ]
        for title, page_slug, ptype, is_home, order in pages_def:
            WebsitePage.objects.get_or_create(
                website=site, slug=page_slug,
                defaults={
                    'title':        title,
                    'page_type':    ptype,
                    'status':       'published',
                    'is_homepage':  is_home,
                    'show_in_menu': order <= 5,
                    'order':        order,
                }
            )
        self.stdout.write(f'  {len(pages_def)} pages crees/verifies')

        # ── Menu header ────────────────────────────────────────────────────────
        nav_menu, _ = WebsiteMenu.objects.get_or_create(
            website=site, position='header',
            defaults={'name': 'Navigation SIECLE', 'is_active': True}
        )
        if not nav_menu.items.exists():
            nav_items = [
                ('Home',       '/', 1),
                ('Boutique',   '/boutique', 2),
                ('Vetements',  '/boutique?category=vetements', 3),
                ('Montres',    '/boutique?category=montres', 4),
                ('Maquillage', '/boutique?category=maquillage', 5),
            ]
            for label, url, order in nav_items:
                WebsiteMenuItem.objects.create(menu=nav_menu, label=label, url=url, order=order, is_active=True)
            self.stdout.write(f'  Menu nav : {len(nav_items)} elements')

        # ── Menu footer ────────────────────────────────────────────────────────
        footer_menu, _ = WebsiteMenu.objects.get_or_create(
            website=site, position='footer',
            defaults={'name': 'Footer SIECLE', 'is_active': True}
        )
        if not footer_menu.items.exists():
            footer_items = [
                ('Vetements',        '/boutique?category=vetements', 1),
                ('Montres',          '/boutique?category=montres', 2),
                ('Maquillage',       '/boutique?category=maquillage', 3),
                ('Contact',          '/contact', 4),
                ('Livraison',        '/livraison', 5),
                ('Retours',          '/retours', 6),
                ('CGV',              '/cgv', 7),
                ('Confidentialite',  '/confidentialite', 8),
                ('Mentions legales', '/mentions-legales', 9),
            ]
            for label, url, order in footer_items:
                WebsiteMenuItem.objects.create(menu=footer_menu, label=label, url=url, order=order, is_active=True)
            self.stdout.write(f'  Menu footer : {len(footer_items)} elements')

        self.stdout.write(self.style.SUCCESS(
            f'\nSite SIECLE cree avec succes !\n'
            f'  Slug : {site.slug}\n'
            f'  API  : /api/v1/siecle/products/?site={site.slug}\n\n'
            f'Prochaines etapes :\n'
            f'  1. python manage.py seed_siecle_products --company-id={company.pk}\n'
            f'  2. Ajoutez vos cles Stripe dans .env\n'
            f'  3. cd frontend/siecle-store && npm install && npm run dev\n'
        ))
