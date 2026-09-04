"""
manage.py seed_neostructura_pricing
Peuple ElectricityPriceLibrary pour NÉOSTRUCTURA (multi-métiers : électricité,
domotique, étanchéité, informatique, rénovation, maintenance), nécessaire au
configurateur du site public. Idempotent (get_or_create par company+code).

Chaque poste est tagué `metier` pour apparaître dans l'étape "Matériel" du
configurateur public — voir apps/btp/public_configurator_api.py. Plusieurs
postes peuvent partager le même `product_family` pour représenter plusieurs
gammes (standard/premium/luxe) d'un même équipement : le visiteur choisit
alors le produit précis, avec son vrai prix, au lieu d'une majoration
forfaitaire. Ce fichier ne sert qu'à amorcer le catalogue — toute la
gestion courante (ajout de nouveaux produits/gammes) se fait ensuite depuis
l'ERP : Bâtiment > Bibliothèque de prix.
"""
from django.core.management.base import BaseCommand, CommandError


# Postes internes (non liés à un métier — ne s'affichent pas comme "matériel"
# dans le configurateur, utilisés directement par code : déplacement, main-d'œuvre).
INTERNAL_ITEMS = [
    dict(code='DEPL', name='Frais de déplacement', category='deplacement', unit='forfait',
         price_min=0, price_avg=0, price_max=45, duration_hours=0, complexity='simple'),
    dict(code='DIAG', name='Diagnostic technique', category='diagnostic', unit='forfait',
         price_min=45, price_avg=60, price_max=85, duration_hours=1, complexity='simple'),
    dict(code='URG', name='Majoration urgence', category='forfait', unit='forfait',
         price_min=60, price_avg=90, price_max=130, duration_hours=0, complexity='simple'),
    dict(code='MO', name="Main-d'œuvre horaire", category='main_oeuvre', unit='h',
         price_min=45, price_avg=55, price_max=70, duration_hours=1, complexity='medium'),
]

