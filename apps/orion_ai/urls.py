from django.urls import path

from apps.orion_ai import api
from apps.orion_ai import views

app_name = 'orion_ai'

urlpatterns = [
    # ERP UI
    path('erp/assistant/', views.assistant_dashboard, name='assistant_dashboard'),
    path('erp/assistant/conversations/', views.conversations_view, name='conversations'),
    path('erp/assistant/conversations/<int:pk>/', views.conversation_detail_view, name='conversation_detail'),
    path('erp/assistant/memoire/', views.ai_memory_view, name='memory'),
    path('erp/assistant/parametres/', views.ai_user_settings_view, name='user_settings'),

    # Super Admin UI
    path('orion-admin/ai/settings/', views.ai_settings_view, name='admin_ai_settings'),
    path('orion-admin/ai/audit/', views.ai_audit_view, name='admin_ai_audit'),

    # API REST
    path('api/v1/orion-ai/chat/', api.ai_chat_api, name='api_chat'),
    path('api/v1/orion-ai/conversations/', api.ai_conversations_api, name='api_conversations'),
    path('api/v1/orion-ai/conversations/<int:pk>/', api.ai_conversation_detail_api, name='api_conversation_detail'),
    path('api/v1/orion-ai/actions/', api.ai_proposed_actions_api, name='api_actions'),
    path('api/v1/orion-ai/actions/<int:pk>/confirm/', api.ai_confirm_action_api, name='api_confirm_action'),
    path('api/v1/orion-ai/actions/<int:pk>/cancel/', api.ai_cancel_action_api, name='api_cancel_action'),
    path('api/v1/orion-ai/settings/public/', api.ai_public_settings_api, name='api_public_settings'),
]
