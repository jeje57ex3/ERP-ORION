from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.orion_ai.models import (
    OrionAIAuditLog,
    OrionAIConversation,
    OrionAIMemory,
    OrionAIProposedAction,
    OrionAISettings,
)
from apps.orion_ai.permissions import can_use_ai, user_is_super_admin
from apps.orion_ai.selectors import get_ai_settings, get_audit_logs


def get_request_company(request):
    return getattr(request, 'active_company', None) or getattr(request, 'company', None)


@login_required
def assistant_dashboard(request):
    if not can_use_ai(request.user):
        messages.error(request, "Vous n'avez pas accès à l'assistant IA.")
        return redirect('core:dashboard')

    company = get_request_company(request)
    ai_settings = get_ai_settings(company)

    recent_conversations = OrionAIConversation.objects.filter(
        company=company,
        user=request.user,
        status='active',
    )[:5]

    pending_actions = OrionAIProposedAction.objects.filter(
        conversation__company=company,
        conversation__user=request.user,
        status='pending',
    )[:10]

    # D'ou la question est posee. L'icone de la barre du haut transmet le nom
    # de route ; on le traduit en libelle de menu, le seul qui ait du sens
    # pour l'utilisateur comme pour le modele.
    from apps.orion_ai.knowledge import page_depuis_route
    module_courant = page_depuis_route(
        request.GET.get('module', ''), user=request.user, company=company,
    )

    return render(request, 'orion_ai/dashboard.html', {
        'ai_settings': ai_settings,
        'module_courant': module_courant,
        'retour_url': request.GET.get('depuis', ''),
        'recent_conversations': recent_conversations,
        'pending_actions': pending_actions,
        'page_title': 'Assistant Orion IA',
    })


@login_required
def conversations_view(request):
    if not can_use_ai(request.user):
        return redirect('core:dashboard')

    company = get_request_company(request)

    conversations = OrionAIConversation.objects.filter(
        company=company,
        user=request.user,
    ).exclude(status='deleted')

    return render(request, 'orion_ai/conversations.html', {
        'conversations': conversations,
        'page_title': 'Conversations IA',
    })


@login_required
def conversation_detail_view(request, pk):
    if not can_use_ai(request.user):
        return redirect('core:dashboard')

    company = get_request_company(request)
    conversation = get_object_or_404(
        OrionAIConversation,
        id=pk,
        company=company,
        user=request.user,
    )

    conversation_messages = conversation.messages.order_by('created_at')
    pending_actions = conversation.proposed_actions.filter(status='pending')

    return render(request, 'orion_ai/conversation_detail.html', {
        'conversation': conversation,
        'conversation_messages': conversation_messages,
        'pending_actions': pending_actions,
        'page_title': conversation.title,
    })


@login_required
def ai_memory_view(request):
    if not can_use_ai(request.user):
        return redirect('core:dashboard')

    company = get_request_company(request)

    memories = OrionAIMemory.objects.filter(
        is_active=True,
        company=company,
    )

    if request.method == 'POST' and request.POST.get('action') == 'delete':
        memory_id = request.POST.get('memory_id')
        OrionAIMemory.objects.filter(id=memory_id, company=company).update(is_active=False)
        messages.success(request, 'Entrée mémoire désactivée.')
        return redirect('orion_ai:memory')

    return render(request, 'orion_ai/memory.html', {
        'memories': memories,
        'page_title': 'Mémoire IA',
    })


@login_required
def ai_user_settings_view(request):
    if not can_use_ai(request.user):
        return redirect('core:dashboard')

    company = get_request_company(request)
    ai_settings = get_ai_settings(company)

    return render(request, 'orion_ai/settings.html', {
        'ai_settings': ai_settings,
        'page_title': 'Paramètres IA',
    })


@login_required
def ai_settings_view(request):
    if not user_is_super_admin(request.user):
        messages.error(request, 'Accès réservé au Super Admin.')
        return redirect('core:dashboard')

    ai_settings = OrionAISettings.get_global()

    if request.method == 'POST':
        ai_settings.ai_enabled = request.POST.get('ai_enabled') == 'on'

        # Les valeurs de repli etaient codees en dur sur « openai » et
        # « gpt-4.1-mini » : un champ absent du formulaire REVENAIT donc
        # silencieusement a un fournisseur externe, et le verrou local
        # refusait ensuite chaque requete. Le repli est desormais la valeur
        # courante -- un champ manquant conserve ce qui est en place au lieu
        # de le remplacer par autre chose.
        ai_settings.local_only = request.POST.get('local_only') == 'on'
        ai_settings.default_provider = request.POST.get(
            'default_provider', ai_settings.default_provider,
        )
        ai_settings.default_model = request.POST.get(
            'default_model', ai_settings.default_model,
        )
        ai_settings.allow_tools = request.POST.get('allow_tools') == 'on'
        ai_settings.allow_erp_read_tools = request.POST.get('allow_erp_read_tools') == 'on'
        ai_settings.allow_erp_write_tools = request.POST.get('allow_erp_write_tools') == 'on'
        ai_settings.allow_dangerous_actions = request.POST.get('allow_dangerous_actions') == 'on'
        ai_settings.log_conversations = request.POST.get('log_conversations') == 'on'
        ai_settings.redact_sensitive_data = request.POST.get('redact_sensitive_data') == 'on'
        ai_settings.ai_name = request.POST.get('ai_name', ai_settings.ai_name)
        ai_settings.system_prompt_extra = request.POST.get('system_prompt_extra', '')
        from apps.orion_ai.providers import FOURNISSEURS_EXTERNES
        if ai_settings.local_only and ai_settings.default_provider in FOURNISSEURS_EXTERNES:
            messages.error(
                request,
                f'Le fournisseur « {ai_settings.default_provider} » est externe, '
                'alors que le traitement local uniquement est demandé. '
                'Choisissez le fournisseur local, ou levez ce verrou en '
                "connaissance de cause : les données de l'entreprise "
                'partiraient alors chez un tiers.',
            )
            return redirect('orion_ai:admin_ai_settings')

        ai_settings.updated_by = request.user
        ai_settings.save()

        from apps.orion_ai.services import audit_ai_event
        audit_ai_event(
            company=None,
            user=request.user,
            event_type='settings_changed',
            title='Paramètres IA globaux modifiés',
            request=request,
        )

        messages.success(request, 'Paramètres IA enregistrés.')
        return redirect('orion_ai:admin_ai_settings')

    from apps.orion_ai.tool_registry import get_available_ai_tools
    tools = get_available_ai_tools()

    return render(request, 'orion_ai/admin_settings.html', {
        'ai_settings': ai_settings,
        'available_tools': tools,
        'page_title': 'Paramètres IA — Super Admin',
    })


@login_required
def ai_audit_view(request):
    if not user_is_super_admin(request.user):
        messages.error(request, 'Accès réservé au Super Admin.')
        return redirect('core:dashboard')

    logs = get_audit_logs(limit=200)

    event_filter = request.GET.get('event', '')
    if event_filter:
        logs = logs.filter(event_type=event_filter)

    return render(request, 'orion_ai/admin_audit.html', {
        'logs': logs,
        'event_filter': event_filter,
        'event_choices': OrionAIAuditLog.EVENT_CHOICES,
        'page_title': 'Audit IA — Super Admin',
    })
