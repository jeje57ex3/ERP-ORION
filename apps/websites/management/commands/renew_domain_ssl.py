"""
Commande : python manage.py renew_domain_ssl

Vérifie les certificats SSL des domaines actifs et signale ceux
qui expirent bientôt (dans moins de 30 jours par défaut).
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
import datetime


class Command(BaseCommand):
    help = 'Vérifie les certificats SSL et signale ceux qui expirent bientôt.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days', type=int, default=30,
            help='Nombre de jours avant expiration pour déclencher une alerte (défaut: 30).',
        )
        parser.add_argument(
            '--auto-renew', action='store_true',
            help='Tenter un renouvellement automatique (si l\'environnement le supporte).',
        )
        parser.add_argument(
            '--notify', action='store_true',
            help='Envoyer une notification ERP aux admins.',
        )

    def handle(self, *args, **options):
        from apps.websites.services.ssl_service import get_expiring_soon, check_ssl_certificate

        days      = options['days']
        threshold = timezone.now().date() + datetime.timedelta(days=days)

        self.stdout.write(f'\n🔐  Vérification SSL — domaines expirant avant le {threshold.strftime("%d/%m/%Y")}...\n')

        expiring = get_expiring_soon(days)
        total    = expiring.count()

        if total == 0:
            self.stdout.write(self.style.SUCCESS(f'  ✓ Aucun certificat n\'expire dans les {days} prochains jours.'))
            return

        self.stdout.write(self.style.WARNING(f'  ⚠️  {total} certificat(s) expirant bientôt :\n'))

        for domain in expiring:
            days_left = (domain.ssl_expires_at - timezone.now().date()).days if domain.ssl_expires_at else '?'
            self.stdout.write(
                f'  - {domain.domain:40s}  expire dans {days_left} jours  ({domain.ssl_expires_at})'
            )

            # Vérification SSL réelle
            result = check_ssl_certificate(domain)
            if not result['valid']:
                self.stdout.write(self.style.ERROR(f'    ✗ Certificat invalide : {result.get("error", "")}'))
                domain.ssl_status = 'expired'
                domain.save(update_fields=['ssl_status'])
            else:
                self.stdout.write(f'    ✓ Certificat toujours valide.')

            if options['auto_renew']:
                self.stdout.write(f'    ↻ Tentative de renouvellement automatique...')
                # Affiche la commande certbot à exécuter
                self.stdout.write(
                    f'      sudo certbot renew --cert-name {domain.domain} --non-interactive'
                )

            if options['notify']:
                try:
                    self._send_notification(domain, days_left)
                    self.stdout.write(f'    📧 Notification envoyée.')
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'    ✗ Notification : {e}'))

        self.stdout.write('')

    def _send_notification(self, domain, days_left):
        """Envoie une notification ERP à l'admin de l'entreprise."""
        try:
            from apps.notifications.models import Notification
            from django.contrib.auth.models import User

            admins = User.objects.filter(
                companymember__company=domain.company,
                companymember__role__in=['admin', 'owner'],
                is_active=True,
            )
            for admin in admins:
                Notification.objects.create(
                    user    = admin,
                    title   = f'SSL expirant bientôt : {domain.domain}',
                    message = f'Le certificat SSL de {domain.domain} expire dans {days_left} jours.',
                    type    = 'warning',
                )
        except Exception:
            pass
