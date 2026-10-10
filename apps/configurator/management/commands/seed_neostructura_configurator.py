"""
manage.py seed_neostructura_configurator
Peuple le moteur générique apps.configurator pour NÉOSTRUCTURA : domaines,
prestations, questions conditionnelles, matériel (référencé depuis
ElectricityPriceLibrary — jamais dupliqué), règles de main-d'œuvre / zones
de déplacement / coefficients / marge, scénarios de diagnostic.

Idempotent (update_or_create sur les codes). Toute cette donnée est ensuite
modifiable depuis l'admin Django (/admin/) sans redéploiement.
"""
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError


# ─── Domaines ──────────────────────────────────────────────────────────────────
DOMAINS = [
    dict(code='electricite', name='Électricité', icon='⚡', order=1,
         description="Dépannage, pose, rénovation, mise aux normes, installation neuve."),
    dict(code='informatique-reseaux', name='Informatique & Réseaux', icon='🖥', order=2,
         description="Wi-Fi, RJ45, câblage, baie informatique, dépannage réseau."),
    dict(code='btp-renovation', name='BTP / Rénovation & autres services', icon='🏗', order=3,
         description="Rénovation, étanchéité, domotique, maintenance."),
]

# ─── Prestations (par domaine) ─────────────────────────────────────────────────
# Chaque entrée : code, name, intervention_type, requires_diagnostic,
# confidence_level, durées (min/avg/max h), danger_alert, questions[], materials[],
# diagnostic{} (si requires_diagnostic).
#
# questions[]: identifier, label, type, required, order, options[] (si choix),
#              display_condition {} (si conditionnelle), impacts_*.
# materials[]: price_code (ElectricityPriceLibrary.code), source ('fixed'|'answer'),
#              qty (si fixed) ou answer_identifier (si answer), multiplier.

