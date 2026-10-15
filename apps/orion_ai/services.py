from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.orion_ai.knowledge import contexte_pour_question
from apps.orion_ai.memory import get_memory_context
from apps.orion_ai.models import (
    OrionAIAuditLog,
    OrionAIConversation,
    OrionAIMessage,
    OrionAIProposedAction,
    OrionAISettings,
    OrionAIToolCall,
)
from apps.orion_ai.permissions import can_use_ai
from apps.orion_ai.prompts import build_system_prompt
from apps.orion_ai.providers import get_ai_provider, AIProviderError
from apps.orion_ai.safety import (
    is_dangerous_action,
    is_write_action,
    redact_payload,
    redact_sensitive_text,
    validate_user_prompt,
)
from apps.orion_ai.tool_registry import get_ai_tool


def get_request_company(request):
    return getattr(request, 'active_company', None) or getattr(request, 'company', None)


def get_ai_settings(company=None):
    if company:
        return OrionAISettings.get_for_company(company)
    return OrionAISettings.get_global()


def audit_ai_event(*, company, user, event_type, title, description='', payload=None, request=None):
    payload = redact_payload(payload or {})
    OrionAIAuditLog.objects.create(
        company=company,
        user=user,
        event_type=event_type,
        title=title,
        description=description,
        payload=payload,
        ip_address=request.META.get('REMOTE_ADDR') if request else None,
        user_agent=request.META.get('HTTP_USER_AGENT', '') if request else '',
    )


def build_messages_for_provider(conversation, ai_settings, user_message,
                                company=None, user=None, brand_key='',
                                exclure_message_id=None):
    system_prompt = build_system_prompt(ai_settings, user=user, company=company)

    memory_context = get_memory_context(
        company=company,
        user=user,
        brand_key=brand_key,
    )
    if memory_context:
        system_prompt += '\n\n' + memory_context

    # Faits vérifiés, cherchés AVANT l'appel au modèle plutôt que laissés à
    # son initiative. Les appels d'outils décidés par le modèle sont peu
    # fiables sur un petit modèle local : il oublie de s'en servir, ou invente
    # les arguments. La recherche déterministe, elle, aboutit toujours — et
    # les adresses qu'elle fournit sortent du résolveur d'URL, donc existent.
    grounding = contexte_pour_question(
        user_message,
        user=user,
        company=company,
        module_courant=getattr(conversation, 'context_module', '') or '',
    )
    if grounding:
        system_prompt += '\n\n' + grounding

    messages = [{'role': 'system', 'content': system_prompt}]

    # La question courante est DEJA enregistree en base quand cette fonction
    # est appelee : sans cette exclusion, elle figurait dans l'historique PUIS
    # etait ajoutee une seconde fois en fin de liste. Chaque requete envoyait
    # donc la question en double -- des jetons de prompt payes pour rien a
    # chaque echange, et un modele qui voyait la demande repetee.
    anciens = conversation.messages.exclude(role='system')
    if exclure_message_id is not None:
        anciens = anciens.exclude(pk=exclure_message_id)

    history = list(
        anciens.order_by('-created_at')[:ai_settings.max_history_messages]
    )
    history = list(reversed(history))

    # Budget en CARACTERES, en plus du nombre de messages. Sur un petit modele
    # en CPU, c'est l'evaluation du prompt qui domine le temps de reponse, et
    # elle croit avec la longueur -- pas avec le nombre de messages. Vingt
    # messages courts coutent moins que trois longs. Sans ce budget, une
    # conversation ralentissait a mesure qu'elle avancait, sans que rien ne
    # l'explique a l'utilisateur.
    #
    # On garde les plus RECENTS : ce sont eux qui portent le contexte utile.
    budget = getattr(ai_settings, 'max_history_chars', 0) or 0
    if budget:
        retenus = []
        total = 0
        for msg in reversed(history):
            if msg.role not in ('user', 'assistant'):
                continue
            taille = len(msg.content or '')
            if retenus and total + taille > budget:
                break
            retenus.append(msg)
            total += taille
        history = list(reversed(retenus))

    for msg in history:
        if msg.role in ('user', 'assistant'):
            messages.append({'role': msg.role, 'content': msg.content})

    messages.append({'role': 'user', 'content': user_message})

    return messages


