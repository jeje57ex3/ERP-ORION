"""
Vérifie que les BuilderPages sont liées aux bons Website réels.

Usage : python manage.py check_builder_sites
"""
from django.core.management.base import BaseCommand

from apps.site_builder.models import BuilderPage

EXPECTED_DOMAINS = {
    'siecle': 'siecle.elysiums.fr',
    'lunea':  'lunea.elysiums.fr',
}


class Command(BaseCommand):
    help = 'Vérifie si les BuilderPages sont liées aux bons sites réels.'

    def handle(self, *args, **options):
        pages = BuilderPage.objects.select_related('website', 'company').all()

        if not pages.exists():
            self.stdout.write(self.style.WARNING('Aucune BuilderPage trouvée.'))
            return

        for page in pages:
            website = page.website
            problems = []

            if not website:
                problems.append('aucun Website lié')
            else:
                if not website.is_active:
                    problems.append(f'Website inactif : {website.name}')

                expected_slug = page.brand_key
                if expected_slug and website.slug != expected_slug:
                    problems.append(
                        f'slug incohérent : page.brand_key={expected_slug}, website.slug={website.slug}'
                    )

                expected_domain = EXPECTED_DOMAINS.get(website.slug)
                if expected_domain and website.domain and website.domain != expected_domain:
                    problems.append(
                        f'domaine inattendu : {website.domain} (attendu {expected_domain})'
                    )

            tag = f'[{page.company.name}] Page {page.pk} « {page.title} »'

            if problems:
                self.stdout.write(
                    self.style.WARNING(f'⚠  {tag} : {", ".join(problems)}')
                )
            else:
                domain_info = website.domain or website.slug
                self.stdout.write(
                    self.style.SUCCESS(f'✓  {tag} → {website.name} / {domain_info}')
                )