ELECTRICITE = [
    dict(
        code='depannage-disjoncteur', name='Disjoncteur qui saute',
        intervention_type='depannage', requires_diagnostic=True, confidence_level='diagnostic_required',
        duration=(0.5, 1, 2), width=30, danger_alert=True,
        questions=[
            dict(id='moment', label='Le disjoncteur saute-t-il tout de suite ou après un moment ?', type='single_choice', order=1,
                 options=[('immediat', 'Immédiatement'), ('apres_moment', 'Après un moment'), ('aleatoire', 'De façon aléatoire')]),
            dict(id='danger_signes', label='Fumée, étincelles ou odeur de brûlé ?', type='boolean', order=2, impacts_diagnostic=True),
            dict(id='depuis_quand', label='Depuis quand ce problème survient-il ?', type='text', order=3, required=False),
            dict(id='photo_tableau', label='Photo du tableau électrique (optionnel)', type='photo', order=4, required=False),
        ],
        materials=[],
        diagnostic=dict(
            hypotheses=[
                {'label': 'Court-circuit sur un circuit spécifique', 'likelihood': 'medium'},
                {'label': 'Surcharge électrique', 'likelihood': 'medium'},
                {'label': 'Disjoncteur défectueux', 'likelihood': 'low'},
            ],
            duration=(0.5, 1, 1.5),
            danger_keywords=['fumée', 'étincelle', 'brûlé', 'chaud', 'chaleur'],
        ),
    ),
    dict(
        code='depannage-differentiel', name='Différentiel qui saute',
        intervention_type='depannage', requires_diagnostic=True, confidence_level='diagnostic_required',
        duration=(0.5, 1.5, 2.5), width=30, danger_alert=True,
        questions=[
            dict(id='declenche_quand', label='Le différentiel saute-t-il en permanence ou par intermittence ?', type='single_choice', order=1,
                 options=[('permanent', 'En permanence'), ('intermittent', 'Par intermittence'), ('appareil_precis', "Quand j'utilise un appareil précis")]),
            dict(id='humidite', label="Le déclenchement est-il lié à l'humidité (salle de bain, extérieur, pluie) ?", type='boolean', order=2, impacts_diagnostic=True),
            dict(id='photo_tableau', label='Photo du tableau électrique (optionnel)', type='photo', order=3, required=False),
        ],
        materials=[],
        diagnostic=dict(
            hypotheses=[
                {'label': "Fuite à la terre liée à l'humidité", 'likelihood': 'high'},
                {'label': 'Appareil électroménager défectueux', 'likelihood': 'medium'},
                {'label': 'Différentiel lui-même défectueux', 'likelihood': 'low'},
            ],
            duration=(0.5, 1.5, 2),
            danger_keywords=['fumée', 'étincelle', 'brûlé', 'choc électrique'],
        ),
    ),
    dict(
        code='depannage-panne-generale', name='Plus de courant du tout',
        intervention_type='depannage', requires_diagnostic=True, confidence_level='diagnostic_required',
        duration=(0.5, 1.5, 3), width=35, danger_alert=True,
        questions=[
            dict(id='voisinage', label='Vos voisins sont-ils également touchés ?', type='boolean', order=1),
            dict(id='depuis_quand', label='Depuis quand ?', type='text', order=2, required=False),
        ],
        materials=[],
        diagnostic=dict(
            hypotheses=[
                {'label': 'Coupure générale fournisseur (à vérifier avant intervention)', 'likelihood': 'medium'},
                {'label': 'Disjoncteur général déclenché', 'likelihood': 'medium'},
                {'label': 'Panne sur le tableau principal', 'likelihood': 'low'},
            ],
            duration=(0.5, 1.5, 2.5),
            danger_keywords=['fumée', 'étincelle', 'brûlé', 'odeur'],
        ),
    ),
    dict(
        code='depannage-prise', name='Prise ou interrupteur ne fonctionne plus',
        intervention_type='depannage', requires_diagnostic=False, confidence_level='medium',
        duration=(0.5, 1, 1.5), width=20,
        questions=[
            dict(id='nb_points', label='Combien de prises/interrupteurs sont concernés ?', type='number', order=1, impacts_material=True),
        ],
        materials=[dict(code='ELEC-PRISE-STD', source='answer', answer='nb_points')],
    ),
    dict(
        code='depannage-eclairage', name='Éclairage en panne',
        intervention_type='depannage', requires_diagnostic=False, confidence_level='medium',
        duration=(0.5, 1, 1.5), width=20,
        questions=[
            dict(id='nb_points', label="Combien de points lumineux sont concernés ?", type='number', order=1, impacts_material=True),
        ],
        materials=[dict(code='ELEC-LUM', source='answer', answer='nb_points')],
    ),
    dict(
        code='pose-prises', name='Installation de prises / interrupteurs',
        intervention_type='installation_neuve', requires_diagnostic=False, confidence_level='high',
        duration=(1, 2, 4), width=10,
        questions=[
            dict(id='nb_points', label='Combien de prises/interrupteurs souhaitez-vous installer ?', type='number', order=1, impacts_material=True),
            dict(id='gamme', label='Quelle gamme souhaitez-vous ?', type='single_choice', order=2,
                 options=[('standard', 'Standard'), ('premium', 'Premium'), ('luxe', 'Luxe')]),
        ],
        materials=[dict(code='ELEC-PRISE-STD', source='answer', answer='nb_points')],
    ),
    dict(
        code='pose-eclairage', name='Installation de points lumineux',
        intervention_type='installation_neuve', requires_diagnostic=False, confidence_level='high',
        duration=(1, 2, 4), width=10,
        questions=[
            dict(id='nb_points', label='Combien de points lumineux souhaitez-vous installer ?', type='number', order=1, impacts_material=True),
        ],
        materials=[dict(code='ELEC-LUM', source='answer', answer='nb_points')],
    ),
    dict(
        code='pose-tableau', name='Remplacement du tableau électrique',
        intervention_type='installation_neuve', requires_diagnostic=False, confidence_level='high',
        duration=(4, 6, 8), width=15,
        questions=[
            dict(id='age_tableau', label="Le tableau actuel a-t-il plus de 20 ans ?", type='boolean', order=1, required=False),
        ],
        materials=[dict(code='ELEC-TAB', source='fixed', qty=1)],
    ),
    dict(
        code='renovation-electrique', name='Rénovation électrique',
        intervention_type='renovation', requires_diagnostic=False, confidence_level='low',
        duration=(8, 24, 40), width=25,
        questions=[
            dict(id='surface', label='Surface approximative à rénover (m²)', type='surface', order=1, impacts_material=True),
            dict(id='nb_pieces', label='Nombre de pièces concernées', type='number', order=2),
            dict(id='etat', label="État actuel de l'installation", type='single_choice', order=3,
                 options=[('bon', 'Bon'), ('moyen', 'Moyen'), ('vetuste', 'Vétuste'), ('inconnu', 'Je ne sais pas')]),
        ],
        materials=[dict(code='ELEC-NORM', source='fixed', qty=1)],
    ),
    dict(
        code='mise-normes', name='Mise aux normes NF C 15-100',
        intervention_type='mise_normes', requires_diagnostic=False, confidence_level='medium',
        duration=(6, 8, 12), width=20,
        questions=[
            dict(id='contexte', label='Dans quel cadre ?', type='single_choice', order=1,
                 options=[('vente', 'Vente du bien'), ('diagnostic_defavorable', 'Suite à un diagnostic défavorable'), ('securite', 'Mise en sécurité volontaire')]),
        ],
        materials=[dict(code='ELEC-NORM', source='fixed', qty=1)],
    ),
    dict(
        code='installation-neuve', name='Installation électrique neuve (construction)',
        intervention_type='installation_neuve', requires_diagnostic=False, confidence_level='low',
        duration=(16, 32, 56), width=30,
        questions=[
            dict(id='type_batiment', label='Type de bâtiment', type='single_choice', order=1,
                 options=[('maison', 'Maison'), ('appartement', 'Appartement'), ('local_pro', 'Local professionnel')]),
            dict(id='surface', label='Surface (m²)', type='surface', order=2, impacts_material=True),
            dict(id='gamme', label="Niveau d'équipement souhaité", type='single_choice', order=3,
                 options=[('standard', 'Standard'), ('premium', 'Premium'), ('luxe', 'Luxe')]),
        ],
        materials=[dict(code='ELEC-INST', source='answer', answer='surface', multiplier='0.3')],
    ),
]

