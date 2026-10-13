from django.core.management.base import BaseCommand

from apps.high_availability.services import check_all_ha_nodes
from apps.high_availability.takeover import precedence_order


class Command(BaseCommand):
    help = (
        'Vérifie les serveurs Orion HA, affiche l\'ordre de préséance et '
        'applique la règle de retour de main.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--no-failback',
            action='store_true',
            help='Constate sans jamais rendre la main, même en politique '
                 'automatique. À utiliser pour inspecter sans agir.',
        )

    def handle(self, *args, **options):
        results = check_all_ha_nodes(apply_failback=not options['no_failback'])

        for result in results:
            node = result['node']
            if result['ok']:
                self.stdout.write(self.style.SUCCESS(f'{node.node_id} OK'))
            else:
                self.stdout.write(
                    self.style.ERROR(f"{node.node_id} HORS LIGNE : {result['error']}")
                )

            decision = result.get('takeover') or {}
            if decision.get('error'):
                self.stdout.write(self.style.ERROR(f"    règle de retour : {decision['error']}"))
            elif decision.get('split_brain_suspected'):
                self.stdout.write(self.style.ERROR(f"    DIVERGENCE : {decision['reason']}"))
            elif decision.get('failback'):
                self.stdout.write(self.style.SUCCESS(f"    {decision['reason']}"))
            elif decision.get('proposed'):
                self.stdout.write(self.style.WARNING(f"    {decision['reason']}"))

        self.stdout.write('')
        self.stdout.write('Ordre de préséance :')
        for ligne in precedence_order():
            node = ligne['node']
            marques = []
            if ligne['is_active']:
                marques.append('ACTIF')
            if ligne['is_preferred']:
                marques.append('préféré')
            suffixe = f" [{', '.join(marques)}]" if marques else ''
            style = self.style.SUCCESS if ligne['eligible'] else self.style.WARNING
            self.stdout.write(style(
                f"  rang {node.priority}  {node.node_id}{suffixe} — {ligne['reason']}"
            ))
