from django.core.management.base import BaseCommand

from apps.core.models import Company
from apps.website_shop_settings.services import create_default_shop_settings


class Command(BaseCommand):
    help = 'Crée les paramètres boutique par défaut pour toutes les entreprises (SIÈCLE + LUNEA).'

    def add_arguments(self, parser):
        parser.add_argument('--company-id', type=int, help='ID de l\'entreprise (toutes si absent).')
        parser.add_argument('--brand', choices=['siecle', 'lunea', 'all'], default='all')

    def handle(self, *args, **options):
        companies = Company.objects.filter(is_active=True)
        if options.get('company_id'):
            companies = companies.filter(pk=options['company_id'])

        brand = options['brand']
        brands = ['siecle', 'lunea'] if brand == 'all' else [brand]

        for company in companies:
            for brand_key in brands:
                shop = create_default_shop_settings(company=company, brand_key=brand_key)
                self.stdout.write(self.style.SUCCESS(
                    f'OK  {company.name} / {brand_key} -> {shop.site_name} (id={shop.id})'
                ))
