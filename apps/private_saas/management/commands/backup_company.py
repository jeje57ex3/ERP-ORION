"""
python manage.py backup_company --company=siecle
python manage.py backup_all_companies
"""
import os
import subprocess
from datetime import datetime
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings


class Command(BaseCommand):
    help = 'Sauvegarde la base de données d\'une ou toutes les entreprises'

    def add_arguments(self, parser):
        parser.add_argument('--company', default=None, help='Slug de l\'entreprise (ou "all")')
        parser.add_argument('--all', action='store_true', help='Sauvegarder toutes les entreprises')

    def handle(self, *args, **options):
        from apps.core.models import Company
        from apps.private_saas.models import CompanyBackup

        backup_dir = Path(getattr(settings, 'BACKUP_DIR', settings.BASE_DIR / 'backups'))
        backup_dir.mkdir(parents=True, exist_ok=True)

        if options['all'] or options['company'] == 'all':
            companies = Company.objects.filter(is_active=True)
        elif options['company']:
            try:
                companies = [Company.objects.get(slug=options['company'])]
            except Company.DoesNotExist:
                raise CommandError(f'Entreprise « {options["company"]} » introuvable.')
        else:
            raise CommandError('Spécifiez --company=<slug> ou --all')

        for company in companies:
            self.stdout.write(f'Sauvegarde de {company.name}…')
            backup = CompanyBackup.objects.create(
                company=company, backup_type='database', status='pending',
            )
            try:
                ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f'backup_{company.slug}_{ts}.sql'
                filepath = backup_dir / filename

                db = settings.DATABASES['default']
                db_name = getattr(company, 'database_name', None) or db['NAME']
                db_host = getattr(company, 'database_host', None) or db.get('HOST', '127.0.0.1')
                db_user = getattr(company, 'database_user', None) or db.get('USER', 'root')
                db_pwd  = getattr(company, 'database_password', None) or db.get('PASSWORD', '')

                env = os.environ.copy()
                if db_pwd:
                    env['MYSQL_PWD'] = db_pwd

                cmd = [
                    'mysqldump', '--host', db_host, '--user', db_user,
                    '--single-transaction', '--routines', '--triggers',
                    db_name,
                ]
                with open(filepath, 'w') as f:
                    result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, env=env)

                if result.returncode == 0:
                    size = filepath.stat().st_size
                    backup.file_path = str(filepath)
                    backup.status    = 'success'
                    backup.size      = size
                    backup.save(update_fields=['file_path', 'status', 'size'])
                    self.stdout.write(self.style.SUCCESS(f'  ✓ {filename} ({size // 1024} Ko)'))
                else:
                    err = result.stderr.decode()
                    backup.status        = 'error'
                    backup.error_message = err
                    backup.save(update_fields=['status', 'error_message'])
                    self.stdout.write(self.style.ERROR(f'  ✗ Erreur mysqldump: {err[:200]}'))

            except FileNotFoundError:
                backup.status        = 'error'
                backup.error_message = 'mysqldump non trouvé dans PATH'
                backup.save(update_fields=['status', 'error_message'])
                self.stdout.write(self.style.WARNING('  ! mysqldump non disponible — sauvegarde ignorée'))
            except Exception as e:
                backup.status        = 'error'
                backup.error_message = str(e)
                backup.save(update_fields=['status', 'error_message'])
                self.stdout.write(self.style.ERROR(f'  ✗ {e}'))