INFORMATIQUE = [
    dict(
        code='wifi-faible', name='Wi-Fi faible ou zones mortes',
        intervention_type='depannage', requires_diagnostic=True, confidence_level='diagnostic_required',
        duration=(1, 2, 3), width=30,
        questions=[
            dict(id='type_logement', label='Type de logement', type='single_choice', order=1,
                 options=[('maison', 'Maison'), ('appartement', 'Appartement'), ('local_pro', 'Local professionnel')]),
            dict(id='surface', label='Surface approximative (m²)', type='surface', order=2),
            dict(id='nb_etages', label="Nombre d'étages", type='number', order=3),
            dict(id='nb_pieces', label='Nombre de pièces', type='number', order=4),
            dict(id='emplacement_box', label='Où se trouve la box actuellement ?', type='single_choice', order=5,
                 options=[('rdc', 'Rez-de-chaussée'), ('etage', 'Étage'), ('sous_sol', 'Sous-sol / local technique')]),
            dict(id='zone_probleme', label='Le problème touche-t-il tout le logement ou certaines zones ?', type='single_choice', order=6,
                 options=[('partout', 'Partout'), ('certaines_zones', 'Certaines zones seulement')]),
            dict(id='nb_zones_mortes', label='Combien de zones sont concernées ?', type='number', order=7,
                 required=False, impacts_material=True,
                 display_condition={'question': 'zone_probleme', 'equals': 'certaines_zones'}),
            dict(id='debit_constate', label='Débit constaté si vous le connaissez (optionnel)', type='text', order=8, required=False),
            dict(id='nb_appareils', label="Nombre approximatif d'appareils connectés", type='number', order=9, required=False),
            dict(id='photo_box', label='Photo de la box / du logement (optionnel)', type='photo', order=10, required=False),
        ],
        materials=[dict(code='IT-WIFI', source='answer', answer='nb_zones_mortes')],
        diagnostic=dict(
            hypotheses=[
                {'label': 'Box mal placée (centrale, hauteur, obstacles proches)', 'likelihood': 'high'},
                {'label': 'Matériaux épais faisant écran (béton, métal)', 'likelihood': 'medium'},
                {'label': "Débit insuffisant côté opérateur", 'likelihood': 'low'},
            ],
            duration=(0.5, 1, 1.5),
        ),
    ),
    dict(
        code='rj45-creation', name='Création de prises RJ45',
        intervention_type='installation_neuve', requires_diagnostic=False, confidence_level='medium',
        duration=(1, 2, 4), width=15,
        questions=[
            dict(id='nb_prises', label='Combien de prises RJ45 souhaitez-vous ?', type='number', order=1, impacts_material=True),
            dict(id='type_batiment', label='Type de bâtiment', type='single_choice', order=2,
                 options=[('maison', 'Maison'), ('appartement', 'Appartement'), ('local_pro', 'Local professionnel')]),
            dict(id='distance', label='Distance approximative entre la baie et le point le plus éloigné', type='distance', order=3, required=False),
            dict(id='cablage_existant', label='Un câblage réseau existe-t-il déjà ?', type='boolean', order=4),
            dict(id='contexte', label="Rénovation ou construction neuve ?", type='single_choice', order=5,
                 options=[('renovation', 'Rénovation'), ('neuf', 'Neuf')]),
        ],
        materials=[dict(code='IT-RES', source='answer', answer='nb_prises')],
    ),
    dict(
        code='baie-informatique', name='Baie informatique / armoire réseau',
        intervention_type='installation_neuve', requires_diagnostic=False, confidence_level='medium',
        duration=(3, 4, 6), width=15,
        questions=[
            dict(id='nb_equipements', label="Nombre approximatif d'équipements à installer (switch, routeur...)", type='number', order=1, required=False),
        ],
        materials=[dict(code='IT-BAIE', source='fixed', qty=1)],
    ),
    dict(
        code='depannage-reseau', name='Dépannage réseau (switch, routeur, câblage)',
        intervention_type='depannage', requires_diagnostic=True, confidence_level='diagnostic_required',
        duration=(1, 2, 3), width=30,
        questions=[
            dict(id='symptome', label='Que constatez-vous ?', type='single_choice', order=1,
                 options=[('aucune_connexion', 'Aucune connexion'), ('connexion_intermittente', 'Connexion intermittente'), ('lenteur', 'Lenteur importante'), ('poste_isole', "Un seul poste ne fonctionne plus")]),
            dict(id='equipements_concernes', label='Quels équipements sont concernés ?', type='multi_choice', order=2,
                 options=[('switch', 'Switch'), ('routeur', 'Routeur'), ('cablage', 'Câblage'), ('baie', 'Baie informatique')]),
        ],
        materials=[],
        diagnostic=dict(
            hypotheses=[
                {'label': 'Équipement réseau défectueux (switch/routeur)', 'likelihood': 'medium'},
                {'label': 'Câble ou prise RJ45 endommagé', 'likelihood': 'medium'},
                {'label': 'Configuration réseau à revoir', 'likelihood': 'low'},
            ],
            duration=(0.5, 1.5, 2),
        ),
    ),
]

