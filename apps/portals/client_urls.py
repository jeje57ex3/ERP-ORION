from django.urls import path
from . import client_views as v
from . import views_signup as sv

app_name = 'client_portal'

urlpatterns = [
    # ── Auth ──────────────────────────────────────────────────────────────────
    path('', v.dashboard, name='dashboard'),
    path('connexion/', v.portal_login, name='login'),
    path('deconnexion/', v.portal_logout, name='logout'),

    # ── Inscription publique ──────────────────────────────────────────────────
    path('inscription/', sv.ClientRegisterView.as_view(), name='register'),
    path('inscription/succes/', sv.ClientRegisterSuccessView.as_view(), name='register_success'),
    path('verification-email/<str:token>/', sv.ClientVerifyEmailView.as_view(), name='verify_email'),
    path('chantiers/', v.project_list, name='project_list'),
    path('chantiers/<int:pk>/', v.project_detail, name='project_detail'),
    path('chantiers/<int:pk>/planning/', v.project_planning, name='project_planning'),
    path('chantiers/<int:pk>/documents/', v.project_documents, name='project_documents'),
    path('chantiers/<int:pk>/messages/', v.project_messages, name='project_messages'),
    path('chantiers/<int:pk>/messages/<int:conv_pk>/', v.conversation_detail, name='conversation_detail'),
    path('chantiers/<int:pk>/reserves/', v.project_reservations, name='project_reservations'),
    path('chantiers/<int:pk>/modifications/', v.project_changes, name='project_changes'),
    path('chantiers/<int:pk>/heures/', v.project_hours, name='project_hours'),
    path('chantiers/<int:pk>/equipe/', v.project_team, name='project_team'),
    path('notifications/', v.notifications, name='notifications'),
]