def create_or_get_conversation(*, company, user, conversation_id=None, title='Nouvelle conversation', context_module='', brand_key=''):
    if conversation_id:
        return OrionAIConversation.objects.get(
            id=conversation_id,
            company=company,
            user=user,
        )
    return OrionAIConversation.objects.create(
        company=company,
        user=user,
        title=title,
        context_module=context_module,
        brand_key=brand_key,
    )


def _avec_mesures(response):
    """Joint les durees mesurees a la charge brute conservee du message.

    Elles sont la seule facon de regler le temps de reponse sans deviner :
    « lent » ne dit pas s'il faut garder le modele en memoire, raccourcir le
    prompt ou plafonner la reponse, et ce sont trois remedes differents. Les
    conserver par message permet de le voir apres coup, y compris sur un
    ralentissement passe.
    """
    brut = dict(response.get('raw') or {})
    mesures = response.get('timings')
    if mesures:
        brut['mesures_orion'] = mesures
    return brut


@transaction.atomic
def send_ai_message(*, request, prompt, conversation_id=None, context_module='', brand_key=''):
    user = request.user
    company = get_request_company(request)

    if not can_use_ai(user):
        raise PermissionError("Vous n'avez pas accès à l'assistant IA.")

    ai_settings = get_ai_settings(company)

    if not ai_settings.ai_enabled or not getattr(settings, 'ORION_AI_ENABLED', False):
        raise RuntimeError("L'assistant IA est désactivé. Activez ORION_AI_ENABLED dans la configuration.")

    valid, error_message = validate_user_prompt(prompt)
    if not valid:
        raise ValueError(error_message)

    if len(prompt) > ai_settings.max_input_chars:
        raise ValueError(f'Message trop long (max {ai_settings.max_input_chars} caractères).')

    clean_prompt = redact_sensitive_text(prompt) if ai_settings.redact_sensitive_data else prompt

    conversation = create_or_get_conversation(
        company=company,
        user=user,
        conversation_id=conversation_id,
        context_module=context_module,
        brand_key=brand_key,
    )

    message_utilisateur = OrionAIMessage.objects.create(
        conversation=conversation,
        role='user',
        content=clean_prompt,
    )

    messages = build_messages_for_provider(
        conversation,
        ai_settings,
        clean_prompt,
        company=company,
        user=user,
        brand_key=brand_key,
        # Deja enregistree juste au-dessus : l'exclure de l'historique evite
        # de l'envoyer deux fois.
        exclure_message_id=message_utilisateur.pk,
    )

    # Le verrou de l'entreprise est transmis au fabricant de fournisseur :
    # c'est lui qui refuse, parce que tout appel passe par la. Le verifier
    # ici seulement laisserait d'autres chemins d'appel le contourner.
    provider = get_ai_provider(
        ai_settings.default_provider,
        local_only=ai_settings.local_only,
    )

    # Reglages de temps de reponse, propres au moteur local : garder le modele
    # en memoire, plafonner la generation, borner la fenetre de contexte. Les
    # fournisseurs externes n'ont pas ces notions -- les leur passer
    # leverait une TypeError, et un **kwargs complaisant les avalerait en
    # silence, ce qui est pire : on ne saurait pas que le reglage est inerte.
    options_locales = {}
    if ai_settings.default_provider == 'local':
        options_locales = {
            'keep_alive_minutes': ai_settings.keep_alive_minutes,
            'max_output_tokens': ai_settings.max_output_tokens,
            'context_window_tokens': ai_settings.context_window_tokens,
        }

    try:
        response = provider.generate(
            messages=messages,
            model=ai_settings.default_model,
            temperature=ai_settings.temperature,
            **options_locales,
        )
    except AIProviderError as exc:
        # Le moteur local absent est LE cas d'echec courant, et « connexion
        # impossible » ne dit pas quoi faire. On nomme le remede.
        if ai_settings.default_provider == 'local':
            raise RuntimeError(
                f"{exc} Le moteur local ne répond pas. Sur l'appliance : "
                '/opt/orion/scripts/orion-ai.sh status, puis '
                '/opt/orion/scripts/orion-ai.sh install si besoin.'
            ) from exc
        raise

    assistant_content = redact_sensitive_text(response['content'])

    assistant_msg = OrionAIMessage.objects.create(
        conversation=conversation,
        role='assistant',
        content=assistant_content,
        provider=response['provider'],
        model=response['model'],
        token_input=response.get('token_input', 0),
        token_output=response.get('token_output', 0),
        raw_payload=redact_payload(_avec_mesures(response)),
    )

    update_fields = ['updated_at']
    if conversation.title == 'Nouvelle conversation':
        conversation.title = clean_prompt[:80]
        update_fields.append('title')
    conversation.updated_at = timezone.now()
    conversation.save(update_fields=update_fields)

    if ai_settings.log_conversations:
        audit_ai_event(
            company=company,
            user=user,
            event_type='chat_message',
            title='Message IA',
            description=clean_prompt[:220],
            payload={
                'conversation_id': conversation.id,
                'provider': response['provider'],
                'model': response['model'],
            },
            request=request,
        )

    return {
        'conversation_id': conversation.id,
        'message_id': assistant_msg.id,
        'answer': assistant_msg.content,
        'provider': response['provider'],
        'model': response['model'],
    }