BTP_RENOVATION = [
    dict(code='reno-multi-corps', name='Rénovation multi-corps de métier', intervention_type='renovation',
         confidence_level='low', duration=(16, 32, 60), width=25,
         questions=[dict(id='surface', label='Surface à rénover (m²)', type='surface', order=1, impacts_material=True)],
         materials=[dict(code='RENO-COMPL', source='answer', answer='surface')]),
    dict(code='reno-sdb', name='Rénovation salle de bain', intervention_type='renovation',
         confidence_level='medium', duration=(24, 40, 56), width=20,
         questions=[], materials=[dict(code='RENO-SDB', source='fixed', qty=1)]),
    dict(code='reno-cuisine', name='Rénovation cuisine', intervention_type='renovation',
         confidence_level='medium', duration=(28, 48, 64), width=20,
         questions=[], materials=[dict(code='RENO-CUISINE', source='fixed', qty=1)]),
    dict(code='etancheite-toiture', name='Étanchéité toiture-terrasse', intervention_type='renovation',
         confidence_level='medium', duration=(4, 8, 16), width=20,
         questions=[dict(id='surface', label='Surface de toiture (m²)', type='surface', order=1, impacts_material=True)],
         materials=[dict(code='ETAN-TOIT', source='answer', answer='surface')]),
    dict(code='etancheite-fuite', name='Réparation ponctuelle de fuite', intervention_type='depannage',
         requires_diagnostic=True, confidence_level='diagnostic_required', duration=(2, 3, 5), width=25,
         questions=[dict(id='localisation', label='Où se situe la fuite constatée ?', type='text', order=1, required=False)],
         materials=[dict(code='ETAN-REPAR', source='fixed', qty=1)],
         diagnostic=dict(hypotheses=[
             {'label': 'Membrane endommagée localement', 'likelihood': 'medium'},
             {'label': 'Point singulier défaillant (évacuation, relevé)', 'likelihood': 'medium'},
         ], duration=(1, 2, 3))),
    dict(code='domotique-module', name='Module domotique (éclairage/volets/chauffage)', intervention_type='installation_neuve',
         confidence_level='medium', duration=(1, 2, 4), width=15,
         questions=[dict(id='nb_modules', label='Combien de modules souhaitez-vous ?', type='number', order=1, impacts_material=True)],
         materials=[dict(code='DOM-MOD', source='answer', answer='nb_modules')]),
    dict(code='domotique-securite', name='Sécurité connectée (alarme/caméra)', intervention_type='installation_neuve',
         confidence_level='medium', duration=(1, 2, 4), width=15,
         questions=[dict(id='nb_points', label='Combien de points sécurité ?', type='number', order=1, impacts_material=True)],
         materials=[dict(code='DOM-SEC', source='answer', answer='nb_points')]),
    dict(code='maintenance-contrat', name='Contrat de maintenance annuel', intervention_type='autre',
         confidence_level='high', duration=(0, 0, 0), width=5,
         questions=[], materials=[dict(code='MAINT-CONTRAT', source='fixed', qty=1)]),
    dict(code='maintenance-ponctuelle', name='Intervention ponctuelle hors contrat', intervention_type='depannage',
         confidence_level='medium', duration=(1, 1.5, 2.5), width=20,
         questions=[], materials=[dict(code='MAINT-PONCT', source='fixed', qty=1)]),
]

