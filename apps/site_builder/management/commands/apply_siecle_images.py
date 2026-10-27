"""
Management command: apply_siecle_images

Met à jour les URLs d'images des sections SIÈCLE existantes en base.
À utiliser si seed_siecle_builder a déjà été lancé sans les images.

Usage:
    python manage.py apply_siecle_images
    python manage.py apply_siecle_images --company-id 1 --publish
"""
from django.core.management.base import BaseCommand, CommandError

from apps.site_builder.models import BuilderPage, BuilderSection
from apps.site_builder.services import publish_builder_page
from apps.websites.models import Website

# Images dans l'ordre de position (correspond au seed_siecle_builder)
IMAGES_BY_POSITION = {
    1: '/siecle/object-01.png',          # hero
    2: '/siecle/matiere-01.png',         # text_image
    3: '/siecle/structure-02.png',       # text_image
    4: '/siecle/forme-03.png',           # text_image
    5: '/siecle/etude-04.png',           # text_image
    6: '/siecle/matiere-premiere-05.png',# full_image
    7: '/siecle/archive-002-003.png',    # full_image
    # position 8 = cta, pas d'image
}


class Command(BaseCommand):
    help = "Injecte les URLs d'images dans les sections SIÈCLE existantes."

    def add_arguments(self, parser):
        parser.add_argument('--company-id', type=int, default=None)
        parser.add_argument('--publish', action='store_true',
                            help='Publie la page après avoir mis à jour les images.')

    def handle(self, *args, **options):
        company_id = options['company_id']
        do_publish  = options['publish']

        qs = Website.objects.filter(slug='siecle', is_active=True)
        if company_id:
            qs = qs.filter(company_id=company_id)
        website = qs.select_related('company').first()
        if not website:
            raise CommandError("Aucun site SIÈCLE actif trouvé.")

        page = BuilderPage.objects.filter(
            company=website.company, website=website, is_homepage=True,
        ).first()
        if not page:
            raise CommandError(
                "Aucune page d'accueil SIÈCLE trouvée. "
                "Lancez d'abord : python manage.py seed_siecle_builder"
            )

        sections = list(page.sections.order_by('position'))
        if not sections:
            raise CommandError(
                "La page n'a aucune section. "
                "Lancez d'abord : python manage.py seed_siecle_builder"
            )

        updated = 0
        for section in sections:
            img_url = IMAGES_BY_POSITION.get(section.position)
            if img_url is None:
                continue
            settings = dict(section.settings)
            if settings.get('image') == img_url:
                self.stdout.write(f"  [{section.position}] déjà à jour — {img_url}")
                continue
            settings['image'] = img_url
            section.settings = settings
            section.save(update_fields=['settings'])
            self.stdout.write(self.style.SUCCESS(f"  [{section.position}] {section.module_type} ← {img_url}"))
            updated += 1

        self.stdout.write(f"\n{updated} section(s) mise(s) à jour.")

        if do_publish:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.filter(is_superuser=True).first()
            publish_builder_page(page, user=user)
            self.stdout.write(self.style.SUCCESS("[OK] Page publiee."))
        else:
            self.stdout.write(
                "\nPour publier et voir les images sur le site :\n"
                "  python manage.py apply_siecle_images --publish\n"
                "  (ou cliquer 'Publier' dans l'éditeur)"
            )
