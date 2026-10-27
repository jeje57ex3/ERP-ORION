"""
Management command: seed_siecle_builder

Pré-remplit le builder ERP avec les 8 sections éditoriales de la page d'accueil SIÈCLE.
Les images sont laissées vides — l'utilisateur les uploade via le builder.

Usage:
    python manage.py seed_siecle_builder
    python manage.py seed_siecle_builder --company-id 1
    python manage.py seed_siecle_builder --reset       # supprime les sections existantes avant
"""
from django.core.management.base import BaseCommand, CommandError

from apps.site_builder.models import BuilderPage, BuilderSection
from apps.websites.models import Website


# ── Contenu éditorial SIÈCLE ──────────────────────────────────────────────────
# Les images sont vides : l'utilisateur les uploade via le builder ERP.
# L'ordre est (module_type, settings_dict).

SIECLE_SECTIONS = [
    ('hero', {
        'title': "L'objet qui\ntraverse le temps",
        'subtitle': (
            "Chaque pièce SIÈCLE naît d'une matière, d'une structure, d'une forme. "
            "Rien n'est ornemental. Tout est essentiel."
        ),
        'cta_label': 'Découvrir les objets',
        'cta_url': '/siecle/objects',
        'image': '/siecle/object-01.png',
        'overlay_opacity': 30,
        'bg_color': '#080808',
        'text_color': '#F5F0EB',
    }),
    ('text_image', {
        'title': "La pierre. La résine. Le métal brut.",
        'body': (
            "Avant la forme, la matière choisit le créateur. "
            "Chaque collection SIÈCLE commence par une roche, un alliage, "
            "une texture que le temps a déjà travaillée."
        ),
        'image': '/siecle/matiere-01.png',
        'image_side': 'left',
        'cta_label': 'Explorer les matières',
        'cta_url': '/siecle/objects?filter=matiere',
        'bg_color': '#0A0A0A',
        'text_color': '#F5F0EB',
    }),
    ('text_image', {
        'title': "L'architecture de l'ornement.",
        'body': (
            "La structure n'est pas le squelette — elle est l'œuvre. "
            "Chaque pic, chaque jointure, chaque anneau est dessiné "
            "pour porter une tension visuelle précise."
        ),
        'image': '/siecle/structure-02.png',
        'image_side': 'right',
        'cta_label': 'Voir la collection',
        'cta_url': '/siecle/objects?filter=structure',
        'bg_color': '#0D0D0D',
        'text_color': '#F5F0EB',
    }),
    ('text_image', {
        'title': "Du croquis à l'objet final.",
        'body': (
            "La forme est une décision irréversible. "
            "Des centaines d'études précèdent chaque prototype. "
            "Ce qui reste est ce qui ne peut être simplifié davantage."
        ),
        'image': '/siecle/forme-03.png',
        'image_side': 'left',
        'cta_label': 'Les objets',
        'cta_url': '/siecle/objects',
        'bg_color': '#0A0A0A',
        'text_color': '#F5F0EB',
    }),
    ('text_image', {
        'title': "L'œil comme instrument de mesure.",
        'body': (
            "Chaque étude explore un principe formel unique. "
            "La symétrie. Le déséquilibre. La répétition. "
            "SIÈCLE ne dessine pas des accessoires — il résout des problèmes de géométrie."
        ),
        'image': '/siecle/etude-04.png',
        'image_side': 'right',
        'cta_label': 'Voir les études',
        'cta_url': '/siecle/objects?filter=etude',
        'bg_color': '#0D0D0D',
        'text_color': '#F5F0EB',
    }),
    ('full_image', {
        'eyebrow': '05 — Matière Première',
        'title': "Avant l'objet,\nla matière qui résiste.",
        'subtitle': (
            "Le carbone. La résine noire. Le métal forgé. "
            "SIÈCLE ne travaille qu'avec des matières qui ont une histoire propre "
            "avant même d'être touchées."
        ),
        'image': '/siecle/matiere-premiere-05.png',
        'overlay_opacity': 70,
        'min_height': '70vh',
        'cta_label': 'Voir tous les objets',
        'cta_url': '/siecle/objects',
        'bg_color': '#080808',
        'text_color': '#F5F0EB',
    }),
    ('full_image', {
        'eyebrow': 'Archive',
        'title': '002 & 003',
        'subtitle': (
            "La prochaine archive est en préparation. "
            "Accès réservé aux membres SIÈCLE."
        ),
        'image': '/siecle/archive-002-003.png',
        'overlay_opacity': 60,
        'min_height': '100vh',
        'cta_label': "Demander l'accès",
        'cta_url': '/siecle/archive',
        'bg_color': '#080808',
        'text_color': '#F5F0EB',
    }),
    ('cta', {
        'title': "L'objet juste.\nRien de plus.",
        'subtitle': '',
        'cta_label': 'Tous les objets',
        'cta_url': '/siecle/objects',
        'bg_color': '#080808',
        'text_color': '#F5F0EB',
    }),
]


