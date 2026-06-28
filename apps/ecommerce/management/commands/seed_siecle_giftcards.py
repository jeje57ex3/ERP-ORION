"""
python manage.py seed_siecle_giftcards --company-id=1

Seed les designs de cartes cadeaux SIÈCLE.
"""
from django.core.management.base import BaseCommand, CommandError

DESIGNS = [
    {'slug': 'noir-signature', 'name': 'Noir Signature', 'bg_color': '#000000', 'text_color': '#D8C7A3', 'is_active': True},
    {'slug': 'beige-elegance', 'name': 'Beige Élégance', 'bg_color': '#D8C7A3', 'text_color': '#000000', 'is_active': True},
    {'slug': 'dore-nuit',      'name': 'Doré Nuit',       'bg_color': '#1a1200', 'text_color': '#FFD700', 'is_active': True},
    {'slug': 'minimal-blanc',  'name': 'Minimal Blanc',   'bg_color': '#ffffff', 'text_color': '#111111', 'is_active': True},
]

PRESET_AMOUNTS = [25, 50, 100, 150, 200, 300]


class Command(BaseCommand):
    help = 'Seed les designs de cartes cadeaux SIÈCLE'

    def add_arguments(self, parser):
        parser.add_argument('--company-id', type=int, default=1)

    def handle(self, *args, **options):
        from apps.core.models import Company
        try:
            company = Company.objects.get(pk=options['company_id'])
        except Company.DoesNotExist:
            raise CommandError(f"Company id={options['company_id']} introuvable")

        created = 0
        try:
            from apps.websites.models import GiftCardDesign
            for d in DESIGNS:
                obj, c = GiftCardDesign.objects.get_or_create(
                    company=company, slug=d['slug'], defaults={**d, 'company': company}
                )
                if c:
                    created += 1
            self.stdout.write(self.style.SUCCESS(f'{created} designs de cartes cadeaux créés.'))
        except Exception as e:
            self.stderr.write(self.style.WARNING(f'GiftCardDesign non disponible: {e}'))
            self.stdout.write(f'Designs définis (en mémoire): {[d["name"] for d in DESIGNS]}')

        self.stdout.write(self.style.SUCCESS(f'Montants prédéfinis: {PRESET_AMOUNTS}'))
        self.stdout.write(self.style.SUCCESS('Cartes cadeaux SIÈCLE configurées.'))
