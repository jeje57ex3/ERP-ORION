from django.core.management.base import BaseCommand
from apps.high_availability.services import check_all_ha_nodes


class Command(BaseCommand):
    help = 'Vérifie les serveurs Orion HA.'

    def handle(self, *args, **options):
        results = check_all_ha_nodes()
        for result in results:
            node = result['node']
            if result['ok']:
                self.stdout.write(self.style.SUCCESS(f'{node.node_id} OK'))
            else:
                self.stdout.write(self.style.ERROR(f"{node.node_id} DOWN : {result['error']}"))