def envoyer_message_en_flux(*, request, prompt, conversation_id=None,
                            context_module='', brand_key=''):
    """Même échange que send_ai_message, rendu au fur et à mesure.

    Le temps total ne change pas : ce qui change est le temps avant le PREMIER
    mot. Sans flux, l'utilisateur attend la réponse entière — vingt ou trente
    secondes pendant lesquelles rien ne bouge, et pendant lesquelles il ne
    peut pas distinguer un assistant qui réfléchit d'un assistant en panne.

    Produit des dictionnaires, à sérialiser par la vue :
      {'delta': '...'} pour chaque morceau de texte,
      puis {'fin': True, 'conversation_id': …, 'message_id': …, 'mesures': …}.

    Volontairement PAS décoré de @transaction.atomic, contrairement à
    send_ai_message : la génération dure des dizaines de secondes, et tenir
    une transaction ouverte pendant tout ce temps bloquerait des lignes et
    consommerait une connexion pour rien. Les écritures sont donc faites en
    deux temps courts — la question avant, la réponse après.
    """
    user = request.user
    company = get_request_company(request)

    if not can_use_ai(user):
        raise PermissionError("Vous n'avez pas accès à l'assistant IA.")

    ai_settings = get_ai_settings(company)

    if not ai_settings.ai_enabled or not getattr(settings, 'ORION_AI_ENABLED', False):
        raise RuntimeError(
            "L'assistant IA est désactivé. Activez ORION_AI_ENABLED dans la "
            'configuration.'
        )

    valid, error_message = validate_user_prompt(prompt)
    if not valid:
        raise ValueError(error_message)

    if len(prompt) > ai_settings.max_input_chars:
        raise ValueError(
            f'Message trop long (max {ai_settings.max_input_chars} caractères).'
        )

    clean_prompt = (
        redact_sensitive_text(prompt) if ai_settings.redact_sensitive_data
        else prompt
    )

    provider = get_ai_provider(
        ai_settings.default_provider,
        local_only=ai_settings.local_only,
    )

    # Seul le moteur local sait diffuser ici. Pour les autres, on rend la
    # réponse d'un bloc plutôt que d'échouer : le flux est un confort, et son
    # absence ne doit pas priver de l'assistant.
    if not hasattr(provider, 'generate_stream'):
        resultat = send_ai_message(
            request=request, prompt=prompt, conversation_id=conversation_id,
            context_module=context_module, brand_key=brand_key,
        )
        yield {'delta': resultat['answer']}
        yield {
            'fin': True,
            'conversation_id': resultat['conversation_id'],
            'message_id': resultat['message_id'],
            'provider': resultat['provider'],
            'model': resultat['model'],
            'mesures': {},
        }
        return

    with transaction.atomic():
        conversation = create_or_get_conversation(
            company=company,
            user=user,
            conversation_id=conversation_id,
            context_module=context_module,
            brand_key=brand_key,
        )
        message_utilisateur = OrionAIMessage.objects.create(
            conversation=conversation,
            role='user',
            content=clean_prompt,
        )

    messages = build_messages_for_provider(
        conversation,
        ai_settings,
        clean_prompt,
        company=company,
        user=user,
        brand_key=brand_key,
        exclure_message_id=message_utilisateur.pk,
    )

    morceaux = []
    dernier = {}
    for evenement in provider.generate_stream(
        messages=messages,
        model=ai_settings.default_model,
        temperature=ai_settings.temperature,
        keep_alive_minutes=ai_settings.keep_alive_minutes,
        max_output_tokens=ai_settings.max_output_tokens,
        context_window_tokens=ai_settings.context_window_tokens,
    ):
        if evenement.get('fin'):
            dernier = evenement
            break
        texte = evenement.get('delta') or ''
        if texte:
            morceaux.append(texte)
            yield {'delta': texte}

    # La redaction s'applique au texte COMPLET, et non morceau par morceau :
    # un secret coupe en deux jetons ne serait reconnu par aucun des deux.
    # C'est pourquoi le texte diffusé est brut et le texte CONSERVÉ expurgé --
    # la diffusion va à l'auteur de la question, qui a déjà ce qu'il a tapé.
    contenu = redact_sensitive_text(''.join(morceaux))

    with transaction.atomic():
        assistant_msg = OrionAIMessage.objects.create(
            conversation=conversation,
            role='assistant',
            content=contenu,
            provider=dernier.get('provider', 'local'),
            model=dernier.get('model', ai_settings.default_model),
            token_input=dernier.get('token_input', 0),
            token_output=dernier.get('token_output', 0),
            raw_payload=redact_payload(_avec_mesures(dernier)),
        )

        update_fields = ['updated_at']
        if conversation.title == 'Nouvelle conversation':
            conversation.title = clean_prompt[:80]
            update_fields.append('title')
        conversation.updated_at = timezone.now()
        conversation.save(update_fields=update_fields)

    if ai_settings.log_conversations:
        audit_ai_event(
            company=company,
            user=user,
            event_type='chat_message',
            title='Message IA (flux)',
            description=clean_prompt[:220],
            payload={
                'conversation_id': conversation.id,
                'provider': dernier.get('provider', 'local'),
                'model': dernier.get('model', ai_settings.default_model),
            },
            request=request,
        )

    yield {
        'fin': True,
        'conversation_id': conversation.id,
        'message_id': assistant_msg.id,
        'provider': dernier.get('provider', 'local'),
        'model': dernier.get('model', ai_settings.default_model),
        'mesures': dernier.get('timings') or {},
    }


