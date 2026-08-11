import os

from django.core.management.base import BaseCommand

from apps.system_updates.models import SystemUpdateSettings
from apps.website_shop_settings.crypto import encrypt_secret


class Command(BaseCommand):
    help = 'Crée les paramètres par défaut du module mises à jour.'

    def handle(self, *args, **options):
        obj = SystemUpdateSettings.get_solo()

        # Préseed le jeton GitHub depuis GITHUB_TOKEN (--github-token au
        # déploiement, voir deploy.sh) si fourni et pas déjà configuré —
        # évite à l'admin de le ressaisir dans l'interface après coup, sans
        # jamais écraser un jeton déjà en base (ex: renouvelé depuis l'UI).
        token = os.environ.get('GITHUB_TOKEN', '').strip()
        if token and not obj.github_token_encrypted:
            obj.github_token_encrypted = encrypt_secret(token)
            obj.save(update_fields=['github_token_encrypted'])
            self.stdout.write(self.style.SUCCESS('Jeton GitHub préseedé depuis GITHUB_TOKEN.'))

        self.stdout.write(self.style.SUCCESS(
            f'Paramètres mises à jour initialisés (id={obj.id}).'
        ))
