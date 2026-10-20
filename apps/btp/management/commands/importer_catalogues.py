"""Import programmé des catalogues web.

À appeler par cron ou par Celery beat. La commande décide elle-même quelles
sources sont dues, d'après `intervalle_minutes` et `derniere_execution` :
l'ordonnanceur n'a donc rien à savoir des intervalles, et peut tourner
toutes les quinze minutes sans importer quinze fois par heure.

    */15 * * * *  /opt/orion/venv/bin/python manage.py importer_catalogues

Un échec sur une source n'arrête pas les autres : un fournisseur dont le
serveur est en panne ne doit pas priver l'exploitant de ses cinq autres
tarifs. Chaque résultat est journalisé dans CatalogueImport, consultable
depuis l'écran de la source.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Importe les catalogues web dont l’intervalle est écoulé.'

    def add_arguments(self, analyseur):
        analyseur.add_argument(
            '--forcer', action='store_true',
            help='Importe toutes les sources actives, sans tenir compte de '
                 'l’intervalle.')
        analyseur.add_argument(
            '--a-blanc', action='store_true',
            help='Lit et compte sans rien écrire.')
        analyseur.add_argument(
            '--source', type=int, default=None,
            help='Identifiant d’une seule source à traiter.')

    def handle(self, *args, **options):
        from datetime import timedelta

        from apps.btp.catalogue_import import executer
        from apps.btp.models import CatalogueSource

        sources = CatalogueSource.objects.filter(is_active=True)
        if options['source']:
            sources = sources.filter(pk=options['source'])

        maintenant = timezone.now()
        traitees = 0

        for source in sources.select_related('company'):
            if not options['forcer'] and source.derniere_execution:
                echeance = source.derniere_execution + timedelta(
                    minutes=source.intervalle_minutes or 1440)
                if maintenant < echeance:
                    continue

            # Chaque source dans son propre essai : un fournisseur en panne
            # ne doit pas priver l'exploitant de ses autres tarifs.
            try:
                journal = executer(source, a_blanc=options['a_blanc'])
            except Exception as exc:  # noqa: BLE001
                # Volontairement large, et journalise : une exception
                # imprevue ici (reseau, encodage, pilote) arreterait la
                # boucle et les sources suivantes seraient silencieusement
                # sautees jusqu'au prochain passage de cron.
                self.stderr.write(self.style.ERROR(
                    f'{source.name} : erreur inattendue — {exc}'))
                continue

            traitees += 1
            ligne = (f'{source.name} : {journal.get_statut_display()} — '
                     f'{journal.lignes_lues} lue(s), {journal.crees} créé(s), '
                     f'{journal.mis_a_jour} modifié(s), '
                     f'{journal.inchanges} inchangé(s)')
            if journal.ignores:
                ligne += f', {journal.ignores} ignorée(s)'
            if journal.statut == 'echec':
                self.stderr.write(self.style.ERROR(
                    f'{source.name} : {journal.message}'))
            elif journal.ignores:
                self.stdout.write(self.style.WARNING(ligne))
            else:
                self.stdout.write(self.style.SUCCESS(ligne))

        if not traitees:
            self.stdout.write('Aucune source due pour le moment.')
