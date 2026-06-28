"""
Commande : python manage.py sync_domain_status

Met à jour le statut de tous les domaines actifs :
- Vérifie les DNS
- Vérifie l'état SSL
- Met à jour les statuts en base
"""
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Met à jour le statut DNS et SSL de tous les domaines actifs.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--company-id', type=int,
            help='Limiter à une entreprise.',
        )
        parser.add_argument(
            '--check-ssl', action='store_true',
            help='Vérifier aussi les certificats SSL.',
        )
        parser.add_argument(
            '--force', action='store_true',
            help='Forcer la vérification même pour les domaines déjà actifs.',
        )

    def handle(self, *args, **options):
        from apps.websites.models import WebsiteDomain
        from apps.websites.domain_services import verify_domain_ownership

        qs = WebsiteDomain.objects.select_related('website', 'website__company')

        if options['company_id']:
            qs = qs.filter(website__company_id=options['company_id'])

        if not options['force']:
            qs = qs.filter(status__in=['pending', 'dns_pending', 'dns_verified', 'error'])

        qs = qs.exclude(status='disabled')
        total = qs.count()

        self.stdout.write(f'\n🔄  Synchronisation de {total} domaine(s)...\n')
        verified_count = 0
        failed_count   = 0
        ssl_checked    = 0

        for domain in qs:
            self.stdout.write(f'  {domain.domain} ... ', ending='')
            try:
                ok = verify_domain_ownership(domain)
                if ok:
                    verified_count += 1
                    self.stdout.write(self.style.SUCCESS('✓ DNS vérifié'))
                else:
                    failed_count += 1
                    err = domain.last_error[:60] if domain.last_error else 'non résolu'
                    self.stdout.write(self.style.WARNING(f'✗ {err}'))
            except Exception as e:
                failed_count += 1
                self.stdout.write(self.style.ERROR(f'✗ Erreur : {e}'))

            # Vérification SSL optionnelle
            if options['check_ssl'] and domain.ssl_enabled:
                try:
                    from apps.websites.services.ssl_service import check_ssl_certificate, mark_ssl_active
                    result = check_ssl_certificate(domain)
                    ssl_checked += 1
                    if result['valid']:
                        if result.get('expires_at'):
                            mark_ssl_active(domain, expires_at=result['expires_at'])
                        self.stdout.write(f'       SSL ✓ (expire: {domain.ssl_expires_at})')
                    else:
                        domain.ssl_status = 'error'
                        domain.save(update_fields=['ssl_status'])
                        self.stdout.write(self.style.ERROR(f'       SSL ✗ : {result.get("error", "")}'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'       SSL erreur : {e}'))

        self.stdout.write(
            f'\n✅  {verified_count} vérifié(s), '
            f'⚠️  {failed_count} échec(s) sur {total} domaine(s).'
        )
        if options['check_ssl']:
            self.stdout.write(f'🔐  {ssl_checked} SSL vérifiés.')
        self.stdout.write('')
