"""
python manage.py scan_competitors --company-id=1
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Scan legal des sites concurrents (respecte robots.txt)'

    def add_arguments(self, parser):
        parser.add_argument('--company-id', type=int, required=True)

    def handle(self, *args, **options):
        from apps.core.models import Company
        from apps.competitor_intelligence.models import CompetitorSite
        from apps.competitor_intelligence.services.competitor_service import scan_public_product_page
        from django.utils import timezone

        try:
            company = Company.objects.get(pk=options['company_id'])
        except Company.DoesNotExist:
            self.stderr.write(f'Entreprise #{options["company_id"]} introuvable')
            return

        self.stdout.write(f'Scan concurrents: {company.name}')
        sites = CompetitorSite.objects.filter(
            competitor__company=company,
            tracking_enabled=True,
        ).exclude(scan_frequency='manual')

        ok, fail = 0, 0
        for site in sites:
            result = scan_public_product_page(site.site_url)
            site.last_scan_at = timezone.now()
            site.status = 'active' if result.get('accessible') else 'error'
            site.save(update_fields=['last_scan_at', 'status'])
            if result.get('accessible'):
                self.stdout.write(self.style.SUCCESS(f'  OK {site.competitor.name}: {site.site_url}'))
                ok += 1
            else:
                reason = result.get('reason', 'inaccessible')
                self.stdout.write(self.style.WARNING(f'  ~ {site.competitor.name}: {reason}'))
                fail += 1

        self.stdout.write(f'\nResultat: {ok} OK / {fail} echecs sur {ok+fail} sites')
