from django.core.management.base import BaseCommand

from apps.website_shop_settings.models import WebsiteShopSettings


class Command(BaseCommand):
    help = 'Vérifie l\'état des paramètres boutique pour chaque site.'

    def handle(self, *args, **options):
        settings_list = WebsiteShopSettings.objects.select_related(
            'company', 'payment_settings', 'maintenance_settings',
        ).order_by('company__name', 'brand_key')

        if not settings_list.exists():
            self.stdout.write(self.style.WARNING('Aucun paramètre boutique trouvé.'))
            return

        for s in settings_list:
            self.stdout.write(f'\n-- {s.company.name} / {s.brand_key} --')
            self.stdout.write(f'  Site activé    : {s.is_site_enabled}')
            self.stdout.write(f'  Shop activé    : {s.is_shop_enabled}')
            try:
                p = s.payment_settings
                self.stdout.write(f'  Paiements      : enabled={p.payments_enabled}, stripe={p.stripe_enabled}, mode={p.stripe_mode}')
                self.stdout.write(f'  Cle pub Stripe : {"OK" if p.stripe_publishable_key else "MANQUANTE"}')
                self.stdout.write(f'  Cle sec chiffr.: {"OK" if p.stripe_secret_key_encrypted else "MANQUANTE"}')
            except Exception:
                self.stdout.write(self.style.WARNING('  Paiements : paramètres manquants'))
            try:
                m = s.maintenance_settings
                if m.maintenance_enabled:
                    self.stdout.write(self.style.WARNING(f'  MAINTENANCE    : ACTIVE'))
                else:
                    self.stdout.write(f'  Maintenance    : inactive')
            except Exception:
                pass
