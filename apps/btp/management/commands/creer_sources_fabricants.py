"""
Prépare les sources de catalogue des grands fabricants.

Crée le fournisseur et la source d'import pour Schneider Electric, Legrand,
Hager et Soprema, de façon à ce qu'il n'y ait plus qu'à **déposer le
fichier** de tarif téléchargé depuis le portail de chacun.

**Aucune référence et aucun prix ne sont créés par cette commande.** C'est
délibéré, et c'est le seul choix tenable : ces tarifs sont réservés aux
clients professionnels, derrière un portail protégé par identifiants. Les
fabriquer donnerait des références plausibles et des prix inventés, qui
partiraient dans des devis chez des clients. Une référence absente se
remarque ; une référence fausse se facture.

Les correspondances de colonnes ci-dessous sont des **hypothèses de
départ**, fondées sur les intitulés courants des tarifs français. Elles
seront presque certainement à ajuster : chaque fabricant nomme ses colonnes
à sa façon, et change ces intitulés d'une année sur l'autre. L'essai à
blanc est là pour ça — il lit le fichier et dit ce qu'il a compris sans
rien écrire.
"""

from django.core.management.base import BaseCommand, CommandError

# Les CLÉS de ces dictionnaires sont les champs de l'ERP et ne sont pas
# libres : nom, reference, prix_achat, prix_vente, nature, categorie, unite,
# reference_fournisseur, description. Une clé inconnue est silencieusement
# ignorée — l'import lit alors les lignes et n'en tire aucun article, sans
# message d'erreur. Défaut commis ici (« designation » au lieu de « nom »),
# attrapé par un test.
#
# Les VALEURS, elles, sont les intitulés de colonnes du fichier, et ce sont
# eux qui varient d'un fabricant à l'autre.
#
# Hypothèses d'intitulés, par fabricant. Volontairement courtes : mieux
# vaut deux colonnes justes et le reste à compléter qu'une correspondance
# complète et fausse, qui importerait des prix dans le mauvais champ.
FABRICANTS = [
    {
        'nom': 'Schneider Electric',
        'slug': 'schneider',
        'format': 'excel',
        'nature': 'material',
        'colonnes': {
            'reference': 'Référence',
            'nom': 'Désignation',
            'prix_achat': 'Prix public HT',
            'unite': 'Unité',
            'categorie': 'Famille',
        },
        'note': 'Tarif téléchargeable depuis le portail distributeur '
                'Schneider (eShop / mySchneider). Plus de 100 000 '
                'références : utilisez importer_fichier_catalogue sur le '
                'serveur plutôt que le dépôt par navigateur.',
    },
    {
        'nom': 'Legrand',
        'slug': 'legrand',
        'format': 'excel',
        'nature': 'material',
        'colonnes': {
            'reference': 'Référence',
            'nom': 'Désignation',
            'prix_achat': 'Tarif HT',
            'unite': 'Unité',
            'categorie': 'Gamme',
        },
        'note': 'Tarif téléchargeable depuis l’espace professionnel '
                'Legrand.',
    },
    {
        'nom': 'Hager',
        'slug': 'hager',
        'format': 'excel',
        'nature': 'material',
        'colonnes': {
            'reference': 'Référence',
            'nom': 'Désignation',
            'prix_achat': 'Prix tarif HT',
            'unite': 'Unité',
            'categorie': 'Famille',
        },
        'note': 'Tarif téléchargeable depuis Hager Ready / l’espace pro.',
    },
    {
        'nom': 'Soprema',
        'slug': 'soprema',
        'format': 'excel',
        # Étanchéité : des rouleaux, des plaques, des primaires. Ce sont des
        # FOURNITURES consommées sur le chantier, pas du matériel installé
        # une fois — d'où une nature par défaut différente des trois autres.
        'nature': 'supply',
        'colonnes': {
            'reference': 'Code article',
            'nom': 'Désignation',
            'prix_achat': 'Prix HT',
            'unite': 'Unité',
            'categorie': 'Gamme',
        },
        'note': 'Tarif étanchéité, téléchargeable depuis l’espace '
                'professionnel Soprema.',
    },
]


class Command(BaseCommand):
    help = ('Crée les sources de catalogue Schneider, Legrand, Hager et '
            'Soprema pour une entreprise, sans importer aucun article.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--entreprise', required=True,
            help='Slug de l’entreprise (ex. : neostructura).')
        parser.add_argument(
            '--seulement', default='',
            help='Limiter à certains fabricants, séparés par des virgules '
                 '(schneider, legrand, hager, soprema).')

    def handle(self, *args, **options):
        from apps.core.models import Company
        from apps.purchases.models import Supplier

        from ...models import CatalogueSource

        slug = options['entreprise']
        company = Company.objects.filter(slug=slug).first()
        if company is None:
            connus = ', '.join(
                Company.objects.values_list('slug', flat=True)[:20]) or 'aucune'
            raise CommandError(
                f'Aucune entreprise de slug « {slug} ». Connues : {connus}')

        filtre = {part.strip().lower()
                  for part in options['seulement'].split(',') if part.strip()}

        crees, existants = 0, 0
        for fabricant in FABRICANTS:
            if filtre and fabricant['slug'] not in filtre:
                continue

            fournisseur, _ = Supplier.objects.get_or_create(
                company=company, name=fabricant['nom'],
                defaults={'supplier_type': 'company', 'is_active': True})

            source, cree = CatalogueSource.objects.get_or_create(
                company=company, name=f'Tarif {fabricant["nom"]}',
                defaults={
                    # Pas d'URL : le tarif n'a pas d'adresse publique.
                    'url': '',
                    'format': fabricant['format'],
                    'colonnes': fabricant['colonnes'],
                    'nature_par_defaut': fabricant['nature'],
                    'supplier': fournisseur,
                    'is_active': True,
                    # Pas de synchronisation automatique : il n'y a rien à
                    # aller chercher. Une source à zéro ne se déclenche pas.
                    'intervalle_minutes': 0,
                })
            if cree:
                crees += 1
                self.stdout.write(self.style.SUCCESS(
                    f'  créé   {source.name} (nature par défaut : '
                    f'{fabricant["nature"]})'))
                self.stdout.write(f'         {fabricant["note"]}')
            else:
                existants += 1
                self.stdout.write(f'  existe {source.name}')

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'{crees} source(s) créée(s), {existants} déjà présente(s) — '
            f'aucun article importé.'))
        self.stdout.write('')
        self.stdout.write(
            'Prochaine étape, pour chaque fabricant :\n'
            '  1. télécharger son tarif depuis son portail professionnel ;\n'
            '  2. ouvrir la fiche de la source dans l\'ERP et déposer le '
            'fichier en ESSAI À BLANC ;\n'
            '  3. comparer ce qu\'il a compris aux intitulés réels du '
            'fichier, et corriger la correspondance des colonnes ;\n'
            '  4. relancer sans l\'essai à blanc.\n'
            '\n'
            'Les correspondances posées ici sont des hypothèses : chaque '
            'fabricant nomme ses colonnes à sa façon, et change ces '
            'intitulés d\'une année sur l\'autre.')
