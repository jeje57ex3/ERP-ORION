from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from apps.orion_ai.actions import cancel_ai_action, confirm_and_execute_action
from apps.orion_ai.models import OrionAIConversation, OrionAIProposedAction
from apps.orion_ai.serializers import (
    OrionAIChatRequestSerializer,
    OrionAIConversationDetailSerializer,
    OrionAIConversationSerializer,
    OrionAIProposedActionSerializer,
)
from apps.orion_ai.services import send_ai_message, get_request_company


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ai_chat_api(request):
    serializer = OrionAIChatRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    try:
        result = send_ai_message(
            request=request,
            prompt=data['prompt'],
            conversation_id=data.get('conversation_id'),
            context_module=data.get('context_module', ''),
            brand_key=data.get('brand_key', ''),
        )
        return Response(result)
    except PermissionError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)
    except (ValueError, RuntimeError) as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as exc:
        return Response({'error': f'Erreur IA : {exc}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ai_conversations_api(request):
    company = get_request_company(request)
    conversations = OrionAIConversation.objects.filter(
        company=company,
        user=request.user,
        status='active',
    )
    return Response(OrionAIConversationSerializer(conversations, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ai_conversation_detail_api(request, pk):
    company = get_request_company(request)
    try:
        conversation = OrionAIConversation.objects.get(id=pk, company=company, user=request.user)
    except OrionAIConversation.DoesNotExist:
        return Response({'error': 'Conversation introuvable.'}, status=status.HTTP_404_NOT_FOUND)
    return Response(OrionAIConversationDetailSerializer(conversation).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ai_proposed_actions_api(request):
    company = get_request_company(request)
    actions = OrionAIProposedAction.objects.filter(
        conversation__company=company,
        conversation__user=request.user,
        status='pending',
    )
    return Response(OrionAIProposedActionSerializer(actions, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ai_confirm_action_api(request, pk):
    company = get_request_company(request)
    try:
        action = OrionAIProposedAction.objects.get(id=pk, conversation__company=company)
    except OrionAIProposedAction.DoesNotExist:
        return Response({'error': 'Action introuvable.'}, status=status.HTTP_404_NOT_FOUND)

    try:
        action = confirm_and_execute_action(action=action, user=request.user, request=request)
        return Response(OrionAIProposedActionSerializer(action).data)
    except PermissionError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ai_cancel_action_api(request, pk):
    company = get_request_company(request)
    try:
        action = OrionAIProposedAction.objects.get(id=pk, conversation__company=company)
    except OrionAIProposedAction.DoesNotExist:
        return Response({'error': 'Action introuvable.'}, status=status.HTTP_404_NOT_FOUND)

    try:
        action = cancel_ai_action(action=action, user=request.user, request=request)
        return Response(OrionAIProposedActionSerializer(action).data)
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ai_public_settings_api(request):
    from apps.orion_ai.services import get_ai_settings
    company = get_request_company(request)
    ai_settings = get_ai_settings(company)
    return Response({
        'ai_enabled': ai_settings.ai_enabled,
        'ai_name': ai_settings.ai_name,
        'allow_tools': ai_settings.allow_tools,
        'provider': ai_settings.default_provider,
        'model': ai_settings.default_model,
    })
