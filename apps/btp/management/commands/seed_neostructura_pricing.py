"""
manage.py seed_neostructura_pricing
Peuple ElectricityPriceLibrary pour NÉOSTRUCTURA (multi-métiers : électricité,
domotique, étanchéité, informatique, rénovation, maintenance), nécessaire au
configurateur du site public. Idempotent (get_or_create par company+code).
"""
from django.core.management.base import BaseCommand, CommandError


PRICE_ITEMS = [
    # code, name, category, unit, price_min, price_avg, price_max, duration_hours, complexity
    ('DEPL', 'Frais de déplacement', 'deplacement', 'forfait', 0, 0, 45, 0, 'simple'),
    ('DIAG', 'Diagnostic technique', 'diagnostic', 'forfait', 45, 60, 85, 1, 'simple'),
    ('URG', 'Majoration urgence', 'forfait', 'forfait', 60, 90, 130, 0, 'simple'),
    ('MO', "Main-d'œuvre horaire", 'main_oeuvre', 'h', 45, 55, 70, 1, 'medium'),

    # Électricité
    ('ELEC-INST', 'Installation électrique par pièce', 'installation', 'u', 320, 420, 550, 4, 'medium'),
    ('ELEC-TAB', 'Remplacement tableau électrique', 'tableau', 'forfait', 850, 1100, 1400, 6, 'complex'),
    ('ELEC-PRISE', 'Prise / interrupteur', 'prise_interrupteur', 'u', 55, 65, 80, 1, 'simple'),
    ('ELEC-LUM', 'Point lumineux / éclairage', 'eclairage', 'u', 65, 78, 95, 1, 'simple'),
    ('ELEC-NORM', 'Mise aux normes NF C 15-100', 'mise_normes', 'forfait', 600, 900, 1300, 8, 'complex'),

    # Domotique
    ('DOM-MOD', 'Module domotique (éclairage/volets/chauffage)', 'domotique', 'u', 180, 240, 320, 2, 'medium'),
    ('DOM-SEC', 'Point sécurité connecté (alarme/caméra)', 'alarme', 'u', 150, 210, 280, 2, 'medium'),
    ('DOM-HUB', 'Box domotique / passerelle centrale', 'domotique', 'forfait', 120, 180, 250, 1, 'simple'),

    # Informatique & réseaux
    ('IT-RES', 'Prise RJ45 / point réseau', 'reseau', 'u', 70, 88, 110, 1, 'simple'),
    ('IT-WIFI', 'Installation Wi-Fi / borne', 'reseau', 'u', 120, 160, 220, 2, 'medium'),
    ('IT-BAIE', 'Baie informatique / armoire réseau', 'reseau', 'forfait', 280, 420, 650, 4, 'complex'),
    ('IT-CAM', 'Caméra IP de surveillance', 'alarme', 'u', 95, 130, 180, 1, 'simple'),

    # Étanchéité / rénovation / maintenance — pas de catégorie dédiée, on
    # utilise 'renovation' (m²) et 'forfait' comme approximation en attendant
    # une extension du modèle de prix propre au BTP multi-métiers.
    ('ETAN-TOIT', 'Étanchéité toiture-terrasse', 'renovation', 'm2', 45, 65, 90, 0.5, 'complex'),
    ('ETAN-REPAR', 'Réparation ponctuelle de fuite', 'renovation', 'forfait', 180, 280, 420, 3, 'medium'),
    ('ETAN-ISOL', 'Isolation complémentaire', 'renovation', 'm2', 25, 38, 55, 0.3, 'medium'),
    ('RENO-COMPL', 'Rénovation multi-corps de métier', 'renovation', 'm2', 75, 95, 130, 1, 'complex'),
    ('RENO-SDB', 'Rénovation salle de bain (forfait)', 'renovation', 'forfait', 2800, 4200, 6500, 40, 'complex'),
    ('RENO-CUISINE', 'Rénovation cuisine (forfait)', 'renovation', 'forfait', 3200, 4800, 7500, 48, 'complex'),
    ('MAINT-CONTRAT', 'Contrat de maintenance annuel', 'forfait', 'forfait', 39, 59, 89, 0, 'simple'),
    ('MAINT-PONCT', 'Intervention ponctuelle hors contrat', 'depannage', 'forfait', 65, 95, 140, 1.5, 'simple'),
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

        created, updated = 0, 0
        for code, name, category, unit, pmin, pavg, pmax, duration, complexity in PRICE_ITEMS:
            obj, was_created = ElectricityPriceLibrary.objects.update_or_create(
                company=company, code=code,
                defaults=dict(
                    name=name, category=category, unit=unit,
                    price_min=pmin, price_avg=pavg, price_max=pmax,
                    duration_hours=duration, complexity=complexity, is_active=True,
                ),
            )
            created += was_created
            updated += not was_created

        self.stdout.write(self.style.SUCCESS(
            f'{created} tarif(s) créé(s), {updated} mis à jour pour {company.name}.'
        ))
