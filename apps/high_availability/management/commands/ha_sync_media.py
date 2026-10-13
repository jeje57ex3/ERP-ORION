"""Pousse les fichiers téléversés vers les autres serveurs de la grappe.

À planifier sur le serveur actif. La commande se protège elle-même : lancée
sur un serveur passif, elle refuse de copier — sans quoi des fichiers anciens
écraseraient les récents de l'actif.
"""

from django.core.management.base import BaseCommand

from apps.high_availability.media_sync import synchroniser


class Command(BaseCommand):
    help = 'Synchronise les médias du serveur actif vers les autres serveurs.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--constat', action='store_true',
            help='Affiche les commandes qui seraient lancées, sans rien copier.',
        )

    def handle(self, *args, **options):
        resultat = synchroniser(executer=not options['constat'])

        if resultat['skipped']:
            self.stdout.write(self.style.WARNING(resultat['reason']))
            return

        echecs = 0
        for ligne in resultat['resultats']:
            cible = f"{ligne['node_id']} ({ligne['adresse']})"
            if options['constat']:
                self.stdout.write(f'{cible} :')
                self.stdout.write('  ' + ' '.join(ligne['commande']))
                continue

            if ligne['ok']:
                self.stdout.write(self.style.SUCCESS(f'{cible} : {ligne["detail"]}'))
            else:
                echecs += 1
                self.stdout.write(self.style.ERROR(f'{cible} : {ligne["detail"]}'))

        if echecs:
            self.stdout.write(self.style.ERROR(
                f'\n{echecs} serveur(s) en échec. Le réseau privé est-il actif, '
                "et la clé SSH du compte orion en place sur la destination ?"
            ))
