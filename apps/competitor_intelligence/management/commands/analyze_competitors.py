"""
python manage.py analyze_competitors --company-id=1
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Analyse et scoring des concurrents d une entreprise'

    def add_arguments(self, parser):
        parser.add_argument('--company-id', type=int, required=True)

    def handle(self, *args, **options):
        from apps.core.models import Company
        from apps.competitor_intelligence.models import Competitor
        from apps.competitor_intelligence.services.analysis_service import (
            generate_competitor_score, analyze_market_position,
        )
        from apps.competitor_intelligence.services.price_tracker import calculate_price_index

        try:
            company = Company.objects.get(pk=options['company_id'])
        except Company.DoesNotExist:
            self.stderr.write(f'Entreprise #{options["company_id"]} introuvable')
            return

        self.stdout.write(f'\n=== Analyse concurrentielle: {company.name} ===\n')

        position = analyze_market_position(company)
        self.stdout.write(f'Concurrents suivis:  {position["competitors_count"]}')
        self.stdout.write(f'Produits trackes:    {position["products_tracked"]}')

        price_data = calculate_price_index(company)
        if price_data['competitor_avg']:
            self.stdout.write(f'Prix moyen marche:   {price_data["competitor_avg"]:.2f} EUR')
        if price_data['gap_percent'] is not None:
            sign = '+' if price_data['gap_percent'] > 0 else ''
            self.stdout.write(f'Ecart nos prix:      {sign}{price_data["gap_percent"]}%')

        self.stdout.write('\n--- Classement concurrents ---')
        for entry in position['ranking']:
            c     = entry['competitor']
            score = entry['score']
            bar   = '#' * (score // 10)
            self.stdout.write(f'  {score:3d}/100 [{bar:<10}] {c.name}')

        self.stdout.write('\n=====================================\n')
