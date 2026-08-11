"""
python manage.py restore_backup --backup-id=1
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Restaure une sauvegarde (superuser uniquement)'

    def add_arguments(self, parser):
        parser.add_argument('--backup-id', type=int, required=True)
        parser.add_argument('--confirm', action='store_true', default=False,
                            help='Confirmer la restauration sans interaction')

    def handle(self, *args, **options):
        from apps.backups.models import BackupJob
        from apps.backups.services import restore_backup

        try:
            job = BackupJob.objects.get(pk=options['backup_id'])
        except BackupJob.DoesNotExist:
            self.stderr.write(f'Sauvegarde #{options["backup_id"]} introuvable')
            return

        if job.status != 'success':
            self.stderr.write(f'Impossible: statut = {job.status} (sauvegarde non reussie)')
            return

        self.stdout.write(f'Sauvegarde: {job.name}')
        self.stdout.write(f'Fichier:    {job.file_path}')
        self.stdout.write(f'Taille:     {job.file_size_display}')
        self.stdout.write(f'Entreprise: {job.company.name if job.company else "Base centrale"}')

        if not options['confirm']:
            confirm = input('\nATTENTION: Cette operation remplace les donnees actuelles.\nTaper "CONFIRMER" pour continuer: ')
            if confirm.strip() != 'CONFIRMER':
                self.stdout.write('Restauration annulee.')
                return

        self.stdout.write('Creation sauvegarde pre-restauration...')
        log = restore_backup(job)

        if log.status == 'success':
            self.stdout.write(self.style.SUCCESS('Restauration reussie.'))
        else:
            self.stderr.write(self.style.ERROR(f'Restauration echouee: {log.error_message}'))
