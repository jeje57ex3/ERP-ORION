from django.core.management.base import BaseCommand

from apps.system_updates.update_runner import run_system_update


class Command(BaseCommand):
    help = 'Lance une mise à jour Orion ERP (backend + frontend + migrations).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--no-confirm',
            action='store_true',
            help='Bypasse la confirmation interactive.',
        )

    def handle(self, *args, **options):
        if not options['no_confirm']:
            self.stdout.write(self.style.WARNING(
                'ATTENTION : Cette commande va mettre à jour Orion ERP.\n'
                'Une sauvegarde sera lancée si configurée.\n'
                'Tapez "oui" pour confirmer :'
            ))
            answer = input().strip().lower()
            if answer not in ('oui', 'yes', 'y'):
                self.stdout.write('Annulé.')
                return

        self.stdout.write('Lancement de la mise à jour...')
        update_run = run_system_update()
        self.stdout.write(self.style.SUCCESS(
            f'Mise à jour terminée : #{update_run.id} — {update_run.status}'
        ))
