import requests as http_requests

from django.conf import settings


class AIProviderError(Exception):
    pass


class BaseAIProvider:
    def generate(self, *, messages, model, temperature=0.2, tools=None):
        raise NotImplementedError


class OpenAIProvider(BaseAIProvider):
    def generate(self, *, messages, model, temperature=0.2, tools=None):
        try:
            from openai import OpenAI
        except ImportError:
            raise AIProviderError("Le package openai n'est pas installé. Exécutez : pip install openai")

        api_key = getattr(settings, 'OPENAI_API_KEY', '')
        if not api_key:
            raise AIProviderError('OPENAI_API_KEY manquante dans la configuration.')

        client = OpenAI(api_key=api_key)

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=float(temperature),
        )

        content = response.choices[0].message.content or ''

        usage = response.usage
        token_input = usage.prompt_tokens if usage else 0
        token_output = usage.completion_tokens if usage else 0

        return {
            'content': content,
            'raw': response.model_dump() if hasattr(response, 'model_dump') else {},
            'provider': 'openai',
            'model': model,
            'token_input': token_input,
            'token_output': token_output,
        }


class AnthropicProvider(BaseAIProvider):
    def generate(self, *, messages, model, temperature=0.2, tools=None):
        try:
            import anthropic
        except ImportError:
            raise AIProviderError("Le package anthropic n'est pas installé. Exécutez : pip install anthropic")

        api_key = getattr(settings, 'ANTHROPIC_API_KEY', '')
        if not api_key:
            raise AIProviderError('ANTHROPIC_API_KEY manquante dans la configuration.')

        client = anthropic.Anthropic(api_key=api_key)

        system = ''
        clean_messages = []

        for message in messages:
            if message['role'] == 'system':
                system += message['content'] + '\n'
            else:
                clean_messages.append(message)

        response = client.messages.create(
            model=model,
            system=system.strip(),
            messages=clean_messages,
            max_tokens=4096,
            temperature=float(temperature),
        )

        content = ''
        for block in response.content:
            if getattr(block, 'type', '') == 'text':
                content += block.text

        usage = response.usage
        token_input = usage.input_tokens if usage else 0
        token_output = usage.output_tokens if usage else 0

        return {
            'content': content,
            'raw': response.model_dump() if hasattr(response, 'model_dump') else {},
            'provider': 'anthropic',
            'model': model,
            'token_input': token_input,
            'token_output': token_output,
        }


class LocalAIProvider(BaseAIProvider):
    def generate(self, *, messages, model, temperature=0.2, tools=None):
        base_url = getattr(settings, 'LOCAL_AI_BASE_URL', 'http://localhost:11434')
        url = base_url.rstrip('/') + '/api/chat'

        try:
            response = http_requests.post(
                url,
                json={
                    'model': model,
                    'messages': messages,
                    'stream': False,
                    'options': {
                        'temperature': float(temperature),
                    },
                },
                timeout=120,
            )
            response.raise_for_status()
        except http_requests.exceptions.ConnectionError:
            raise AIProviderError(f"Impossible de se connecter à l'IA locale : {base_url}")
        except http_requests.exceptions.Timeout:
            raise AIProviderError("Délai d'attente dépassé pour l'IA locale.")

        data = response.json()

        return {
            'content': data.get('message', {}).get('content', ''),
            'raw': data,
            'provider': 'local',
            'model': model,
            'token_input': data.get('prompt_eval_count', 0),
            'token_output': data.get('eval_count', 0),
        }


def get_ai_provider(provider_name):
    if provider_name == 'openai':
        return OpenAIProvider()
    if provider_name == 'anthropic':
        return AnthropicProvider()
    if provider_name == 'local':
        return LocalAIProvider()
    raise AIProviderError(f'Fournisseur IA inconnu : {provider_name}')
