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
    """Moteur local (Ollama).

    Le temps de réponse se décompose en trois parts, et les trois sont
    renseignées ici — plutôt que laissées aux valeurs par défaut :

      1. **Chargement du modèle.** Ollama le décharge après un délai
         d'inactivité (5 min par défaut), et la requête suivante attend
         plusieurs secondes qu'il remonte du disque. C'est ce qui rendait
         l'assistant « parfois très lent » sans raison visible. `keep_alive`
         le garde résident.
      2. **Évaluation du prompt**, proportionnelle à sa longueur. `num_ctx`
         borne l'allocation ; le budget d'historique, lui, est appliqué en
         amont (voir services.build_messages_for_provider).
      3. **Génération**, proportionnelle à la longueur de la réponse.
         `num_predict` en pose le plafond : sans lui, une réponse bavarde se
         paie en secondes d'attente.

    Les durées mesurées par Ollama sont renvoyées dans `timings`, et
    conservées avec le message. Le réglage se fait ainsi sur des chiffres.
    """

    def generate(self, *, messages, model, temperature=0.2, tools=None,
                 keep_alive_minutes=None, max_output_tokens=None,
                 context_window_tokens=None):
        base_url = getattr(settings, 'LOCAL_AI_BASE_URL', 'http://localhost:11434')
        url = base_url.rstrip('/') + '/api/chat'

        options = {'temperature': float(temperature)}
        if max_output_tokens:
            options['num_predict'] = int(max_output_tokens)
        if context_window_tokens:
            options['num_ctx'] = int(context_window_tokens)

        charge = {
            'model': model,
            'messages': messages,
            'stream': False,
            'options': options,
        }
        if keep_alive_minutes is not None:
            # Format accepté par Ollama : « 30m », ou 0 pour décharger
            # aussitôt. Passer un entier nu serait interprété en SECONDES,
            # et « 30 » garderait le modèle une demi-minute au lieu d'une
            # demi-heure — l'inverse de l'effet recherché.
            charge['keep_alive'] = (
                f'{int(keep_alive_minutes)}m' if int(keep_alive_minutes) > 0
                else 0
            )

        try:
            response = http_requests.post(
                url,
                json=charge,
                timeout=120,
            )
        except http_requests.exceptions.ConnectionError:
            raise AIProviderError(
                f"Le moteur local ne répond pas sur {base_url}. "
                'Sur le serveur : /opt/orion/scripts/orion-ai.sh status'
            )
        except http_requests.exceptions.Timeout:
            raise AIProviderError(
                "Délai d'attente dépassé par le moteur local. Le modèle est "
                'peut-être en cours de chargement, ou la machine manque de '
                'mémoire — réessayez, puis vérifiez la RAM disponible avec '
                'orion-ai.sh status.'
            )

        # Un 404 ici ne veut PAS dire que le point d'entrée est absent : Ollama
        # répond 404 quand le MODÈLE demandé n'est pas téléchargé. Sans cette
        # distinction, l'utilisateur recevait
        # « 404 Client Error: Not Found for url: .../api/chat », qui ne dit ni
        # ce qui manque ni quoi faire — constaté en production.
        if response.status_code == 404:
            raise AIProviderError(
                f"Le modèle « {model} » n'est pas téléchargé sur ce serveur. "
                'Lancez : /opt/orion/scripts/orion-ai.sh pull ' + model
            )

        if response.status_code >= 400:
            detail = ''
            try:
                detail = (response.json() or {}).get('error', '')
            except ValueError:
                detail = (response.text or '')[:200]
            raise AIProviderError(
                f'Le moteur local a refusé la requête (HTTP '
                f'{response.status_code}){" : " + detail if detail else "."}'
            )

        try:
            data = response.json()
        except ValueError:
            raise AIProviderError(
                'Réponse illisible du moteur local : du JSON était attendu. '
                f'{base_url} sert-il bien Ollama ?'
            )

        # Ollama chiffre lui-meme chaque part du temps, en nanosecondes. Les
        # exposer evite de regler a l'aveugle : « lent » ne dit pas s'il faut
        # garder le modele en memoire, raccourcir le prompt ou plafonner la
        # reponse -- et ce sont trois remedes differents.
        def _ms(cle):
            valeur = data.get(cle)
            return round(valeur / 1_000_000) if isinstance(valeur, (int, float)) else None

        jetons_sortie = data.get('eval_count', 0) or 0
        duree_generation = _ms('eval_duration')
        return {
            'content': data.get('message', {}).get('content', ''),
            'raw': data,
            'provider': 'local',
            'model': model,
            'token_input': data.get('prompt_eval_count', 0),
            'token_output': jetons_sortie,
            'timings': {
                'total_ms': _ms('total_duration'),
                'chargement_modele_ms': _ms('load_duration'),
                'evaluation_prompt_ms': _ms('prompt_eval_duration'),
                'generation_ms': duree_generation,
                'jetons_par_seconde': (
                    round(jetons_sortie / (duree_generation / 1000), 1)
                    if duree_generation and jetons_sortie else None
                ),
            },
        }


    def generate_stream(self, *, messages, model, temperature=0.2,
                        keep_alive_minutes=None, max_output_tokens=None,
                        context_window_tokens=None):
        """Même requête, mais rendue au fur et à mesure.

        C'est le gain de confort le plus important sur un petit modèle en CPU,
        et il ne vient d'aucune accélération : le temps total ne change pas.
        Ce qui change, c'est le temps avant le PREMIER mot. Sans flux,
        l'utilisateur attend la réponse entière — vingt ou trente secondes
        pendant lesquelles rien ne bouge, et pendant lesquelles il ne sait pas
        si l'assistant réfléchit ou s'il est en panne. Avec le flux, les
        premiers mots arrivent en une ou deux secondes et le reste défile.

        Produit des dictionnaires : {'delta': '...'} pour chaque morceau de
        texte, puis un dernier {'fin': True, 'timings': {...}, ...}.
        """
        base_url = getattr(settings, 'LOCAL_AI_BASE_URL', 'http://localhost:11434')
        url = base_url.rstrip('/') + '/api/chat'

        options = {'temperature': float(temperature)}
        if max_output_tokens:
            options['num_predict'] = int(max_output_tokens)
        if context_window_tokens:
            options['num_ctx'] = int(context_window_tokens)

        charge = {
            'model': model,
            'messages': messages,
            'stream': True,
            'options': options,
        }
        if keep_alive_minutes is not None:
            charge['keep_alive'] = (
                f'{int(keep_alive_minutes)}m' if int(keep_alive_minutes) > 0
                else 0
            )

        try:
            reponse = http_requests.post(
                url, json=charge, timeout=180, stream=True,
            )
        except http_requests.exceptions.ConnectionError:
            raise AIProviderError(
                f"Le moteur local ne répond pas sur {base_url}. "
                'Sur le serveur : /opt/orion/scripts/orion-ai.sh status'
            )

        if reponse.status_code == 404:
            raise AIProviderError(
                f"Le modèle « {model} » n'est pas téléchargé sur ce serveur. "
                'Lancez : /opt/orion/scripts/orion-ai.sh pull ' + model
            )
        if reponse.status_code >= 400:
            raise AIProviderError(
                'Le moteur local a refusé la requête (HTTP %s).'
                % reponse.status_code
            )

        import json as _json

        dernier = {}
        for ligne in reponse.iter_lines(decode_unicode=True):
            if not ligne:
                continue
            try:
                morceau = _json.loads(ligne)
            except ValueError:
                # Une ligne illisible ne doit pas interrompre un flux par
                # ailleurs valide : Ollama en émet une par jeton, et perdre
                # la réponse entière pour une seule serait disproportionné.
                continue

            texte = (morceau.get('message') or {}).get('content') or ''
            if texte:
                yield {'delta': texte}

            if morceau.get('done'):
                dernier = morceau
                break

        def _ms(cle):
            valeur = dernier.get(cle)
            return round(valeur / 1_000_000) if isinstance(valeur, (int, float)) else None

        jetons_sortie = dernier.get('eval_count', 0) or 0
        duree_generation = _ms('eval_duration')
        yield {
            'fin': True,
            'raw': dernier,
            'provider': 'local',
            'model': model,
            'token_input': dernier.get('prompt_eval_count', 0),
            'token_output': jetons_sortie,
            'timings': {
                'total_ms': _ms('total_duration'),
                'chargement_modele_ms': _ms('load_duration'),
                'evaluation_prompt_ms': _ms('prompt_eval_duration'),
                'generation_ms': duree_generation,
                'jetons_par_seconde': (
                    round(jetons_sortie / (duree_generation / 1000), 1)
                    if duree_generation and jetons_sortie else None
                ),
            },
        }


