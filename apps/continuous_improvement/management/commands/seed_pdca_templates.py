from django.core.management.base import BaseCommand

from apps.continuous_improvement.models import PDCATemplate

TEMPLATES = [
    {
        'title': 'Réduction des réclamations client',
        'category': 'customer_service',
        'priority': 'high',
        'description': 'Réduire le nombre et le délai de traitement des réclamations client.',
        'default_problem_statement': 'Trop de réclamations client non résolues dans les délais.',
        'default_objective': 'Réduire le taux de réclamations de 30% en 3 mois.',
        'default_success_criteria': 'Taux de résolution au premier contact > 80%. Délai < 24h.',
        'related_module': 'crm',
        'default_actions': [
            {'title': 'Cartographier les types de réclamations', 'description': ''},
            {'title': 'Former les équipes au traitement des réclamations', 'description': ''},
            {'title': 'Mettre en place un suivi hebdomadaire', 'description': ''},
        ],
        'default_kpis': [
            {'name': 'Nombre de réclamations', 'unit': ''},
            {'name': 'Délai moyen de traitement', 'unit': 'h'},
            {'name': 'Taux de résolution premier contact', 'unit': '%'},
        ],
        'is_system_template': True,
    },
    {
        'title': 'Amélioration du taux de conversion boutique',
        'category': 'shop',
        'priority': 'high',
        'description': 'Augmenter le taux de conversion des visiteurs en acheteurs.',
        'default_problem_statement': 'Faible taux de conversion sur la boutique en ligne.',
        'default_objective': 'Augmenter le taux de conversion de X% à Y% en 2 mois.',
        'default_success_criteria': 'Taux de conversion > 3%. Panier moyen stable.',
        'related_module': 'ecommerce',
        'default_actions': [
            {'title': 'Analyser les abandons de panier', 'description': ''},
            {'title': 'Optimiser les fiches produits', 'description': ''},
            {'title': 'Tester de nouvelles campagnes', 'description': ''},
        ],
        'default_kpis': [
            {'name': 'Taux de conversion', 'unit': '%'},
            {'name': 'Panier moyen', 'unit': 'EUR'},
            {'name': 'Abandons de panier', 'unit': '%'},
        ],
        'is_system_template': True,
    },
    {
        'title': 'Résolution d\'un bug critique',
        'category': 'bug',
        'priority': 'critical',
        'description': 'Identifier, corriger et prévenir la récurrence d\'un bug critique.',
        'default_problem_statement': 'Un bug critique impacte le fonctionnement du système.',
        'default_objective': 'Corriger le bug et mettre en place des mesures préventives.',
        'default_success_criteria': 'Bug résolu. Tests de non-régression passés. Documentation à jour.',
        'related_module': 'system_health',
        'default_actions': [
            {'title': 'Reproduire et documenter le bug', 'description': ''},
            {'title': 'Identifier la cause racine', 'description': ''},
            {'title': 'Développer et tester le correctif', 'description': ''},
            {'title': 'Déployer en production', 'description': ''},
            {'title': 'Ajouter un test de non-régression', 'description': ''},
        ],
        'default_kpis': [
            {'name': 'Délai de résolution', 'unit': 'h'},
            {'name': 'Tests de non-régression', 'unit': ''},
        ],
        'is_system_template': True,
    },
    {
        'title': 'Gestion des ruptures de stock',
        'category': 'stock',
        'priority': 'medium',
        'description': 'Réduire les ruptures de stock et améliorer la disponibilité produit.',
        'default_problem_statement': 'Ruptures de stock fréquentes entraînant des ventes perdues.',
        'default_objective': 'Réduire les ruptures de stock de 50% en 6 semaines.',
        'default_success_criteria': 'Taux de disponibilité > 95%. Alertes stock bas actives.',
        'related_module': 'ecommerce',
        'default_actions': [
            {'title': 'Analyser les produits en rupture fréquente', 'description': ''},
            {'title': 'Contacter les fournisseurs', 'description': ''},
            {'title': 'Définir des seuils d\'alerte de stock', 'description': ''},
        ],
        'default_kpis': [
            {'name': 'Produits en rupture', 'unit': ''},
            {'name': 'Taux de disponibilité', 'unit': '%'},
        ],
        'is_system_template': True,
    },
    {
        'title': 'Amélioration de la santé système',
        'category': 'system_health',
        'priority': 'high',
        'description': 'Résoudre les problèmes détectés par le module de santé système.',
        'default_problem_statement': 'Plusieurs problèmes système détectés nécessitant une intervention.',
        'default_objective': 'Résoudre tous les problèmes critiques en 1 semaine.',
        'default_success_criteria': 'Score de santé système > 90%. Aucun problème critique ouvert.',
        'related_module': 'system_health',
        'default_actions': [
            {'title': 'Inventorier tous les problèmes ouverts', 'description': ''},
            {'title': 'Prioriser par criticité', 'description': ''},
            {'title': 'Résoudre les problèmes critiques', 'description': ''},
            {'title': 'Planifier la résolution des problèmes mineurs', 'description': ''},
        ],
        'default_kpis': [
            {'name': 'Problèmes critiques ouverts', 'unit': ''},
            {'name': 'Score santé système', 'unit': '%'},
        ],
        'is_system_template': True,
    },
    {
        'title': 'Optimisation des délais de livraison',
        'category': 'delivery',
        'priority': 'medium',
        'description': 'Réduire les délais de livraison et améliorer la satisfaction client.',
        'default_problem_statement': 'Les délais de livraison dépassent les engagements contractuels.',
        'default_objective': 'Livraison sous 3 jours ouvrés pour 95% des commandes.',
        'default_success_criteria': 'Délai moyen < 3j. Taux de satisfaction livraison > 90%.',
        'related_module': 'ecommerce',
        'default_actions': [
            {'title': 'Analyser les étapes de préparation', 'description': ''},
            {'title': 'Négocier avec les transporteurs', 'description': ''},
            {'title': 'Automatiser les confirmations d\'expédition', 'description': ''},
        ],
        'default_kpis': [
            {'name': 'Délai moyen de livraison', 'unit': 'j'},
            {'name': 'Taux de livraison à temps', 'unit': '%'},
        ],
        'is_system_template': True,
    },
]


class Command(BaseCommand):
    help = 'Installe les modèles PDCA par défaut'

    def handle(self, *args, **options):
        created = 0
        updated = 0
        for tpl in TEMPLATES:
            obj, was_created = PDCATemplate.objects.update_or_create(
                title=tpl['title'],
                defaults={
                    'category': tpl['category'],
                    'priority': tpl['priority'],
                    'description': tpl.get('description', ''),
                    'default_problem_statement': tpl.get('default_problem_statement', ''),
                    'default_objective': tpl.get('default_objective', ''),
                    'default_success_criteria': tpl.get('default_success_criteria', ''),
                    'related_module': tpl.get('related_module', ''),
                    'default_actions': tpl.get('default_actions', []),
                    'default_kpis': tpl.get('default_kpis', []),
                    'is_system_template': tpl.get('is_system_template', False),
                    'is_active': True,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(self.style.SUCCESS(
            f'Modeles PDCA : {created} crees, {updated} mis a jour.'
        ))