DOMAIN_SERVICES = {
    'electricite': ELECTRICITE,
    'informatique-reseaux': INFORMATIQUE,
    'btp-renovation': BTP_RENOVATION,
}


class Command(BaseCommand):
    help = 'Peuple le moteur configurateur générique pour NÉOSTRUCTURA.'

    def handle(self, *args, **options):
        from apps.core.models import Company
        from apps.btp.models import ElectricityPriceLibrary
        from apps.configurator.models import (
            ServiceDomain, ServiceCategory, ConfiguratorQuestion, ConfiguratorQuestionOption,
            MaterialRequirement, LaborRule, TravelRule, PricingCoefficient, MarginRule,
            DiagnosticScenario,
        )

        try:
            company = Company.objects.get(slug='neostructura')
        except Company.DoesNotExist:
            raise CommandError("Entreprise 'neostructura' introuvable.")

        price_items = {p.code: p for p in ElectricityPriceLibrary.objects.filter(company=company)}
        n_domains = n_services = n_questions = n_materials = 0

        for dom in DOMAINS:
            domain, _ = ServiceDomain.objects.update_or_create(
                company=company, code=dom['code'],
                defaults=dict(name=dom['name'], icon=dom['icon'], order=dom['order'],
                              description=dom['description'], is_active=True),
            )
            n_domains += 1

            for svc in DOMAIN_SERVICES[dom['code']]:
                dmin, davg, dmax = svc['duration']
                category, _ = ServiceCategory.objects.update_or_create(
                    domain=domain, code=svc['code'],
                    defaults=dict(
                        company=company, name=svc['name'],
                        intervention_type=svc.get('intervention_type', 'autre'),
                        requires_diagnostic=svc.get('requires_diagnostic', False),
                        confidence_level=svc.get('confidence_level', 'medium'),
                        duration_min_hours=Decimal(str(dmin)), duration_avg_hours=Decimal(str(davg)),
                        duration_max_hours=Decimal(str(dmax)), estimate_width_pct=svc.get('width', 15),
                        danger_alert=svc.get('danger_alert', False), is_active=True,
                    ),
                )
                n_services += 1

                question_objs = {}
                for q in svc['questions']:
                    question, _ = ConfiguratorQuestion.objects.update_or_create(
                        service=category, identifier=q['id'],
                        defaults=dict(
                            label=q['label'], question_type=q['type'], order=q['order'],
                            is_required=q.get('required', True),
                            display_condition=q.get('display_condition', {}),
                            impacts_diagnostic=q.get('impacts_diagnostic', False),
                            impacts_material=q.get('impacts_material', False),
                            impacts_duration=q.get('impacts_duration', False),
                            impacts_price=q.get('impacts_price', False),
                        ),
                    )
                    question_objs[q['id']] = question
                    n_questions += 1
                    for i, (val, label) in enumerate(q.get('options', [])):
                        ConfiguratorQuestionOption.objects.update_or_create(
                            question=question, value=val, defaults=dict(label=label, order=i),
                        )

                for order, mat in enumerate(svc.get('materials', [])):
                    price_item = price_items.get(mat['code'])
                    if not price_item:
                        self.stdout.write(self.style.WARNING(f"  Poste prix introuvable : {mat['code']} (ignoré)"))
                        continue
                    defaults = dict(
                        quantity_source='fixed' if mat['source'] == 'fixed' else 'from_answer',
                        fixed_quantity=Decimal(str(mat.get('qty', 1))),
                        quantity_answer=question_objs.get(mat.get('answer')) if mat['source'] == 'answer' else None,
                        quantity_multiplier=Decimal(str(mat.get('multiplier', 1))),
                        order=order,
                    )
                    MaterialRequirement.objects.update_or_create(
                        service=category, price_item=price_item, defaults=defaults,
                    )
                    n_materials += 1

                if svc.get('requires_diagnostic') and svc.get('diagnostic'):
                    diag = svc['diagnostic']
                    dmin2, davg2, dmax2 = diag['duration']
                    DiagnosticScenario.objects.update_or_create(
                        service=category,
                        defaults=dict(
                            hypotheses=diag['hypotheses'],
                            diagnostic_min_hours=Decimal(str(dmin2)), diagnostic_avg_hours=Decimal(str(davg2)),
                            diagnostic_max_hours=Decimal(str(dmax2)),
                            danger_keywords=diag.get('danger_keywords', []),
                        ),
                    )

        # ── Main-d'œuvre ──
        for rate_type, rate in [('normal', 55), ('urgent', 82), ('night', 70), ('weekend', 65)]:
            LaborRule.objects.update_or_create(
                company=company, domain=None, rate_type=rate_type,
                defaults=dict(label=f"Taux {rate_type}", hourly_rate=Decimal(str(rate)), is_active=True),
            )

        # ── Zones de déplacement ──
        zones = [
            ('zone1', 'Zone 1 — moins de 10 km', 0, 0, True),
            ('zone2', 'Zone 2 — 10 à 25 km', 25, 0, False),
            ('zone3', 'Zone 3 — 25 à 40 km', 45, 0, False),
            ('zone4', 'Zone 4 — plus de 40 km', 70, 50, False),
        ]
        for i, (code, label, fee, surcharge, is_default) in enumerate(zones):
            TravelRule.objects.update_or_create(
                company=company, zone_code=code,
                defaults=dict(zone_label=label, flat_fee=Decimal(str(fee)),
                              urgency_surcharge_pct=Decimal(str(surcharge)), is_default=is_default,
                              order=i, is_active=True),
            )

        # ── Coefficients de difficulté ──
        for code, label, mult in [
            ('acces_difficile', "Accès difficile (hauteur, sous-sol, combles)", '1.2'),
            ('complexite_elevee', 'Complexité technique élevée', '1.35'),
        ]:
            PricingCoefficient.objects.update_or_create(
                company=company, coefficient_type='difficulty', code=code, domain=None,
                defaults=dict(label=label, multiplier=Decimal(mult), is_active=True),
            )

        # ── Marge ──
        MarginRule.objects.update_or_create(
            company=company, scope_type='global', domain=None, category=None,
            defaults=dict(margin_percent=Decimal('25'), is_active=True),
        )

        self.stdout.write(self.style.SUCCESS(
            f'{n_domains} domaine(s), {n_services} prestation(s), {n_questions} question(s), '
            f'{n_materials} exigence(s) matériel — main-d\'œuvre/déplacement/coefficients/marge configurés.'
        ))
