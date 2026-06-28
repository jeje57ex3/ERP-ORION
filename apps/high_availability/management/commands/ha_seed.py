from django.core.management.base import BaseCommand
from apps.high_availability.services import seed_default_ha_nodes


class Command(BaseCommand):
    help = 'Crée les paramètres HA par défaut avec un principal et deux secondaires.'

    def handle(self, *args, **options):
        seed_default_ha_nodes()
        self.stdout.write(self.style.SUCCESS(
            'Paramètres HA créés : 1 principal + 2 secondaires.'
        ))
