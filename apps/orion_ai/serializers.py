from rest_framework import serializers

from apps.orion_ai.models import (
    OrionAIConversation,
    OrionAIMessage,
    OrionAIProposedAction,
    OrionAISettings,
)


class OrionAIMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrionAIMessage
        fields = ['id', 'role', 'content', 'provider', 'model', 'created_at']


class OrionAIConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrionAIConversation
        fields = ['id', 'title', 'context_module', 'brand_key', 'status', 'created_at', 'updated_at']


class OrionAIConversationDetailSerializer(serializers.ModelSerializer):
    messages = OrionAIMessageSerializer(many=True)

    class Meta:
        model = OrionAIConversation
        fields = ['id', 'title', 'context_module', 'brand_key', 'status', 'messages', 'created_at', 'updated_at']


class OrionAIChatRequestSerializer(serializers.Serializer):
    prompt = serializers.CharField(max_length=50000)
    conversation_id = serializers.IntegerField(required=False, allow_null=True)
    context_module = serializers.CharField(required=False, allow_blank=True, default='')
    brand_key = serializers.CharField(required=False, allow_blank=True, default='')


class OrionAIProposedActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrionAIProposedAction
        fields = [
            'id', 'title', 'description', 'action_code', 'arguments',
            'status', 'is_write_action', 'is_dangerous_action',
            'requires_confirmation', 'created_at',
        ]
