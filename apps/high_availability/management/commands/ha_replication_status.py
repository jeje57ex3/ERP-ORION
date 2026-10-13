"""Relève l'état de la réplication locale et le consigne.

Deux usages : un coup d'œil en ligne de commande, et l'alimentation de
`OrionHAReplicationStatus` pour le nœud courant — que rien n'écrivait, d'où
une page Réplication vide quelle que soit la configuration réelle.
"""

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.high_availability.models import OrionHANode
from apps.high_availability.replication import appliquer_etat, lire_status_local


class Command(BaseCommand):
    help = "Affiche et consigne l'état de la réplication de ce serveur."

    def add_arguments(self, parser):
        parser.add_argument(
            '--no-save', action='store_true',
            help='Affiche sans rien consigner en base.',
        )

    def handle(self, *args, **options):
        etat = lire_status_local()

        if not etat['is_replica']:
            self.stdout.write(self.style.WARNING(
                'Ce serveur ne réplique rien (serveur autonome ou source).'
            ))
            lecture_seule = etat.get('read_only')
            if lecture_seule is None:
                self.stdout.write('  Lecture seule : inconnue')
            else:
                self.stdout.write(f"  Lecture seule : {'oui' if lecture_seule else 'non'}")
        else:
            style = self.style.SUCCESS if etat['status'] == 'ok' else self.style.ERROR
            self.stdout.write(style(f"Réplication : {etat['status']}"))
            self.stdout.write(f"  Source            : {etat['source_host'] or '?'}")
            self.stdout.write(f"  Fil de réception  : {'actif' if etat['io_running'] else 'ARRÊTÉ'}")
            self.stdout.write(f"  Fil d'application : {'actif' if etat['sql_running'] else 'ARRÊTÉ'}")
            retard = etat['lag_seconds']
            self.stdout.write(
                f"  Retard            : {retard} s" if retard is not None
                else '  Retard            : inconnu (réplication arrêtée)'
            )
            self.stdout.write(f"  Journal           : {etat['log_file']}:{etat['log_position']}")
            for erreur in etat['errors']:
                self.stdout.write(self.style.ERROR(f'  Erreur : {erreur}'))

        if options['no_save']:
            return

        # Le nœud courant est identifié par ORION_NODE_ID : c'est la seule
        # valeur qui désigne CETTE machine, le nœud actif en base pouvant être
        # un autre serveur.
        node_id = getattr(settings, 'ORION_NODE_ID', '')
        node = OrionHANode.objects.filter(node_id=node_id).first()
        if not node:
            self.stdout.write(self.style.WARNING(
                f'\nNon consigné : aucun serveur « {node_id} » dans la grappe. '
                'Raccordez-le depuis la page Relier les serveurs.'
            ))
            return

        appliquer_etat(node, etat)
        self.stdout.write(self.style.SUCCESS(f'\nConsigné pour « {node.node_id} ».'))