FOURNISSEURS_EXTERNES = ('openai', 'anthropic')


def get_ai_provider(provider_name, local_only=None):
    """Fournisseur demandé, sauf si le verrou local l'interdit.

    `local_only` est une INTERDICTION, pas une préférence. « Répondre
    uniquement en local » est une propriété de confidentialité : les devis,
    les clients, les factures et l'état du système ne doivent jamais quitter
    la machine. Un réglage par défaut se change par inadvertance — un appel
    externe serait alors fait sans que personne le remarque, et les données
    seraient déjà parties. Le refus est donc ici, au seul endroit par lequel
    tout appel passe.

    `local_only=None` retombe sur ORION_AI_LOCAL_ONLY, vrai par défaut.
    """
    if local_only is None:
        local_only = getattr(settings, 'ORION_AI_LOCAL_ONLY', True)

    if local_only and provider_name in FOURNISSEURS_EXTERNES:
        raise AIProviderError(
            f'Le fournisseur « {provider_name} » est externe, et le traitement '
            'local uniquement est activé : aucune donnée ne doit quitter ce '
            'serveur. Choisissez le fournisseur local, ou levez '
            'explicitement ce verrou dans les paramètres IA.'
        )

    if provider_name == 'openai':
        return OpenAIProvider()
    if provider_name == 'anthropic':
        return AnthropicProvider()
    if provider_name == 'local':
        return LocalAIProvider()
    raise AIProviderError(f'Fournisseur IA inconnu : {provider_name}')
