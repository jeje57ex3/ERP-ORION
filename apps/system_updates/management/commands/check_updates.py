from django.core.management.base import BaseCommand

from apps.system_updates.services import check_for_updates


class Command(BaseCommand):
    help = 'Vérifie si une mise à jour Orion ERP est disponible.'

    def handle(self, *args, **options):
        self.stdout.write('Vérification des mises à jour...')
        check = check_for_updates()
        self.stdout.write(f'Statut        : {check.status}')
        self.stdout.write(f'Commit actuel : {check.current_commit}')
        self.stdout.write(f'Commit distant: {check.remote_commit}')
        self.stdout.write(f'Retard        : {check.commits_behind} commit(s)')
        if check.changelog:
            self.stdout.write('\nChangelog :')
            self.stdout.write(check.changelog)
        if check.status == 'update_available':
            self.stdout.write(self.style.WARNING('Une mise à jour est disponible.'))
        elif check.status == 'up_to_date':
            self.stdout.write(self.style.SUCCESS('Orion ERP est à jour.'))
        else:
            self.stdout.write(self.style.ERROR(f'Erreur : {check.error_message}'))
