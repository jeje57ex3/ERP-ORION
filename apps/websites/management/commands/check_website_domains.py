"""
Commande pour vérifier les DNS des domaines de sites web.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.websites.models import WebsiteDomain


class Command(BaseCommand):
    help = 'Vérifie les enregistrements DNS de tous les domaines actifs.'

    def add_arguments(self, parser):
        parser.add_argument('--website-id', type=int, help='Vérifier uniquement ce site.')
        parser.add_argument('--force', action='store_true', help='Revérifier même les domaines déjà vérifiés.')

    def handle(self, *args, **options):
        from apps.websites.domain_services import verify_domain_ownership

        qs = WebsiteDomain.objects.filter(
            status__in=['dns_pending', 'dns_verified', 'active', 'error', 'pending']
        ).select_related('website')

        if options['website_id']:
            qs = qs.filter(website_id=options['website_id'])

        if not options['force']:
            qs = qs.exclude(status='active')

        total = qs.count()
        self.stdout.write(f'Vérification de {total} domaine(s)...\n')

        verified = 0
        failed = 0
        for domain in qs:
            self.stdout.write(f'  Checking {domain.domain}... ', ending='')
            try:
                result = verify_domain_ownership(domain)
                if result:
                    verified += 1
                    self.stdout.write(self.style.SUCCESS('✓ DNS vérifié'))
                else:
                    failed += 1
                    self.stdout.write(self.style.WARNING(f'✗ Non vérifié ({domain.last_error[:50]})'))
            except Exception as e:
                failed += 1
                self.stdout.write(self.style.ERROR(f'✗ Erreur : {e}'))

        self.stdout.write(f'\n{verified} vérifié(s), {failed} échec(s) sur {total} domaine(s).')
