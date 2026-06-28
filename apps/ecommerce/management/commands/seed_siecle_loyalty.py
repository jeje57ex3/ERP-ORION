"""
python manage.py seed_siecle_loyalty --company-id=1

Configure les niveaux de fidélité et les missions SIÈCLE.
"""
from django.core.management.base import BaseCommand, CommandError


TIERS = [
    {'name': 'BRONZE',   'min_points': 0,     'discount_percent': 0,   'free_shipping': False, 'early_access': False},
    {'name': 'SILVER',   'min_points': 1000,  'discount_percent': 5,   'free_shipping': True,  'early_access': True},
    {'name': 'GOLD',     'min_points': 5000,  'discount_percent': 10,  'free_shipping': True,  'early_access': True},
    {'name': 'PLATINUM', 'min_points': 15000, 'discount_percent': 15,  'free_shipping': True,  'early_access': True},
]

MISSIONS = [
    {'title': 'Première commande',    'icon': '🛒', 'points': 200, 'mission_type': 'first_order'},
    {'title': 'Compléter le profil',  'icon': '👤', 'points': 100, 'mission_type': 'complete_profile'},
    {'title': 'Laisser un avis',      'icon': '⭐', 'points': 50,  'mission_type': 'leave_review'},
    {'title': 'Partager un look',     'icon': '📸', 'points': 150, 'mission_type': 'share_look'},
    {'title': 'Parrainer un ami',     'icon': '🤝', 'points': 300, 'mission_type': 'referral'},
    {'title': 'Quiz identité complété','icon': '🎯', 'points': 75,  'mission_type': 'identity_quiz'},
    {'title': 'Quiz beauté complété', 'icon': '💄', 'points': 75,  'mission_type': 'beauty_quiz'},
    {'title': '5 commandes passées',  'icon': '🏆', 'points': 500, 'mission_type': 'five_orders'},
]


class Command(BaseCommand):
    help = 'Configure les niveaux de fidélité et missions SIÈCLE'

    def add_arguments(self, parser):
        parser.add_argument('--company-id', type=int, default=1)

    def handle(self, *args, **options):
        from apps.core.models import Company
        try:
            company = Company.objects.get(pk=options['company_id'])
        except Company.DoesNotExist:
            raise CommandError(f"Company id={options['company_id']} introuvable")

        # Try to create/update loyalty tiers
        created_tiers = 0
        try:
            from apps.websites.models import LoyaltyTier
            for t in TIERS:
                obj, created = LoyaltyTier.objects.get_or_create(
                    company=company, name=t['name'], defaults=t
                )
                if not created:
                    for k, v in t.items():
                        setattr(obj, k, v)
                    obj.save()
                if created:
                    created_tiers += 1
            self.stdout.write(self.style.SUCCESS(f'{created_tiers} niveaux fidélité créés.'))
        except Exception as e:
            self.stderr.write(self.style.WARNING(f'LoyaltyTier non disponible: {e}'))

        # Try to create missions
        created_missions = 0
        try:
            from apps.websites.models import LoyaltyMission
            for m in MISSIONS:
                obj, created = LoyaltyMission.objects.get_or_create(
                    company=company, mission_type=m['mission_type'],
                    defaults={**m, 'company': company, 'is_active': True}
                )
                if created:
                    created_missions += 1
            self.stdout.write(self.style.SUCCESS(f'{created_missions} missions créées.'))
        except Exception as e:
            self.stderr.write(self.style.WARNING(f'LoyaltyMission non disponible: {e}'))

        self.stdout.write(self.style.SUCCESS('Fidélité SIÈCLE configurée.'))
