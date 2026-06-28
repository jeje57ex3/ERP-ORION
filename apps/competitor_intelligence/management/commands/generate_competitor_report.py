"""
python manage.py generate_competitor_report --company-id=1
"""
import os
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Genere un rapport Excel d analyse concurrentielle'

    def add_arguments(self, parser):
        parser.add_argument('--company-id', type=int, required=True)
        parser.add_argument('--output', default='', help='Chemin de sortie du rapport')

    def handle(self, *args, **options):
        from apps.core.models import Company
        from apps.competitor_intelligence.models import Competitor
        from apps.competitor_intelligence.services.report_service import generate_competitor_excel_report
        from django.conf import settings

        try:
            company = Company.objects.get(pk=options['company_id'])
        except Company.DoesNotExist:
            self.stderr.write(f'Entreprise #{options["company_id"]} introuvable')
            return

        ids = list(Competitor.objects.filter(company=company, is_active=True).values_list('pk', flat=True))
        if not ids:
            self.stderr.write('Aucun concurrent actif pour cette entreprise')
            return

        self.stdout.write(f'Generation rapport pour {company.name} ({len(ids)} concurrents)...')

        try:
            buf = generate_competitor_excel_report(company, ids)
        except ImportError as e:
            self.stderr.write(f'Dependance manquante: {e}\nInstallez openpyxl: pip install openpyxl')
            return

        output_path = options['output']
        if not output_path:
            from datetime import datetime
            ts          = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_dir  = os.path.join(settings.BASE_DIR, 'storage', 'reports')
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, f'concurrents_{company.slug}_{ts}.xlsx')

        with open(output_path, 'wb') as f:
            f.write(buf.getvalue())

        self.stdout.write(self.style.SUCCESS(f'Rapport sauvegarde: {output_path}'))
