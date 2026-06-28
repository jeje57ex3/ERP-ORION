from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Teste la connexion au fournisseur IA configuré'

    def add_arguments(self, parser):
        parser.add_argument('--provider', default=None, help='openai, anthropic, local')
        parser.add_argument('--prompt', default='Dis bonjour en une phrase.', help='Prompt de test')

    def handle(self, *args, **options):
        from apps.orion_ai.models import OrionAISettings
        from apps.orion_ai.providers import get_ai_provider, AIProviderError

        ai_settings = OrionAISettings.get_global()
        provider_name = options['provider'] or ai_settings.default_provider
        prompt = options['prompt']

        self.stdout.write(f'Test fournisseur : {provider_name}')
        self.stdout.write(f'Modèle          : {ai_settings.default_model}')
        self.stdout.write(f'Prompt          : {prompt}')
        self.stdout.write('---')

        try:
            provider = get_ai_provider(provider_name)
            result = provider.generate(
                messages=[
                    {'role': 'system', 'content': 'Tu es un assistant de test Orion ERP.'},
                    {'role': 'user', 'content': prompt},
                ],
                model=ai_settings.default_model,
                temperature=0.2,
            )
            self.stdout.write(self.style.SUCCESS(f'✓ Réponse reçue :'))
            self.stdout.write(result['content'])
            self.stdout.write(f'Tokens entrée : {result.get("token_input", "N/A")}')
            self.stdout.write(f'Tokens sortie : {result.get("token_output", "N/A")}')

        except AIProviderError as exc:
            self.stdout.write(self.style.ERROR(f'✗ Erreur fournisseur IA : {exc}'))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f'✗ Erreur inattendue : {exc}'))
