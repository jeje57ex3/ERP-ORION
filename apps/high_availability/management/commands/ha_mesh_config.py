"""Expose la configuration du réseau privé, pour le script shell.

Une seule source de vérité : la dérivation « rang -> adresse privée » vit dans
apps/high_availability/mesh.py, et orion-mesh.sh la consomme en sourçant la
sortie de cette commande. Dupliquer le calcul de part et d'autre aurait
garanti qu'ils divergent un jour.
"""

from django.core.management.base import BaseCommand, CommandError

from apps.high_availability.mesh import (
    MeshConfigError,
    config_locale,
    entrees_hosts,
    pairs_attendus,
)


class Command(BaseCommand):
    help = "Affiche la configuration du réseau privé (sourçable par un shell)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--hosts', action='store_true',
            help="Affiche les lignes /etc/hosts déduites (adresse puis nom).",
        )
        parser.add_argument(
            '--peers', action='store_true',
            help='Affiche les pairs attendus pour ce serveur.',
        )

    def handle(self, *args, **options):
        try:
            if options['hosts']:
                for adresse, hote in entrees_hosts():
                    self.stdout.write(f'{adresse} {hote}')
                return

            if options['peers']:
                for pair in pairs_attendus():
                    self.stdout.write(
                        f"{pair['rang']} {pair['adresse']} {pair['hote']} {pair['node_id']}"
                    )
                return

            for cle, valeur in config_locale().items():
                self.stdout.write(f'{cle}={valeur}')

        except MeshConfigError as exc:
            raise CommandError(str(exc))