class Command(BaseCommand):
    help = "Pré-remplit le builder SIÈCLE avec les 8 sections éditoriales (images à uploader ensuite)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--company-id', type=int, default=None,
            help='ID de l\'entreprise (défaut : première entreprise avec un site SIÈCLE actif).',
        )
        parser.add_argument(
            '--reset', action='store_true',
            help='Supprime les sections existantes avant de re-créer. Sans --reset, les sections existantes sont conservées.',
        )

    def handle(self, *args, **options):
        company_id = options['company_id']
        reset      = options['reset']

        # ── Trouver le Website SIÈCLE ─────────────────────────────────────────
        qs = Website.objects.filter(slug='siecle', is_active=True)
        if company_id:
            qs = qs.filter(company_id=company_id)

        website = qs.select_related('company').first()
        if not website:
            raise CommandError(
                "Aucun site SIÈCLE actif trouvé. "
                "Créez-le dans l'ERP (Sites web > Mes sites, slug='siecle', actif=oui) "
                "puis relancez cette commande."
            )

        company = website.company
        self.stdout.write(f"Entreprise : {company} | Site : {website.name} (id={website.pk})")

        # ── Trouver ou créer la BuilderPage d'accueil ─────────────────────────
        page, created = BuilderPage.objects.get_or_create(
            company=company,
            website=website,
            is_homepage=True,
            defaults={
                'title': 'Accueil SIÈCLE',
                'slug': 'home',
                'brand_key': 'siecle',
                'status': 'draft',
                'meta_title': 'SIÈCLE — Objets Intemporels',
                'meta_description': (
                    "SIÈCLE. Chaque objet est pensé pour traverser le temps. "
                    "Lunettes, ornements, matières brutes."
                ),
            },
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"  Page créée : {page.title} (id={page.pk})"))
        else:
            self.stdout.write(f"  Page existante : {page.title} (id={page.pk}, status={page.status})")

        # ── Reset facultatif ──────────────────────────────────────────────────
        existing = page.sections.count()
        if existing > 0:
            if reset:
                page.sections.all().delete()
                self.stdout.write(self.style.WARNING(f"  {existing} section(s) supprimée(s) (--reset)."))
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"  La page contient déjà {existing} section(s). "
                        "Utilisez --reset pour les supprimer et re-créer. Aucune modification effectuée."
                    )
                )
                return

        # ── Créer les 8 sections ──────────────────────────────────────────────
        created_count = 0
        for position, (module_type, settings) in enumerate(SIECLE_SECTIONS, start=1):
            BuilderSection.objects.create(
                page=page,
                module_type=module_type,
                position=position,
                settings=settings,
                is_visible=True,
            )
            created_count += 1
            self.stdout.write(f"  [{position}] {module_type} — {settings.get('title','')[:50]}")

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f"[OK] {created_count} sections creees pour la page d'accueil SIECLE.\n"
            "\nProchaines etapes :\n"
            "  1. Ouvrir l'editeur SIECLE dans l'ERP\n"
            "  2. Cliquer chaque section et uploader l'image correspondante\n"
            "  3. Cliquer Publier -> le site Next.js affichera le contenu ERP\n"
        ))
