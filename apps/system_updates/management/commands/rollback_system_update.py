from django.core.management.base import BaseCommand, CommandError

from apps.system_updates.models import SystemUpdateRun
from apps.system_updates.rollback import rollback_update


class Command(BaseCommand):
    help = 'Rollback une mise à jour Orion ERP vers le commit précédent.'

    def add_arguments(self, parser):
        parser.add_argument('--update-id', type=int, required=True,
                            help='ID de la mise à jour à annuler.')

    def handle(self, *args, **options):
        try:
            update_run = SystemUpdateRun.objects.get(id=options['update_id'])
        except SystemUpdateRun.DoesNotExist:
            raise CommandError(f"Mise à jour #{options['update_id']} introuvable.")

        self.stdout.write(
            f'Rollback vers le commit {update_run.from_commit[:8]}...'
        )
        rollback = rollback_update(update_run)
        self.stdout.write(self.style.SUCCESS(
            f'Rollback terminé : #{rollback.id} — {rollback.status}'
        ))
