"""
python manage.py backup_all
"""
from django.core.management.base import BaseCommand
from apps.backups.services import create_database_backup


class Command(BaseCommand):
    help = 'Sauvegarde la base centrale + toutes les entreprises actives'

    def handle(self, *args, **options):
        from apps.core.models import Company

        self.stdout.write('=== Sauvegarde globale Orion ERP ===')

        core_job = create_database_backup(scope='core_database')
        self._print(core_job, 'Base centrale')

        companies = Company.objects.filter(is_active=True).order_by('name')
        ok = 0
        fail = 0
        for company in companies:
            job = create_database_backup(company=company, scope='company_database')
            self._print(job, company.name)
            if job.status == 'success':
                ok += 1
            else:
                fail += 1

        self.stdout.write(f'\nResultat: {ok} OK / {fail} echoue(s) sur {companies.count()} entreprises')
        if fail:
            self.stdout.write(self.style.WARNING('Verifiez les erreurs ci-dessus.'))
        else:
            self.stdout.write(self.style.SUCCESS('Toutes les sauvegardes ont reussi.'))

    def _print(self, job, label):
        if job.status == 'success':
            self.stdout.write(self.style.SUCCESS(f'  OK {label}: {job.file_size_display}, {job.duration_display}'))
        else:
            self.stderr.write(self.style.ERROR(f'  FAIL {label}: {job.error_message[:100]}'))
