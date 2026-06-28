"""
python manage.py create_btp_website --company-id=1

Cree automatiquement un site BTP complet pour une entreprise :
- Site Website (type=btp)
- Theme BTP
- Pages (accueil, services, contact, mentions legales, confidentialite)
- Menus (header + footer)
- Sections par defaut sur la page d'accueil
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify


class Command(BaseCommand):
    help = "Cree un site vitrine BTP complet pour une entreprise."

    def add_arguments(self, parser):
        parser.add_argument("--company-id", type=int, required=True,
                            help="ID de l'entreprise (Company.pk)")
        parser.add_argument("--name", type=str, default="",
                            help="Nom du site (defaut: nom de l'entreprise)")
        parser.add_argument("--phone", type=str, default="",
                            help="Telephone affiché sur le site")
        parser.add_argument("--email", type=str, default="",
                            help="Email de contact public")
        parser.add_argument("--publish", action="store_true",
                            help="Publier le site immediatement")

    def handle(self, *args, **options):
        from apps.core.models import Company
        from apps.websites.models import Website, WebsiteTheme, WebsitePage, WebsiteSection, WebsiteMenu, WebsiteMenuItem

        try:
            company = Company.objects.get(pk=options["company_id"])
        except Company.DoesNotExist:
            raise CommandError(f"Entreprise introuvable : id={options['company_id']}")

        site_name = options["name"] or f"{company.name} — Site BTP"
        self.stdout.write(f"\nCreation du site BTP pour : {company.name}")

        # ── Theme BTP ──────────────────────────────────────────────────────────
        theme, _ = WebsiteTheme.objects.get_or_create(
            company=company,
            name="Theme BTP Orion",
            defaults={
                "primary_color":    "#3A2A1A",
                "secondary_color":  "#C6A15B",
                "accent_color":     "#E8D8B0",
                "background_color": "#F8F3EA",
                "text_color":       "#2B2118",
                "button_color":     "#C6A15B",
                "header_bg_color":  "#FFFFFF",
                "footer_bg_color":  "#3A2A1A",
                "footer_text_color":"#C9B89A",
                "font_primary":     "Inter",
                "font_secondary":   "Poppins",
                "button_style":     "rounded",
            }
        )
        self.stdout.write(f"  Theme : {theme.name}")

        # ── Site ───────────────────────────────────────────────────────────────
        slug = slugify(company.name) or "btp-site"
        site, created = Website.objects.get_or_create(
            company=company,
            site_type="btp",
            defaults={
                "name":           site_name,
                "slug":           slug,
                "theme":          theme,
                "status":         "published" if options["publish"] else "draft",
                "is_published":   options["publish"],
                "is_active":      True,
                "contact_phone":  options["phone"] or getattr(company, "phone", ""),
                "contact_email":  options["email"] or getattr(company, "email", ""),
                "meta_title":     f"{company.name} | Entreprise BTP",
                "meta_description": f"Decouvrez les services BTP de {company.name}. Devis gratuit, suivi chantier en ligne, espace client securise.",
                "show_powered_by_orion": True,
            }
        )
        action = "Cree" if created else "Existant"
        self.stdout.write(f"  Site : {action} — {site.name} (slug={site.slug})")

        # ── Pages ──────────────────────────────────────────────────────────────
        pages_def = [
            {"title": "Accueil",               "slug": "accueil",          "page_type": "home",    "is_homepage": True,  "order": 1},
            {"title": "Nos services",           "slug": "services",         "page_type": "services","is_homepage": False, "order": 2},
            {"title": "Travaux",                "slug": "travaux",          "page_type": "custom",  "is_homepage": False, "order": 3},
            {"title": "Depannage",              "slug": "urgence",          "page_type": "custom",  "is_homepage": False, "order": 4},
            {"title": "Nos realisations",       "slug": "realisations",     "page_type": "portfolio","is_homepage": False,"order": 5},
            {"title": "Avis clients",           "slug": "avis",             "page_type": "reviews", "is_homepage": False, "order": 6},
            {"title": "Blog et conseils",       "slug": "blog",             "page_type": "blog",    "is_homepage": False, "order": 7},
            {"title": "Contact",                "slug": "contact",          "page_type": "contact", "is_homepage": False, "order": 8},
            {"title": "Espace client",          "slug": "espace-client",    "page_type": "custom",  "is_homepage": False, "order": 9},
            {"title": "Mentions legales",       "slug": "mentions-legales", "page_type": "legal",   "is_homepage": False, "order": 10, "show_in_menu": False},
            {"title": "Confidentialite",        "slug": "confidentialite",  "page_type": "privacy", "is_homepage": False, "order": 11, "show_in_menu": False},
        ]

        pages = {}
        for pd in pages_def:
            pg, pg_created = WebsitePage.objects.get_or_create(
                website=site, slug=pd["slug"],
                defaults={
                    "title":       pd["title"],
                    "page_type":   pd["page_type"],
                    "status":      "published",
                    "is_homepage": pd["is_homepage"],
                    "show_in_menu":pd.get("show_in_menu", True),
                    "order":       pd["order"],
                    "is_indexable":True,
                }
            )
            pages[pd["slug"]] = pg
            self.stdout.write(f"  Page : {'C' if pg_created else 'E'} — {pg.title}")

        # Lier la page d'accueil au site
        if not site.home_page:
            site.home_page = pages.get("accueil")
            site.save(update_fields=["home_page"])

        # ── Sections page accueil ──────────────────────────────────────────────
        home_page = pages.get("accueil")
        if home_page and not home_page.sections.exists():
            sections_def = [
                {"section_type": "hero",         "title": "Vos travaux suivis simplement",
                 "subtitle": f"Demandez un devis guide, suivez votre chantier en ligne avec {company.name}.",
                 "button_text": "Demarrer mon devis guide", "button_link": "/devis-guide/",
                 "button_secondary_text": "Espace client",  "button_secondary_link": "/client/connexion/",
                 "order": 1},
                {"section_type": "services",     "title": "Nos services BTP",
                 "subtitle": "Des artisans qualifies pour tous vos travaux.",
                 "order": 2},
                {"section_type": "process",      "title": "Comment ca marche",
                 "subtitle": "Un processus simple du devis au chantier.",
                 "order": 3},
                {"section_type": "portfolio",    "title": "Nos realisations",
                 "subtitle": "Decouvrez nos derniers chantiers.",
                 "order": 4},
                {"section_type": "testimonials", "title": "Ce que disent nos clients",
                 "order": 5},
                {"section_type": "cta",          "title": "Vous avez un projet ?",
                 "subtitle": "Repondez a quelques questions et recevez une estimation gratuite.",
                 "button_text": "Demarrer mon devis guide", "button_link": "/devis-guide/",
                 "order": 6},
            ]
            for sd in sections_def:
                WebsiteSection.objects.create(
                    page=home_page,
                    section_type=sd["section_type"],
                    title=sd["title"],
                    subtitle=sd.get("subtitle", ""),
                    button_text=sd.get("button_text", ""),
                    button_link=sd.get("button_link", ""),
                    button_secondary_text=sd.get("button_secondary_text", ""),
                    button_secondary_link=sd.get("button_secondary_link", ""),
                    order=sd["order"],
                    is_visible=True,
                )
            self.stdout.write(f"  {len(sections_def)} sections creees sur la page d'accueil")

        # ── Menus ──────────────────────────────────────────────────────────────
        nav_menu, _ = WebsiteMenu.objects.get_or_create(
            website=site, position="header",
            defaults={"name": "Navigation principale", "is_active": True}
        )
        footer_menu, _ = WebsiteMenu.objects.get_or_create(
            website=site, position="footer",
            defaults={"name": "Pied de page", "is_active": True}
        )

        nav_items = [
            ("Accueil",       "/sites/{slug}/btp/",              1),
            ("Services",      "/sites/{slug}/btp/services/",     2),
            ("Travaux",       "/sites/{slug}/btp/travaux/",      3),
            ("Depannage",     "/sites/{slug}/btp/urgence/",      4),
            ("Realisations",  "/sites/{slug}/btp/realisations/", 5),
            ("Avis",          "/sites/{slug}/btp/avis/",         6),
            ("Blog",          "/sites/{slug}/btp/blog/",         7),
            ("Contact",       "/sites/{slug}/btp/contact/",      8),
            ("Espace client", "/client/connexion/",              9),
        ]
        if not nav_menu.items.exists():
            for label, url_tpl, order in nav_items:
                url = url_tpl.format(slug=site.slug)
                WebsiteMenuItem.objects.create(
                    menu=nav_menu, label=label, url=url, order=order, is_active=True
                )
            self.stdout.write(f"  Menu nav : {len(nav_items)} elements crees")

        footer_items = [
            ("Nos services",    "/sites/{slug}/btp/services/",  1),
            ("Realisations",    "/sites/{slug}/btp/realisations/", 2),
            ("Depannage",       "/sites/{slug}/btp/urgence/",   3),
            ("Blog",            "/sites/{slug}/btp/blog/",      4),
            ("Espace client",   "/client/connexion/",           5),
            ("Mentions legales","/sites/{slug}/page/mentions-legales/", 6),
            ("Confidentialite", "/sites/{slug}/page/confidentialite/",  7),
        ]
        if not footer_menu.items.exists():
            for label, url_tpl, order in footer_items:
                url = url_tpl.format(slug=site.slug)
                WebsiteMenuItem.objects.create(
                    menu=footer_menu, label=label, url=url, order=order, is_active=True
                )
            self.stdout.write(f"  Menu footer : {len(footer_items)} elements crees")

        # ── Recap ──────────────────────────────────────────────────────────────
        self.stdout.write(self.style.SUCCESS(
            f"\nSite BTP cree avec succes !\n"
            f"  Nom     : {site.name}\n"
            f"  Slug    : {site.slug}\n"
            f"  Statut  : {site.status}\n"
            f"  URL BTP : /sites/{site.slug}/btp/\n\n"
            f"Prochaines etapes :\n"
            f"  1. Ajoutez vos services dans Sites web > {site.name} > Services\n"
            f"  2. Ajoutez des realisations dans Sites web > Realisations BTP\n"
            f"  3. Collectez des avis dans Sites web > Avis clients BTP\n"
            f"  4. Publiez : python manage.py create_btp_website --company-id={company.pk} --publish\n"
        ))
