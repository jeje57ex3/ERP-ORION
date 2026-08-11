"""
python manage.py backup_database --scope=core
python manage.py backup_database --scope=company_database --company-id=1
"""
from django.core.management.base import BaseCommand
from apps.backups.services import create_database_backup


class Command(BaseCommand):
    help = 'Sauvegarde une base de données Orion ERP'

    def add_arguments(self, parser):
        parser.add_argument('--scope', default='core_database',
                            choices=['core_database', 'company_database'],
                            help='Perimetre de la sauvegarde')
        parser.add_argument('--company-id', type=int, default=None,
                            help='ID de l entreprise (requis si scope=company_database)')

    def handle(self, *args, **options):
        scope      = options['scope']
        company_id = options['company_id']
        company    = None

        if scope == 'company_database' and company_id:
            from apps.core.models import Company
            try:
                company = Company.objects.get(pk=company_id)
                self.stdout.write(f'Sauvegarde entreprise: {company.name}')
            except Company.DoesNotExist:
                self.stderr.write(f'Entreprise #{company_id} introuvable')
                return

        self.stdout.write(f'Lancement sauvegarde ({scope})...')
        job = create_database_backup(company=company, scope=scope)

        if job.status == 'success':
            self.stdout.write(self.style.SUCCESS(
                f'OK Sauvegarde reussie: {job.file_path} ({job.file_size_display}, {job.duration_display})'
            ))
        else:
            self.stderr.write(self.style.ERROR(f'ECHEC: {job.error_message}'))
