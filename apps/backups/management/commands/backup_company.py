"""
python manage.py backup_company --company-id=1
"""
from django.core.management.base import BaseCommand
from apps.backups.services import create_database_backup, create_media_backup


class Command(BaseCommand):
    help = 'Sauvegarde complète d une entreprise (base + médias)'

    def add_arguments(self, parser):
        parser.add_argument('--company-id', type=int, required=True)
        parser.add_argument('--media', action='store_true', default=False,
                            help='Inclure les médias')

    def handle(self, *args, **options):
        from apps.core.models import Company
        try:
            company = Company.objects.get(pk=options['company_id'])
        except Company.DoesNotExist:
            self.stderr.write(f'Entreprise #{options["company_id"]} introuvable')
            return

        self.stdout.write(f'Sauvegarde: {company.name}...')
        db_job = create_database_backup(company=company, scope='company_database')
        self._print_result(db_job, 'Base de donnees')

        if options['media']:
            media_job = create_media_backup(company=company)
            self._print_result(media_job, 'Medias')

    def _print_result(self, job, label):
        if job.status == 'success':
            self.stdout.write(self.style.SUCCESS(
                f'  OK {label}: {job.file_path} ({job.file_size_display})'
            ))
        else:
            self.stderr.write(self.style.ERROR(f'  ECHEC {label}: {job.error_message}'))
