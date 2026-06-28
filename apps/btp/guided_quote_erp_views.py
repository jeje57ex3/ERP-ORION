"""
Vues ERP pour gérer les demandes guidées, la bibliothèque de prix
et le tableau de bord responsable chantier.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from django.http import JsonResponse
from django.utils import timezone
from .models import (
    GuidedQuoteRequest, GuidedQuoteEstimate, GuidedQuoteEstimateItem,
    ElectricityPriceLibrary, BTPProject, ClientConversation, ClientMessage,
    TimeEntry, SiteAssignment, ProjectReservation, ClientChangeRequest,
    ClientNotification, ProjectDocument,
)


def _company(request):
    return request.current_company


# ─── DASHBOARD RESPONSABLE ────────────────────────────────────────────────────

@login_required
def site_manager_dashboard(request):
    company = _company(request)
    kpis = {
        'new_quotes': GuidedQuoteRequest.objects.filter(company=company, status='new').count(),
        'active_projects': BTPProject.objects.filter(company=company, status='in_progress').count(),
        'unread_messages': ClientConversation.objects.filter(
            project__company=company, unread_by_manager__gt=0
        ).count(),
        'open_reservations': ProjectReservation.objects.filter(
            project__company=company, status__in=['new', 'analyzing', 'planned']
        ).count(),
    }
    recent_quotes = GuidedQuoteRequest.objects.filter(company=company).order_by('-created_at')[:5]
    urgent_quotes = GuidedQuoteRequest.objects.filter(
        company=company, request_type='depannage', status='new'
    ).order_by('-created_at')[:5]

    return render(request, 'btp/site_manager_dashboard.html', {
        'kpis': kpis,
        'recent_quotes': recent_quotes,
        'urgent_quotes': urgent_quotes,
        'today': timezone.now().date(),
    })


# ─── DEMANDES GUIDÉES ─────────────────────────────────────────────────────────

@login_required
def guided_quote_list(request):
    company = _company(request)
    qs = GuidedQuoteRequest.objects.filter(company=company).order_by('-created_at')

    status_filter = request.GET.get('status', '')
    type_filter = request.GET.get('type', '')
    urgency_filter = request.GET.get('urgency', '')
    q = request.GET.get('q', '')

    if status_filter:
        qs = qs.filter(status=status_filter)
    if type_filter:
        qs = qs.filter(request_type=type_filter)
    if urgency_filter:
        qs = qs.filter(urgency=urgency_filter)
    if q:
        qs = qs.filter(Q(client_last_name__icontains=q) | Q(client_email__icontains=q) | Q(reference__icontains=q))

    stats = {
        'total': GuidedQuoteRequest.objects.filter(company=company).count(),
        'new': GuidedQuoteRequest.objects.filter(company=company, status='new').count(),
        'in_progress': GuidedQuoteRequest.objects.filter(
            company=company, status__in=['to_analyze', 'complement_asked', 'estimate_sent', 'quote_created']
        ).count(),
        'converted': GuidedQuoteRequest.objects.filter(company=company, status='converted').count(),
    }

    return render(request, 'btp/guided_quote_list.html', {
        'quotes': qs,
        'stats': stats,
        'status_filter': status_filter, 'type_filter': type_filter,
        'urgency_filter': urgency_filter, 'q': q,
        'status_choices': GuidedQuoteRequest.STATUS_CHOICES,
        'type_choices': GuidedQuoteRequest.REQUEST_TYPE_CHOICES,
    })


@login_required
def guided_quote_detail(request, pk):
    company = _company(request)
    quote_request = get_object_or_404(GuidedQuoteRequest, pk=pk, company=company)
    estimate = getattr(quote_request, 'estimate', None)
    photos = quote_request.photos.all()
    documents = quote_request.documents.all()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'update_status':
            quote_request.status = request.POST.get('status', quote_request.status)
            quote_request.internal_notes = request.POST.get('internal_notes', quote_request.internal_notes)
            quote_request.save()
            messages.success(request, 'Demande mise à jour.')
        elif action == 'assign':
            from django.contrib.auth.models import User
            user_pk = request.POST.get('user_pk')
            if user_pk:
                try:
                    quote_request.assigned_to = User.objects.get(pk=user_pk)
                    quote_request.save()
                    messages.success(request, 'Responsable affecté.')
                except User.DoesNotExist:
                    pass
        elif action == 'create_quote':
            from .models import BTPQuote
            # Créer un brouillon de devis BTP
            quote = BTPQuote.objects.create(
                company=company,
                customer_id=quote_request.crm_customer_id,
                subject=f'Devis suite demande {quote_request.reference}',
                status='draft',
                created_by=request.user,
            )
            quote_request.btp_quote = quote
            quote_request.status = 'quote_created'
            quote_request.save()
            messages.success(request, f'Devis BTP {quote.number or "DEV"} créé.')
        elif action == 'create_project':
            project = BTPProject.objects.create(
                company=company,
                name=f'Chantier {quote_request.reference}',
                address=f'{quote_request.address}, {quote_request.zip_code} {quote_request.city}',
                city=quote_request.city,
                zip_code=quote_request.zip_code,
                status='study',
                project_manager=request.user,
            )
            quote_request.btp_project = project
            quote_request.status = 'converted'
            quote_request.save()
            messages.success(request, f'Chantier {project.name} créé.')
        return redirect('btp:guided_quote_detail', pk=pk)

    return render(request, 'btp/guided_quote_detail.html', {
        'quote': quote_request,
        'estimate': estimate,
        'photos': photos,
        'documents': documents,
        'status_choices': GuidedQuoteRequest.STATUS_CHOICES,
    })


# ─── BIBLIOTHÈQUE DE PRIX ─────────────────────────────────────────────────────

@login_required
def price_library_list(request):
    company = _company(request)
    qs = ElectricityPriceLibrary.objects.filter(company=company)

    cat_filter = request.GET.get('category', '')
    q = request.GET.get('q', '')
    if cat_filter:
        qs = qs.filter(category=cat_filter)
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q))

    return render(request, 'btp/price_library_list.html', {
        'items': qs,
        'cat_filter': cat_filter,
        'q': q,
        'category_choices': ElectricityPriceLibrary.CATEGORY_CHOICES,
    })


@login_required
def price_library_create(request):
    company = _company(request)
    if request.method == 'POST':
        item = ElectricityPriceLibrary(company=company)
        item.code = request.POST.get('code', '')
        item.name = request.POST.get('name', '')
        item.category = request.POST.get('category', 'autre')
        item.description = request.POST.get('description', '')
        item.unit = request.POST.get('unit', 'u')
        item.price_min = request.POST.get('price_min', 0) or 0
        item.price_avg = request.POST.get('price_avg', 0) or 0
        item.price_max = request.POST.get('price_max', 0) or 0
        item.duration_hours = request.POST.get('duration_hours', 0) or 0
        item.complexity = request.POST.get('complexity', 'medium')
        item.save()
        messages.success(request, f'Poste « {item.name} » créé.')
        return redirect('btp:price_library_list')
    return render(request, 'btp/price_library_form.html', {
        'category_choices': ElectricityPriceLibrary.CATEGORY_CHOICES,
        'unit_choices': ElectricityPriceLibrary.UNIT_CHOICES,
        'complexity_choices': ElectricityPriceLibrary.COMPLEXITY_CHOICES,
        'action': 'create',
    })


@login_required
def price_library_edit(request, pk):
    company = _company(request)
    item = get_object_or_404(ElectricityPriceLibrary, pk=pk, company=company)
    if request.method == 'POST':
        item.code = request.POST.get('code', '')
        item.name = request.POST.get('name', '')
        item.category = request.POST.get('category', item.category)
        item.description = request.POST.get('description', '')
        item.unit = request.POST.get('unit', item.unit)
        item.price_min = request.POST.get('price_min', item.price_min) or 0
        item.price_avg = request.POST.get('price_avg', item.price_avg) or 0
        item.price_max = request.POST.get('price_max', item.price_max) or 0
        item.duration_hours = request.POST.get('duration_hours', item.duration_hours) or 0
        item.complexity = request.POST.get('complexity', item.complexity)
        item.is_active = request.POST.get('is_active') == 'on'
        item.save()
        messages.success(request, 'Poste mis à jour.')
        return redirect('btp:price_library_list')
    return render(request, 'btp/price_library_form.html', {
        'item': item,
        'category_choices': ElectricityPriceLibrary.CATEGORY_CHOICES,
        'unit_choices': ElectricityPriceLibrary.UNIT_CHOICES,
        'complexity_choices': ElectricityPriceLibrary.COMPLEXITY_CHOICES,
        'action': 'edit',
    })


@login_required
def price_library_delete(request, pk):
    company = _company(request)
    item = get_object_or_404(ElectricityPriceLibrary, pk=pk, company=company)
    if request.method == 'POST':
        name = item.name
        item.delete()
        messages.success(request, f'Poste « {name} » supprimé.')
        return redirect('btp:price_library_list')
    return render(request, 'btp/price_library_confirm_delete.html', {'item': item})


# ─── GESTION HEURES CHANTIER ──────────────────────────────────────────────────

@login_required
def time_entry_list(request):
    company = _company(request)
    qs = TimeEntry.objects.filter(project__company=company).select_related('employee', 'project')
    project_filter = request.GET.get('project', '')
    status_filter = request.GET.get('status', '')
    if project_filter:
        qs = qs.filter(project_id=project_filter)
    if status_filter:
        qs = qs.filter(status=status_filter)
    projects = BTPProject.objects.filter(company=company, is_active=True).order_by('name')
    return render(request, 'btp/time_entry_list.html', {
        'entries': qs,
        'projects': projects,
    })


@login_required
def time_entry_toggle_visible(request, pk):
    company = _company(request)
    entry = get_object_or_404(TimeEntry, pk=pk, project__company=company)
    entry.visible_to_client = not entry.visible_to_client
    if entry.visible_to_client:
        entry.status = 'client_visible'
    entry.save()
    return redirect(request.META.get('HTTP_REFERER', 'btp:index'))


# ─── MESSAGERIE ERP ───────────────────────────────────────────────────────────

@login_required
def client_messages_list(request):
    company = _company(request)
    conversations = ClientConversation.objects.filter(
        project__company=company
    ).select_related('project').order_by('-updated_at')

    unread_total = sum(c.unread_by_manager for c in conversations)
    return render(request, 'btp/client_messages_list.html', {
        'conversations': conversations,
        'unread_total': unread_total,
    })


@login_required
def client_conversation_detail(request, pk):
    company = _company(request)
    conv = get_object_or_404(ClientConversation, pk=pk, project__company=company)
    msgs = conv.messages.all().prefetch_related('attachments')

    if request.method == 'POST':
        action = request.POST.get('action', 'reply')
        content = request.POST.get('content', '')
        is_internal = action == 'internal_note'
        if content:
            ClientMessage.objects.create(
                conversation=conv,
                sender_name=request.user.get_full_name() or request.user.username,
                is_from_client=False,
                is_internal=is_internal,
                content=content,
            )
            if not is_internal:
                conv.unread_by_client += 1
                conv.status = 'waiting_client'
                conv.save()
                # Notifier le client
                ClientNotification.objects.create(
                    project=conv.project,
                    client_email=conv.project.customer.email if conv.project.customer_id else '',
                    notif_type='message',
                    title='Nouveau message sur votre chantier',
                    message=f'Un responsable a répondu à votre message : {conv.subject}',
                    link=f'/client/chantiers/{conv.project_id}/messages/{conv.pk}/',
                )
        return redirect('btp:client_conversation_detail', pk=pk)

    conv.unread_by_manager = 0
    conv.save(update_fields=['unread_by_manager'])

    return render(request, 'btp/client_conversation_detail.html', {
        'conv': conv, 'msgs': msgs,
    })


# ─── RÉSERVES ERP ─────────────────────────────────────────────────────────────

@login_required
def reservations_list(request):
    company = _company(request)
    qs = ProjectReservation.objects.filter(
        project__company=company
    ).prefetch_related('photos').select_related('project')
    project_filter = request.GET.get('project', '')
    status_filter = request.GET.get('status', '')
    importance_filter = request.GET.get('importance', '')
    if project_filter:
        qs = qs.filter(project_id=project_filter)
    if status_filter:
        qs = qs.filter(status=status_filter)
    if importance_filter:
        qs = qs.filter(importance=importance_filter)
    open_count = ProjectReservation.objects.filter(
        project__company=company, status__in=['new', 'analyzing', 'planned']
    ).count()
    projects = BTPProject.objects.filter(company=company, is_active=True).order_by('name')
    return render(request, 'btp/reservations_list.html', {
        'reservations': qs,
        'open_count': open_count,
        'projects': projects,
    })


@login_required
def reservation_update_status(request, pk):
    company = _company(request)
    res = get_object_or_404(ProjectReservation, pk=pk, project__company=company)
    if request.method == 'POST':
        res.status = request.POST.get('status', res.status)
        res.internal_notes = request.POST.get('internal_notes', res.internal_notes)
        if res.status == 'corrected' and not res.corrected_at:
            res.corrected_at = timezone.now()
        res.save()
        messages.success(request, 'Réserve mise à jour.')
    return redirect(request.META.get('HTTP_REFERER', 'btp:index'))