def supprimer_conversation(*, request, conversation_id):
    """Supprime une conversation et tout ce qu'elle contient.

    Suppression REELLE, et non un statut « supprimee » : une conversation avec
    Orion porte des devis, des noms de clients, des montants. La garder
    indefiniment en base, invisible mais intacte, ne serait pas une
    suppression -- et c'est ce que le statut `deleted` du modele laissait
    croire, alors que rien ne le posait jamais. Les messages, appels d'outils
    et actions proposees partent en cascade.

    Deux garde-fous, tous deux necessaires :

      - l'entreprise ET l'utilisateur sont filtres. Filtrer la seule
        entreprise laisserait un collegue supprimer les conversations d'un
        autre en devinant un identifiant ; filtrer le seul utilisateur
        laisserait passer un identifiant d'une autre entreprise ;
      - une action PROPOSEE encore en attente est comptee et annoncee.
        Supprimer la conversation qui l'a proposee l'abandonne, ce qui est
        legitime -- mais doit etre dit, et non subi.

    La trace d'audit garde le geste sans garder le contenu.
    """
    user = request.user
    company = get_request_company(request)

    if not can_use_ai(user):
        raise PermissionError("Vous n'avez pas accès à l'assistant IA.")

    conversation = (
        OrionAIConversation.objects
        .filter(id=conversation_id, company=company, user=user)
        .first()
    )
    if conversation is None:
        raise OrionAIConversation.DoesNotExist(
            'Conversation introuvable, ou elle ne vous appartient pas.'
        )

    # Releve AVANT la suppression : apres, il n'y a plus rien a compter.
    titre = conversation.title
    nombre_messages = conversation.messages.count()
    actions_en_attente = conversation.proposed_actions.filter(
        status='pending').count()

    with transaction.atomic():
        conversation.delete()
        audit_ai_event(
            company=company,
            user=user,
            event_type='conversation_deleted',
            title='Conversation supprimée',
            description=titre[:220],
            payload={
                'conversation_id': conversation_id,
                'messages': nombre_messages,
                'actions_en_attente_abandonnees': actions_en_attente,
            },
            request=request,
        )

    return {
        'titre': titre,
        'messages': nombre_messages,
        'actions_en_attente': actions_en_attente,
    }


