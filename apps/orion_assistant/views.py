from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from .models import AssistantConversation
from .services import (
    start_conversation, add_message, get_user_conversations,
    get_conversation_history, archive_conversation, build_context_prompt,
    generate_ai_reply,
)


@login_required
def conversation_list(request):
    company = request.current_company
    if not company:
        return redirect('core:dashboard')
    conversations = get_user_conversations(company, request.user)
    return render(request, 'orion_assistant/conversation_list.html', {
        'page_title': 'Orion — Assistant IA',
        'conversations': conversations,
    })


@login_required
def conversation_detail(request, pk):
    company = request.current_company
    conv = get_object_or_404(AssistantConversation, pk=pk, company=company, user=request.user)
    history = get_conversation_history(conv)
    return render(request, 'orion_assistant/conversation_detail.html', {
        'page_title': conv.title or 'Conversation',
        'conversation': conv, 'history': history,
    })


@login_required
@require_POST
def new_conversation(request):
    company = request.current_company
    if not company:
        return redirect('core:dashboard')
    context_module = request.POST.get('context_module', '')
    title = request.POST.get('title', '')
    conv = start_conversation(company, request.user, title=title, context_module=context_module)
    system_prompt = build_context_prompt(company, context_module)
    add_message(conv, 'system', system_prompt)
    return redirect('orion_assistant:detail', pk=conv.pk)


@login_required
@require_POST
def send_message(request, pk):
    company = request.current_company
    conv = get_object_or_404(AssistantConversation, pk=pk, company=company, user=request.user)
    content = request.POST.get('message', '').strip()
    if content:
        add_message(conv, 'user', content)
        reply = generate_ai_reply(conv, content)
        add_message(conv, 'assistant', reply['content'], tokens_used=reply.get('tokens', 0))
    return redirect('orion_assistant:detail', pk=pk)


@login_required
@require_POST
def archive_conv(request, pk):
    company = request.current_company
    conv = get_object_or_404(AssistantConversation, pk=pk, company=company, user=request.user)
    archive_conversation(conv)
    return redirect('orion_assistant:list')
