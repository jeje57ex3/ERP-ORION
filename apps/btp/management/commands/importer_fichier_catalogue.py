"""
Importe un tarif depuis un fichier posé sur le disque du serveur.

Pourquoi en plus du dépôt par navigateur : le tarif Schneider dépasse les
cent mille références, soit une vingtaine de mégaoctets en Excel. Le faire
transiter par un formulaire web passe par la mémoire du worker gunicorn et
par le délai d'attente de nginx, pour un fichier qui est déjà sur la
machine ou qu'un `scp` y dépose en quelques secondes.

L'essai à blanc est le mode par défaut — il faut demander `--ecrire` pour
qu'il écrive. Sur un fichier de cette taille, une correspondance de
colonnes fausse créerait cent mille articles aberrants, et les défaire
prendrait plus longtemps que de relire la sortie d'un essai.
"""

import os

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = ('Importe un fichier de tarif local dans une source de '
            'catalogue. Essai à blanc par défaut.')

    def add_arguments(self, parser):
        parser.add_argument('fichier', help='Chemin du CSV, Excel ou JSON.')
        parser.add_argument(
            '--source', required=True, type=int,
            help='Identifiant de la source de catalogue (visible dans son '
                 'URL dans l\'ERP).')
        parser.add_argument(
            '--ecrire', action='store_true',
            help='Écrit réellement. Sans ce drapeau, essai à blanc.')

    def handle(self, *args, **options):
        from ...catalogue_import import CatalogueError, executer
        from ...models import CatalogueSource

        chemin = options['fichier']
        if not os.path.isfile(chemin):
            raise CommandError(f'Fichier introuvable : {chemin}')

        source = CatalogueSource.objects.filter(pk=options['source']).first()
        if source is None:
            connues = '\n'.join(
                f'  {s.pk:>4}  {s.company.slug:<16} {s.name}'
                for s in CatalogueSource.objects.select_related(
                    'company').order_by('company__slug', 'name')[:40])
            raise CommandError(
                f'Aucune source d\'identifiant {options["source"]}.\n'
                f'Sources connues :\n{connues or "  aucune"}')

        a_blanc = not options['ecrire']
        taille = os.path.getsize(chemin)
        self.stdout.write(
            f'{os.path.basename(chemin)} — {taille / 1024 / 1024:.1f} Mo\n'
            f'source : {source.name} ({source.company.slug})\n'
            f'format : {source.format} — nature par défaut : '
            f'{source.nature_par_defaut}\n'
            f'colonnes : {source.colonnes or "AUCUNE CORRESPONDANCE DÉFINIE"}\n'
            + ('mode   : ESSAI À BLANC (rien ne sera écrit)\n' if a_blanc
               else 'mode   : ÉCRITURE RÉELLE\n'))

        with open(chemin, 'rb') as flux:
            octets = flux.read()

        try:
            journal = executer(source, a_blanc=a_blanc, octets=octets)
        except CatalogueError as exc:
            raise CommandError(str(exc))

        if journal.statut == 'echec':
            raise CommandError(
                f'Import échoué : {journal.message or "cause inconnue"}')

        self.stdout.write('')
        self.stdout.write(f'  lignes lues  : {journal.lignes_lues}')
        self.stdout.write(f'  à créer      : {journal.crees}' if a_blanc
                          else f'  créés        : {journal.crees}')
        self.stdout.write(f'  à modifier   : {journal.mis_a_jour}' if a_blanc
                          else f'  modifiés     : {journal.mis_a_jour}')
        self.stdout.write(f'  inchangés    : {journal.inchanges}')
        if journal.ignores:
            self.stdout.write(self.style.WARNING(
                f'  ignorées     : {journal.ignores}'))
        if journal.erreurs:
            self.stdout.write(self.style.WARNING(
                f'  erreurs      : {journal.erreurs}'))

        # Pas d'avertissement « aucun article » ici : l'importeur classe ce
        # cas en échec et porte désormais lui-même le diagnostic, qui
        # remonte dans le CommandError plus haut. Le répéter ici aurait
        # fait deux messages à maintenir, dont un inatteignable.

        if a_blanc:
            self.stdout.write('')
            self.stdout.write(
                'Essai à blanc : rien n\'a été écrit. Relancez avec '
                '--ecrire quand la sortie vous paraît juste.')