def supprimer_toutes_les_conversations(*, request):
    """Supprime toutes les conversations de CET utilisateur dans CETTE entreprise.

    Volontairement limitee a ses propres conversations, meme pour un
    administrateur : « effacer mon historique » est une demande courante,
    « effacer celui de tout le monde » en est une autre, et la confondre avec
    la premiere serait un accident irreversible.
    """
    user = request.user
    company = get_request_company(request)

    if not can_use_ai(user):
        raise PermissionError("Vous n'avez pas accès à l'assistant IA.")

    conversations = OrionAIConversation.objects.filter(
        company=company, user=user)

    nombre = conversations.count()
    if not nombre:
        return {'conversations': 0, 'messages': 0}

    nombre_messages = OrionAIMessage.objects.filter(
        conversation__in=conversations).count()

    with transaction.atomic():
        conversations.delete()
        audit_ai_event(
            company=company,
            user=user,
            event_type='conversation_deleted',
            title='Historique IA effacé',
            description=f'{nombre} conversation(s) supprimée(s).',
            payload={
                'conversations': nombre,
                'messages': nombre_messages,
            },
            request=request,
        )

    return {'conversations': nombre, 'messages': nombre_messages}


def propose_ai_action(*, conversation, title, description, action_code, arguments):
    action = OrionAIProposedAction.objects.create(
        conversation=conversation,
        title=title,
        description=description,
        action_code=action_code,
        arguments=redact_payload(arguments),
        is_write_action=is_write_action(action_code),
        is_dangerous_action=is_dangerous_action(action_code),
        requires_confirmation=True,
    )

    audit_ai_event(
        company=conversation.company,
        user=conversation.user,
        event_type='action_proposed',
        title=f'Action proposée : {title}',
        payload={'action_id': action.id, 'action_code': action_code},
    )

    return action


@transaction.atomic
def execute_ai_read_tool(*, conversation, user, tool_name, arguments):
    tool = get_ai_tool(tool_name)

    if not tool:
        raise RuntimeError(f'Outil IA inconnu : {tool_name}')

    if tool['is_write_action']:
        raise RuntimeError("Les outils d'écriture doivent passer par une action confirmée.")

    company = conversation.company

    tool_call = OrionAIToolCall.objects.create(
        conversation=conversation,
        tool_name=tool_name,
        arguments=redact_payload(arguments),
        status='running',
        is_write_action=False,
        is_dangerous_action=False,
        executed_by=user,
    )

    try:
        result = tool['func'](company=company, user=user, **arguments)
        tool_call.status = 'success'
        tool_call.result = redact_payload(result)
        tool_call.finished_at = timezone.now()
        tool_call.save()
        return result
    except Exception as exc:
        tool_call.status = 'failed'
        tool_call.error_message = str(exc)
        tool_call.finished_at = timezone.now()
        tool_call.save()
        raise
