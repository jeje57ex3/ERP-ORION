"""
python manage.py check_backups
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Verifie l integrite et l etat des sauvegardes'

    def handle(self, *args, **options):
        from apps.backups.models import BackupJob
        from apps.backups.services import verify_backup_integrity, get_backup_stats
        import os

        self.stdout.write('\n=== Diagnostic Sauvegardes Orion ERP ===\n')

        stats = get_backup_stats()
        self.stdout.write(f'Total sauvegardes:   {stats["total"]}')
        self.stdout.write(f'  Reussies:          {stats["success"]}')
        self.stdout.write(f'  Echouees:          {stats["failed"]}')
        self.stdout.write(f'  En cours:          {stats["running"]}')

        size = stats['total_size']
        for unit in ['o', 'Ko', 'Mo', 'Go']:
            if size < 1024:
                size_str = f'{size:.1f} {unit}'
                break
            size /= 1024
        else:
            size_str = f'{size:.1f} To'
        self.stdout.write(f'  Taille totale:     {size_str}')

        if stats['last_success']:
            last = stats['last_success']
            self.stdout.write(f'  Derniere reussie:  {last.name} ({last.finished_at:%d/%m/%Y %H:%M})')

        self.stdout.write('\n--- Verification integrite ---')
        ok_count = 0
        fail_count = 0
        missing_count = 0

        for job in BackupJob.objects.filter(status='success').order_by('-created_at')[:20]:
            if not job.file_path:
                continue
            if not os.path.exists(job.file_path):
                missing_count += 1
                self.stdout.write(self.style.WARNING(f'  MANQUANT #{job.pk}: {job.name}'))
                continue
            ok, msg = verify_backup_integrity(job)
            if ok:
                ok_count += 1
            else:
                fail_count += 1
                self.stdout.write(self.style.ERROR(f'  CORROMPU #{job.pk}: {job.name} — {msg}'))

        if fail_count == 0 and missing_count == 0:
            self.stdout.write(self.style.SUCCESS(f'  OK {ok_count} fichiers verifies — integrité OK'))
        else:
            self.stdout.write(self.style.WARNING(
                f'  {ok_count} OK / {fail_count} corrompus / {missing_count} manquants'
            ))

        self.stdout.write('\n=====================================\n')
