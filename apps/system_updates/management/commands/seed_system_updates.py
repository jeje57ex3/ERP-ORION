from django.core.management.base import BaseCommand

from apps.system_updates.models import SystemUpdateSettings


class Command(BaseCommand):
    help = 'Crée les paramètres par défaut du module mises à jour.'

    def handle(self, *args, **options):
        obj = SystemUpdateSettings.get_solo()
        self.stdout.write(self.style.SUCCESS(
            f'Paramètres mises à jour initialisés (id={obj.id}).'
        ))
