"""Reprend l'historique de l'ancien module `orion_assistant`.

Deux assistants coexistaient : `orion_assistant` (`/assistant/`, deux modèles)
et `orion_ai` (`/ia/`, sept modèles). Le second est un surensemble strict du
premier — mêmes conversations et mêmes messages, plus les appels d'outils, les
actions proposées, la mémoire, le journal d'audit et les réglages. Deux entrées
« Assistant Orion » figuraient au menu, menant à deux historiques séparés sans
que rien n'explique la différence.

Le doublon est donc supprimé (voir orion_assistant.0002), mais les
conversations déjà tenues ne doivent pas disparaître avec lui : elles sont
reprises ici, avant que les anciennes tables ne soient retirées.

Reprise idempotente : chaque conversation importée porte dans ses métadonnées
la référence de son origine, et une seconde exécution ne la recopie pas.
"""

from django.db import migrations

MARQUE = 'repris_de_orion_assistant'


def reprendre(apps, schema_editor):
    try:
        AncienneConversation = apps.get_model(
            'orion_assistant', 'AssistantConversation')
        AncienMessage = apps.get_model('orion_assistant', 'AssistantMessage')
    except LookupError:
        # Installation neuve : l'ancien module n'a jamais existé, il n'y a rien
        # à reprendre. Ce n'est pas une anomalie.
        return

    Conversation = apps.get_model('orion_ai', 'OrionAIConversation')
    Message = apps.get_model('orion_ai', 'OrionAIMessage')

    deja_reprises = {
        conversation.metadata.get(MARQUE)
        for conversation in Conversation.objects.all()
        if isinstance(conversation.metadata, dict)
        and conversation.metadata.get(MARQUE)
    }

    for ancienne in AncienneConversation.objects.all().order_by('id'):
        if ancienne.id in deja_reprises:
            continue

        nouvelle = Conversation.objects.create(
            company_id=ancienne.company_id,
            user_id=ancienne.user_id,
            title=ancienne.title or 'Conversation reprise',
            status='archived' if ancienne.is_archived else 'active',
            context_module=ancienne.context_module or '',
            metadata={MARQUE: ancienne.id},
        )
        # created_at/updated_at portent auto_now_add et auto_now : une
        # affectation à la création serait écrasée. Un update() ne passe pas par
        # save(), et conserve donc les dates d'origine — sans quoi tout
        # l'historique paraîtrait daté du jour de la migration.
        Conversation.objects.filter(pk=nouvelle.pk).update(
            created_at=ancienne.created_at,
            updated_at=ancienne.updated_at,
        )

        for ancien_message in AncienMessage.objects.filter(
                conversation_id=ancienne.id).order_by('created_at', 'id'):
            message = Message.objects.create(
                conversation_id=nouvelle.pk,
                role=ancien_message.role,
                content=ancien_message.content,
                # `tokens_used` ne distinguait pas entrée et sortie. Le porter
                # en token_output seul fausserait les totaux ; il est conservé
                # tel quel dans la charge brute, où son sens reste exact.
                raw_payload={
                    MARQUE: ancien_message.id,
                    'tokens_used': ancien_message.tokens_used,
                    'metadata': ancien_message.metadata or {},
                },
            )
            Message.objects.filter(pk=message.pk).update(
                created_at=ancien_message.created_at,
            )


def oublier(apps, schema_editor):
    """Retire uniquement ce que cette migration a créé."""
    Conversation = apps.get_model('orion_ai', 'OrionAIConversation')
    for conversation in list(Conversation.objects.all()):
        if isinstance(conversation.metadata, dict) \
                and conversation.metadata.get(MARQUE):
            conversation.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('orion_ai', '0003_basculer_les_reglages_existants_en_local'),
        ('orion_assistant', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(reprendre, oublier),
    ]
