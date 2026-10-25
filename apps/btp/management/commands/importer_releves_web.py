"""
Importe les relevés de catalogues livrés avec le code.

Les CSV produits par `explorer_catalogue` sont versionnés dans
`data/catalogues/`. Ils arrivent donc sur le serveur avec la mise à jour,
et cette commande les importe sans qu'aucun fichier n'ait à passer par un
navigateur.

Pourquoi cette voie plutôt que le dépôt manuel : explorer un catalogue
complet représente des milliers de requêtes — 1 704 fiches chez Legrand,
6 706 chez Hager — soit plus d'une heure. Le faire une fois, versionner le
résultat, et le déployer comme du code évite de refaire ce travail sur
chaque machine, et laisse une trace de ce qui a été importé et quand.

**Essai à blanc par défaut.** Il faut `--ecrire`. Sur huit mille articles,
une correspondance de colonnes fausse en créerait huit mille d'aberrants,
et les défaire prendrait plus longtemps que de relire une sortie.

Chaque fichier va dans la source « Relevé web <fabricant> », distincte du
« Tarif <fabricant> » du portail distributeur : deux provenances, deux
degrés de confiance, et les mélanger ferait écraser un tarif négocié par un
prix public.
"""

import os

from django.core.management.base import BaseCommand, CommandError

# Le fabricant est lu dans le nom du fichier, pas dans son contenu : il
# faut savoir à quelle source l'envoyer AVANT de lire la moindre ligne.
DOSSIER = os.path.join('data', 'catalogues')


class Command(BaseCommand):
    help = ('Importe les CSV de data/catalogues/ dans les sources '
            '« Relevé web ». Essai à blanc par défaut.')

    def add_arguments(self, parser):
        parser.add_argument('--entreprise', required=True,
                            help='Slug de l\'entreprise.')
        parser.add_argument(
            '--dossier', default='',
            help=f'Dossier des CSV. Défaut : {DOSSIER} à la racine du '
                 f'projet.')
        parser.add_argument(
            '--fabricant', default='',
            help='N\'importer que ce fabricant (legrand, hager, soprema).')
        parser.add_argument('--ecrire', action='store_true',
                            help='Écrit réellement. Sans ce drapeau, essai '
                                 'à blanc.')

    def handle(self, *args, **options):
        from django.conf import settings

        from apps.core.models import Company

        from ...catalogue_import import CatalogueError, executer
        from ...models import CatalogueSource

        company = Company.objects.filter(slug=options['entreprise']).first()
        if company is None:
            raise CommandError(
                f'Aucune entreprise de slug « {options["entreprise"]} ».')

        dossier = options['dossier'] or os.path.join(
            str(settings.BASE_DIR), DOSSIER)
        if not os.path.isdir(dossier):
            raise CommandError(
                f'Dossier introuvable : {dossier}. Les relevés sont '
                f'versionnés dans {DOSSIER} et arrivent avec la mise à jour.')

        fichiers = sorted(
            nom for nom in os.listdir(dossier) if nom.lower().endswith('.csv'))
        if options['fabricant']:
            vise = options['fabricant'].lower()
            fichiers = [nom for nom in fichiers if vise in nom.lower()]
        if not fichiers:
            raise CommandError(f'Aucun CSV dans {dossier}.')

        a_blanc = not options['ecrire']
        self.stdout.write(
            f'dossier : {dossier}\n'
            f'fichiers : {len(fichiers)}\n'
            + ('mode    : ESSAI À BLANC (rien ne sera écrit)\n' if a_blanc
               else 'mode    : ÉCRITURE RÉELLE\n'))

        # Les sources, indexées par le mot distinctif de leur nom. Une
        # correspondance par sous-chaîne et non exacte : le fichier
        # s'appelle « legrand », la source « Relevé web Legrand ».
        sources = {
            source.name.replace('Relevé web ', '').lower(): source
            for source in CatalogueSource.objects.filter(
                company=company, name__startswith='Relevé web ')
        }
        if not sources:
            raise CommandError(
                'Aucune source « Relevé web » pour cette entreprise. '
                'Lancez d\'abord : manage.py creer_sources_fabricants '
                f'--entreprise {company.slug}')

        total = {'crees': 0, 'mis_a_jour': 0, 'inchanges': 0, 'ignores': 0}
        traites, ignores = 0, []

        for nom in fichiers:
            source = self._source_du_fichier(nom, sources)
            if source is None:
                ignores.append(nom)
                self.stdout.write(self.style.WARNING(
                    f'  ? {nom} — aucune source « Relevé web » ne '
                    f'correspond ; renommez le fichier avec le nom du '
                    f'fabricant.'))
                continue

            chemin = os.path.join(dossier, nom)
            with open(chemin, 'rb') as flux:
                octets = flux.read()

            try:
                journal = executer(source, a_blanc=a_blanc, octets=octets)
            except CatalogueError as exc:
                self.stdout.write(self.style.ERROR(f'  ! {nom} — {exc}'))
                continue

            if journal.statut == 'echec':
                self.stdout.write(self.style.ERROR(
                    f'  ! {nom} — {journal.message or "cause inconnue"}'))
                continue

            traites += 1
            for cle in total:
                total[cle] += getattr(journal, cle)
            verbes = (('à créer', 'à modifier') if a_blanc
                      else ('créés', 'modifiés'))
            self.stdout.write(
                f'  + {nom} → {source.name} : {journal.lignes_lues} ligne(s), '
                f'{journal.crees} {verbes[0]}, '
                f'{journal.mis_a_jour} {verbes[1]}, '
                f'{journal.inchanges} inchangé(s)')

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'{traites} fichier(s) traité(s) : {total["crees"]} article(s) '
            f'{"à créer" if a_blanc else "créé(s)"}, '
            f'{total["mis_a_jour"]} {"à modifier" if a_blanc else "modifié(s)"}, '
            f'{total["inchanges"]} inchangé(s).'))

        if total['ignores']:
            self.stdout.write(self.style.WARNING(
                f'{total["ignores"]} ligne(s) ignorée(s) — désignation vide, '
                f'le plus souvent.'))

        # Rappel du sens des prix, parce que c'est là que se jouent les
        # marges : ces montants sont des prix PUBLICS, marqués « indicatif,
        # à confirmer » sur chaque article.
        self.stdout.write(
            'Les prix importés sont des prix publics, cochés « prix '
            'indicatif, à confirmer ». Décochez la case article par article '
            'quand vous aurez les tarifs négociés — ils ne seront alors plus '
            'jamais écrasés par un import.')

        if a_blanc:
            self.stdout.write('')
            self.stdout.write(
                'Essai à blanc : rien n\'a été écrit. Relancez avec '
                '--ecrire quand la sortie vous paraît juste.')

    @staticmethod
    def _source_du_fichier(nom, sources):
        """La source dont le fabricant apparaît dans le nom du fichier.

        Les plus longs d'abord : « schneider electric » doit gagner sur
        « schneider » si les deux existent, sinon le fichier partirait dans
        la mauvaise source.
        """
        bas = nom.lower()
        for cle in sorted(sources, key=len, reverse=True):
            # Le nom de la source peut porter plusieurs mots ; on teste le
            # premier, qui suffit à distinguer les fabricants.
            if cle in bas or cle.split()[0] in bas:
                return sources[cle]
        return None
