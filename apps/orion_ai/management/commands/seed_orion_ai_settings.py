from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Initialise les paramètres globaux de l\'assistant IA Orion'

    def handle(self, *args, **options):
        from apps.orion_ai.models import OrionAISettings

        ai_settings = OrionAISettings.get_global()

        self.stdout.write(f'Paramètres IA globaux : {ai_settings}')
        self.stdout.write(f'  Provider : {ai_settings.default_provider}')
        self.stdout.write(f'  Modèle   : {ai_settings.default_model}')
        self.stdout.write(f'  Activé   : {ai_settings.ai_enabled}')
        self.stdout.write(f'  Outils   : {ai_settings.allow_tools}')
        self.stdout.write(self.style.SUCCESS('OK Parametres IA initialises.'))
