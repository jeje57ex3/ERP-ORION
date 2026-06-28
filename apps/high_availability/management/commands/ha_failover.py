from django.core.management.base import BaseCommand
from apps.high_availability.models import OrionHANode
from apps.high_availability.failover import run_manual_failover_to_node


class Command(BaseCommand):
    help = 'Bascule Orion ERP vers un serveur secondaire choisi.'

    def add_arguments(self, parser):
        parser.add_argument('--to-node', required=True, help='node_id cible')
        parser.add_argument('--reason', default='Bascule manuelle CLI')

    def handle(self, *args, **options):
        try:
            target = OrionHANode.objects.get(node_id=options['to_node'])
        except OrionHANode.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"Nœud '{options['to_node']}' introuvable."))
            return

        event = run_manual_failover_to_node(
            target_node=target,
            reason=options['reason'],
        )
        self.stdout.write(self.style.SUCCESS(
            f'Failover terminé vers {target.node_id}. Event #{event.id}'
        ))
