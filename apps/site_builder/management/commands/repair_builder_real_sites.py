"""
Relie les BuilderPages SIÈCLE/LUNEA aux vrais Website existants de leur entreprise.

Usage : python manage.py repair_builder_real_sites [--dry-run]
"""
from django.core.management.base import BaseCommand

from apps.site_builder.models import BuilderPage
from apps.websites.models import Website

BRAND_SLUGS = ('siecle', 'lunea')


class Command(BaseCommand):
    help = 'Relie les BuilderPages aux vrais Website correspondants (par brand_key / company).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Affiche les corrections sans les appliquer.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        repaired = 0
        skipped = 0

        pages = (
            BuilderPage.objects
            .select_related('website', 'company')
            .filter(brand_key__in=BRAND_SLUGS)
        )

        for page in pages:
            target = Website.objects.filter(
                company=page.company,
                slug=page.brand_key,
                is_active=True,
            ).first()

            if not target:
                self.stdout.write(
                    self.style.WARNING(
                        f'⚠  Page {page.pk} « {page.title} » : '
                        f'aucun site actif avec slug={page.brand_key} '
                        f'pour {page.company.name}'
                    )
                )
                skipped += 1
                continue

            if page.website_id == target.pk:
                continue

            msg = (
                f'Page {page.pk} « {page.title} » '
                f'[{page.company.name}] : '
                f'{page.website.slug if page.website else "None"} → {target.slug} '
                f'({target.name})'
            )

            if dry_run:
                self.stdout.write(self.style.MIGRATE_HEADING(f'[dry-run] {msg}'))
            else:
                page.website = target
                page.save(update_fields=['website', 'updated_at'])
                self.stdout.write(self.style.SUCCESS(f'Réparé : {msg}'))
                repaired += 1

        suffix = ' (dry-run)' if dry_run else ''
        self.stdout.write(
            self.style.SUCCESS(
                f'\n{repaired} page(s) réparée(s){suffix}, {skipped} ignorée(s).'
            )
        )
