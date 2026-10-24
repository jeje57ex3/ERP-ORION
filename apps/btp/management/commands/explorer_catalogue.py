"""
Explore le catalogue public d'un fabricant et en tire des articles.

Essai à blanc par défaut : il faut `--ecrire` pour qu'il écrive. Sur un
catalogue entier, une erreur de motif créerait des milliers d'articles
aberrants, et les défaire prendrait plus longtemps que de relire une
sortie.

Reprise : la liste des pages déjà visitées est conservée dans un fichier
d'état, pour qu'une exécution interrompue — ou volontairement bornée —
reprenne où elle s'était arrêtée. Un catalogue complet représente des
milliers de requêtes et ne passe pas en une fois.

**Le prix atterrit dans `prix_indicatif`, jamais dans `purchase_price`.**
Un prix de détail public n'est pas le prix auquel l'entreprise achète.
Voir `catalogue_crawl.importer_candidats`.
"""

import json
import os

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = ('Parcourt le catalogue public d\'un fabricant (Legrand, Hager, '
            'Soprema) et crée les articles correspondants.')

    def add_arguments(self, parser):
        parser.add_argument('url', nargs='?', default='',
                            help='Adresse de départ : une page de gamme ou '
                                 'de catégorie. Inutile avec --urls.')
        parser.add_argument(
            '--urls', default='',
            help='Fichier d\'adresses de fiches, une par ligne (les lignes '
                 'vides et celles commençant par # sont ignorées). Seule '
                 'voie pour Soprema, dont la liste de produits est '
                 'construite par le navigateur et dont /sitemap.xml renvoie '
                 'une image.')
        parser.add_argument('--entreprise', default='',
                            help='Slug de l\'entreprise. Inutile avec '
                                 '--csv, qui n\'ecrit pas en base.')
        parser.add_argument(
            '--csv', default='',
            help='Ecrit les articles trouves dans ce fichier CSV au lieu de '
                 'la base. Aucune connexion a la base n\'est alors '
                 'necessaire : le fichier se depose ensuite sur la source de '
                 'catalogue du serveur, ce qui evite de faire tourner '
                 'l\'exploration sur la VM pendant des heures.')
        parser.add_argument('--nature', default='material',
                            choices=['material', 'supply', 'action'],
                            help='Nature des articles créés.')
        parser.add_argument('--pages', type=int, default=50,
                            help='Pages à visiter au maximum pour cette '
                                 'exécution (défaut : 50).')
        parser.add_argument('--produits', type=int, default=500,
                            help='Produits à retenir au maximum (défaut : '
                                 '500).')
        parser.add_argument('--delai', type=float, default=1.0,
                            help='Secondes entre deux requêtes (défaut : 1). '
                                 'Le réduire expose à un blocage.')
        parser.add_argument(
            '--mode', default='auto', choices=['auto', 'sitemap', 'liens'],
            help='auto (defaut) : le sitemap du site s il en declare un, '
                 'sinon le parcours par liens. Le sitemap est preferable -- '
                 'il enumere les fiches directement au lieu de ramper dans '
                 'la navigation.')
        parser.add_argument('--etat', default='',
                            help='Fichier d\'état pour la reprise. Par '
                                 'défaut, dérivé de l\'adresse.')
        parser.add_argument('--ecrire', action='store_true',
                            help='Écrit réellement. Sans ce drapeau, essai '
                                 'à blanc.')

    def handle(self, *args, **options):
        from apps.core.models import Company
        from apps.purchases.models import Supplier

        from ...catalogue_crawl import (
            ExplorationError, explorer, explorer_liste, explorer_sitemap,
            importer_candidats, site_de,
        )

        # Le mode CSV ne touche pas la base : il sert précisément quand la
        # base n'est pas joignable, ou quand on veut faire tourner
        # l'exploration ailleurs que sur le serveur de production.
        vers_csv = options['csv']
        company = None
        if not vers_csv:
            if not options['entreprise']:
                raise CommandError('--entreprise est requis, sauf avec --csv.')
            company = Company.objects.filter(
                slug=options['entreprise']).first()
            if company is None:
                raise CommandError(
                    f'Aucune entreprise de slug « {options["entreprise"]} ».')

        # ── Mode liste d'adresses ────────────────────────────────────────
        adresses = []
        if options['urls']:
            if not os.path.isfile(options['urls']):
                raise CommandError(
                    f'Fichier d\'adresses introuvable : {options["urls"]}')
            with open(options['urls'], encoding='utf-8-sig') as flux:
                adresses = [ligne.strip() for ligne in flux
                            if ligne.strip() and not ligne.startswith('#')]
            if not adresses:
                raise CommandError(
                    f'{options["urls"]} ne contient aucune adresse.')
        elif not options['url']:
            raise CommandError(
                'Donnez une adresse de départ, ou --urls <fichier>.')

        # Le site est determine sur la premiere adresse : une liste peut en
        # melanger plusieurs, et chaque adresse est reclassee a la volee.
        reference = options['url'] or adresses[0]
        try:
            configuration = site_de(reference)
        except ExplorationError as exc:
            # Le refus nomme la cause : « Schneider ne sert pas ses fiches
            # en HTML » est actionnable, « échec » ne l'est pas.
            raise CommandError(str(exc))

        chemin_etat = options['etat'] or self._chemin_etat(reference)
        deja_vues = self._lire_etat(chemin_etat)

        a_blanc = not options['ecrire']
        self.stdout.write(
            f'site     : {configuration["nom"]}\n'
            f'départ   : {reference}'
            + (f' ({len(adresses)} adresse(s) fournies)' if adresses else '')
            + '\n'
            f'état     : {chemin_etat} ({len(deja_vues)} page(s) déjà vue(s))\n'
            f'bornes   : {options["pages"]} page(s), {options["produits"]} '
            f'produit(s), {options["delai"]} s entre requêtes\n'
            + ('mode     : ESSAI À BLANC (rien ne sera écrit)\n' if a_blanc
               else 'mode     : ÉCRITURE RÉELLE\n'))

        vus = [0]

        def journal(url, genre, detail):
            vus[0] += 1
            etiquette = {'produit': '+', 'liste': '·', 'echec': '!'}.get(
                genre, ' ')
            self.stdout.write(f'  {etiquette} [{vus[0]:>4}] {detail[:70]}')

        # Le sitemap est prefere des que le site en declare un : ramper
        # dans la navigation ne marche pas, mesure faite -- chaque page
        # porte le menu complet, et un parcours parti de la gamme Celiane
        # se retrouvait quatorze pages plus loin dans les tableaux
        # electriques sans avoir vu une seule fiche.
        mode = options['mode']
        par_liste = bool(adresses)
        par_sitemap = (not par_liste
                       and (mode == 'sitemap'
                            or (mode == 'auto'
                                and configuration.get('sitemap'))))
        self.stdout.write(
            'parcours : '
            + ('liste fournie' if par_liste
               else 'sitemap' if par_sitemap else 'liens de page'))

        try:
            if par_liste:
                candidats, visitees, message = explorer_liste(
                    adresses, pages_max=options['pages'],
                    produits_max=options['produits'], delai=options['delai'],
                    deja_vues=deja_vues, journal=journal)
            else:
                parcours = explorer_sitemap if par_sitemap else explorer
                candidats, visitees, message = parcours(
                    options['url'], pages_max=options['pages'],
                    produits_max=options['produits'], delai=options['delai'],
                    deja_vues=deja_vues, journal=journal)
        except ExplorationError as exc:
            raise CommandError(str(exc))

        self.stdout.write('')
        self.stdout.write(message)

        if not candidats:
            self.stdout.write(self.style.WARNING(
                'Aucun produit trouvé. Si des pages ont été visitées, '
                'l\'adresse de départ n\'est probablement pas une page de '
                'gamme, ou le motif des liens produit ne correspond pas à '
                'cette partie du site.'))
            self._ecrire_etat(chemin_etat, visitees)
            return

        # Les prix sans TVA et les prix TTC ne se mélangent pas dans un
        # même compte-rendu : le dire évite de lire 428 € et 20,96 € comme
        # deux chiffres comparables.
        ttc = [c for c in candidats if c.get('prix') and c.get('prix_ht') is False]
        ht = [c for c in candidats if c.get('prix') and c.get('prix_ht') is True]
        sans = [c for c in candidats if not c.get('prix')]
        self.stdout.write(
            f'  prix HT recommandés : {len(ht)}\n'
            f'  prix TTC conseillés : {len(ttc)}\n'
            f'  sans prix publié    : {len(sans)}')
        # Message corrigé : il disait « le prix d'achat reste vide », ce qui
        # ne correspond plus au code — le prix VA dans purchase_price, coché
        # « prix indicatif, à confirmer ». Un message qui contredit le code
        # est pire que pas de message.
        self.stdout.write(self.style.WARNING(
            '  Les prix vont dans le prix d\'achat, cochés « indicatif, à '
            'confirmer ». Ce sont des prix publics, pas vos prix remisés : '
            'décochez la case quand vous aurez le tarif négocié.'))
        if ttc:
            self.stdout.write(self.style.WARNING(
                f'  Les {len(ttc)} prix TTC sont ramenés en HT à 20 %, le '
                f'champ étant du HT.'))

        if vers_csv:
            # Les colonnes portent les intitulés que la source de catalogue
            # attend : le fichier se dépose sans avoir à redéfinir la
            # correspondance.
            lignes = self._ecrire_csv(vers_csv, candidats, configuration)
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS(
                f'{lignes} ligne(s) écrite(s) dans {vers_csv}'))
            self._ecrire_etat(chemin_etat, visitees)
            self.stdout.write(
                f'État enregistré : {len(visitees)} page(s) vue(s). '
                f'Relancez pour continuer — le CSV est réécrit à chaque fois, '
                f'donnez-lui un nom différent par lot.')
            return

        fournisseur = Supplier.objects.filter(
            company=company, name__iexact=configuration['nom']).first()
        if fournisseur is None:
            self.stdout.write(self.style.WARNING(
                f'  Aucun fournisseur « {configuration["nom"]} » : les '
                f'articles seront créés sans fournisseur. Lancez '
                f'creer_sources_fabricants pour le créer.'))

        compteurs = importer_candidats(
            company, candidats, supplier=fournisseur,
            nature=options['nature'], a_blanc=a_blanc)

        self.stdout.write('')
        verbes = (('à créer', 'à modifier') if a_blanc
                  else ('créés', 'modifiés'))
        self.stdout.write(f'  {verbes[0]:<12} : {compteurs["crees"]}')
        self.stdout.write(f'  {verbes[1]:<12} : {compteurs["mis_a_jour"]}')
        self.stdout.write(f'  inchangés    : {compteurs["inchanges"]}')
        if compteurs['ignores']:
            self.stdout.write(self.style.WARNING(
                f'  ignorés      : {compteurs["ignores"]}'))

        # L'état n'est enregistré QU'APRÈS l'import : une exécution
        # interrompue au milieu doit pouvoir être rejouée entièrement, pas
        # sauter les pages dont les produits n'ont pas été écrits.
        self._ecrire_etat(chemin_etat, visitees)
        self.stdout.write('')
        self.stdout.write(f'État enregistré : {len(visitees)} page(s) vue(s).')

        if a_blanc:
            self.stdout.write(
                'Essai à blanc : rien n\'a été écrit. Relancez avec '
                '--ecrire quand la sortie vous paraît juste.')

    # ── L'export CSV ─────────────────────────────────────────────────────────

    @staticmethod
    def _ecrire_csv(chemin, candidats, configuration):
        """Écrit les candidats dans un CSV déposable tel quel.

        Le prix TTC est ramené en HT ici par la MÊME fonction que l'import
        direct : deux conversions auraient divergé, et le CSV n'aurait pas
        donné le même prix que la voie base.

        En utf-8-sig, parce qu'Excel ouvre un CSV utf-8 sans BOM en
        latin-1 et affiche « DÃ©signation ».
        """
        import csv

        from ...catalogue_crawl import _en_ht

        with open(chemin, 'w', encoding='utf-8-sig', newline='') as flux:
            plume = csv.writer(flux, delimiter=';')
            plume.writerow(['Reference', 'Designation', 'Prix HT',
                            'Prix indicatif', 'EAN', 'Source', 'Fabricant'])
            ecrites = 0
            for candidat in candidats:
                nom = (candidat.get('nom') or '').strip()
                if not nom:
                    continue
                prix = _en_ht(candidat.get('prix'), candidat.get('prix_ht'))
                plume.writerow([
                    candidat.get('reference') or '',
                    nom,
                    '' if prix is None else f'{prix}',
                    'oui' if prix is not None else 'non',
                    candidat.get('ean') or '',
                    candidat.get('url') or '',
                    configuration['nom'],
                ])
                ecrites += 1
        return ecrites

    # ── L'état de reprise ────────────────────────────────────────────────────

    @staticmethod
    def _chemin_etat(url):
        from urllib.parse import urlparse

        from django.conf import settings

        morceaux = urlparse(url)
        nom = (morceaux.hostname or 'site').replace('.', '_')
        dossier = os.path.join(str(settings.BASE_DIR), 'var',
                               'exploration_catalogue')
        os.makedirs(dossier, exist_ok=True)
        return os.path.join(dossier, f'{nom}.json')

    def _lire_etat(self, chemin):
        if not os.path.isfile(chemin):
            return []
        try:
            with open(chemin, encoding='utf-8') as flux:
                donnees = json.load(flux)
            return list(donnees.get('visitees', []))
        except Exception:
            # Un état illisible ne doit pas empêcher d'explorer : on
            # repart de zéro en le disant.
            self.stdout.write(self.style.WARNING(
                f'État illisible ({chemin}) : reprise depuis le début.'))
            return []

    @staticmethod
    def _ecrire_etat(chemin, visitees):
        with open(chemin, 'w', encoding='utf-8') as flux:
            json.dump({'visitees': sorted(visitees)}, flux, indent=1)
