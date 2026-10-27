"""
Usage: python manage.py seed_site_builder --website-slug siecle
Creates a sample homepage with hero + features + CTA sections.
"""
from django.core.management.base import BaseCommand, CommandError

from apps.core.models import Company
from apps.websites.models import Website
from apps.site_builder.models import BuilderPage
from apps.site_builder.services import add_section_to_page


class Command(BaseCommand):
    help = 'Seed site_builder with a sample page for a given website.'

    def add_arguments(self, parser):
        parser.add_argument('--website-slug', required=True)
        parser.add_argument('--company-id', type=int, default=None)

    def handle(self, *args, **options):
        slug = options['website_slug']
        company_id = options['company_id']

        qs = Website.objects.filter(slug=slug, is_active=True)
        if company_id:
            qs = qs.filter(company_id=company_id)

        website = qs.first()
        if not website:
            raise CommandError(f"Site introuvable : slug='{slug}'")

        if BuilderPage.objects.filter(website=website, slug='accueil').exists():
            self.stdout.write(self.style.WARNING('Page d\'accueil déjà existante, skip.'))
            return

        page = BuilderPage.objects.create(
            company=website.company,
            website=website,
            brand_key=website.slug,
            title='Accueil',
            slug='accueil',
            is_homepage=True,
            status=BuilderPage.STATUS_DRAFT,
        )

        for module_type in ['hero', 'features', 'cta']:
            add_section_to_page(page, module_type)

        self.stdout.write(self.style.SUCCESS(
            f'Page « {page.title} » créée (id={page.pk}) avec 3 sections. '
            f'Builder : /erp/site-builder/pages/{page.pk}/builder/'
        ))