# Matériel / équipements sélectionnables dans le configurateur public, par métier.
MATERIAL_ITEMS = [
    # ── Électricité ──
    dict(code='ELEC-INST', name='Installation électrique par pièce', category='installation', unit='u',
         price_min=320, price_avg=420, price_max=550, duration_hours=4, complexity='medium', metier='electricite'),
    dict(code='ELEC-TAB', name='Remplacement tableau électrique', category='tableau', unit='forfait',
         price_min=850, price_avg=1100, price_max=1400, duration_hours=6, complexity='complex', metier='electricite'),
    # Exemple de famille multi-gammes : 3 vrais produits pour un même besoin.
    dict(code='ELEC-PRISE-STD', name='Prise / interrupteur — gamme standard', category='prise_interrupteur', unit='u',
         price_min=55, price_avg=65, price_max=80, duration_hours=1, complexity='simple', metier='electricite',
         product_family='Prise / interrupteur', quality_level='standard', brand='Legrand', reference='Mosaic'),
    dict(code='ELEC-PRISE-PREM', name='Prise / interrupteur — gamme premium', category='prise_interrupteur', unit='u',
         price_min=85, price_avg=105, price_max=130, duration_hours=1, complexity='simple', metier='electricite',
         product_family='Prise / interrupteur', quality_level='premium', brand='Schneider Electric', reference='Odace'),
    dict(code='ELEC-PRISE-LUXE', name='Prise / interrupteur — gamme luxe', category='prise_interrupteur', unit='u',
         price_min=140, price_avg=175, price_max=220, duration_hours=1, complexity='simple', metier='electricite',
         product_family='Prise / interrupteur', quality_level='luxe', brand='Arnould', reference='Sixties'),
    dict(code='ELEC-LUM', name='Point lumineux / éclairage', category='eclairage', unit='u',
         price_min=65, price_avg=78, price_max=95, duration_hours=1, complexity='simple', metier='electricite'),
    dict(code='ELEC-NORM', name='Mise aux normes NF C 15-100', category='mise_normes', unit='forfait',
         price_min=600, price_avg=900, price_max=1300, duration_hours=8, complexity='complex', metier='electricite'),

    # ── Domotique ──
    dict(code='DOM-MOD', name='Module domotique (éclairage/volets/chauffage)', category='domotique', unit='u',
         price_min=180, price_avg=240, price_max=320, duration_hours=2, complexity='medium', metier='domotique'),
    dict(code='DOM-SEC', name='Point sécurité connecté (alarme/caméra)', category='alarme', unit='u',
         price_min=150, price_avg=210, price_max=280, duration_hours=2, complexity='medium', metier='domotique'),
    dict(code='DOM-HUB', name='Box domotique / passerelle centrale', category='domotique', unit='forfait',
         price_min=120, price_avg=180, price_max=250, duration_hours=1, complexity='simple', metier='domotique'),

    # ── Informatique & réseaux ──
    dict(code='IT-RES', name='Prise RJ45 / point réseau', category='reseau', unit='u',
         price_min=70, price_avg=88, price_max=110, duration_hours=1, complexity='simple', metier='informatique'),
    dict(code='IT-WIFI', name='Installation Wi-Fi / borne', category='reseau', unit='u',
         price_min=120, price_avg=160, price_max=220, duration_hours=2, complexity='medium', metier='informatique'),
    dict(code='IT-BAIE', name='Baie informatique / armoire réseau', category='reseau', unit='forfait',
         price_min=280, price_avg=420, price_max=650, duration_hours=4, complexity='complex', metier='informatique'),
    dict(code='IT-CAM', name='Caméra IP de surveillance', category='alarme', unit='u',
         price_min=95, price_avg=130, price_max=180, duration_hours=1, complexity='simple', metier='informatique'),

    # ── Étanchéité / rénovation / maintenance — pas de catégorie ElectricityPriceLibrary
    # dédiée, on utilise 'renovation' (m²) et 'forfait' comme approximation. ──
    dict(code='ETAN-TOIT', name='Étanchéité toiture-terrasse', category='renovation', unit='m2',
         price_min=45, price_avg=65, price_max=90, duration_hours=0.5, complexity='complex', metier='etancheite'),
    dict(code='ETAN-REPAR', name='Réparation ponctuelle de fuite', category='renovation', unit='forfait',
         price_min=180, price_avg=280, price_max=420, duration_hours=3, complexity='medium', metier='etancheite'),
    dict(code='ETAN-ISOL', name='Isolation complémentaire', category='renovation', unit='m2',
         price_min=25, price_avg=38, price_max=55, duration_hours=0.3, complexity='medium', metier='etancheite'),
    dict(code='RENO-COMPL', name='Rénovation multi-corps de métier', category='renovation', unit='m2',
         price_min=75, price_avg=95, price_max=130, duration_hours=1, complexity='complex', metier='renovation'),
    dict(code='RENO-SDB', name='Rénovation salle de bain (forfait)', category='renovation', unit='forfait',
         price_min=2800, price_avg=4200, price_max=6500, duration_hours=40, complexity='complex', metier='renovation'),
    dict(code='RENO-CUISINE', name='Rénovation cuisine (forfait)', category='renovation', unit='forfait',
         price_min=3200, price_avg=4800, price_max=7500, duration_hours=48, complexity='complex', metier='renovation'),
    dict(code='MAINT-CONTRAT', name='Contrat de maintenance annuel', category='forfait', unit='forfait',
         price_min=39, price_avg=59, price_max=89, duration_hours=0, complexity='simple', metier='maintenance'),
    dict(code='MAINT-PONCT', name='Intervention ponctuelle hors contrat', category='depannage', unit='forfait',
         price_min=65, price_avg=95, price_max=140, duration_hours=1.5, complexity='simple', metier='maintenance'),
]


class Command(BaseCommand):
    help = "Peuple la bibliothèque de prix NÉOSTRUCTURA (configurateur du site public)."

    def handle(self, *args, **options):
        from apps.core.models import Company
        from apps.btp.models import ElectricityPriceLibrary

        try:
            company = Company.objects.get(slug='neostructura')
        except Company.DoesNotExist:
            raise CommandError("Entreprise 'neostructura' introuvable (slug attendu: neostructura).")

        # 'ELEC-PRISE' a été scindé en 3 gammes (ELEC-PRISE-STD/PREM/LUXE) —
        # supprime l'ancien poste orphelin s'il existe encore.
        ElectricityPriceLibrary.objects.filter(company=company, code='ELEC-PRISE').delete()

        created, updated = 0, 0
        for item in INTERNAL_ITEMS + MATERIAL_ITEMS:
            code = item.pop('code')
            item.setdefault('is_active', True)
            obj, was_created = ElectricityPriceLibrary.objects.update_or_create(
                company=company, code=code, defaults=item,
            )
            created += was_created
            updated += not was_created

        self.stdout.write(self.style.SUCCESS(
            f'{created} tarif(s) créé(s), {updated} mis à jour pour {company.name}.'
        ))
