"""
Vues espace client chantier — URL namespace: client_portal
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from apps.core.models import Company
from apps.btp.models import (
    BTPProject, ClientConversation, ClientMessage, MessageAttachment,
    ProjectDocument, ProjectPlanStep, ClientChangeRequest, ChangeRequestItem,
    ProjectReservation, ReservationPhoto, ClientNotification, TimeEntry,
    SiteAssignment,
)
from .models import ClientPortalAccount, ClientPortalSettings


def _get_company(request):
    return getattr(request, 'current_company', None)


def _get_portal_account(request):
    if request.user.is_authenticated:
        return getattr(request.user, 'portal_account', None)
    return None


def _require_portal_login(request):
    """Redirige vers login si pas connecté au portail client."""
    if not request.user.is_authenticated or not _get_portal_account(request):
        return redirect('client_portal:login')
    return None


# ─── AUTH PORTAIL ─────────────────────────────────────────────────────────────

def portal_login(request):
    company = _get_company(request)
    portal_settings = ClientPortalSettings.get_for_company(company)

    if request.method == 'POST':
        email = request.POST.get('email', '')
        password = request.POST.get('password', '')
        try:
            user_obj = User.objects.get(email=email)
            user = authenticate(request, username=user_obj.username, password=password)
            if user and hasattr(user, 'portal_account'):
                login(request, user)
                acc = user.portal_account
                acc.last_login = timezone.now()
                acc.save(update_fields=['last_login'])
                return redirect('client_portal:dashboard')
            else:
                messages.error(request, 'Identifiants incorrects ou compte non autorisé.')
        except User.DoesNotExist:
            messages.error(request, 'Aucun compte avec cet email.')

    return render(request, 'client_portal/login.html', {
        'company': company,
        'portal_settings': portal_settings,
    })


def portal_logout(request):
    logout(request)
    return redirect('client_portal:login')


# ─── DASHBOARD ────────────────────────────────────────────────────────────────

def dashboard(request):
    redir = _require_portal_login(request)
    if redir:
        return redir
    company = _get_company(request)
    account = _get_portal_account(request)

    projects = list(BTPProject.objects.filter(
        company=company,
        customer__email=account.email,
    ).exclude(status__in=['lost', 'cancelled']))

    notifications = ClientNotification.objects.filter(
        client_email=account.email, is_read=False
    )[:10]

    unread_messages = ClientConversation.objects.filter(
        project__company=company,
        project__customer__email=account.email,
        unread_by_client__gt=0,
    ).count()

    return render(request, 'client_portal/dashboard.html', {
        'account': account,
        'projects': projects,
        'notifications': notifications,
        'unread_messages': unread_messages,
    })


# ─── CHANTIERS ────────────────────────────────────────────────────────────────

def project_list(request):
    redir = _require_portal_login(request)
    if redir:
        return redir
    company = _get_company(request)
    account = _get_portal_account(request)
    projects = BTPProject.objects.filter(company=company, customer__email=account.email)
    return render(request, 'client_portal/project_list.html', {
        'account': account, 'projects': projects,
    })


def project_detail(request, pk):
    redir = _require_portal_login(request)
    if redir:
        return redir
    company = _get_company(request)
    account = _get_portal_account(request)
    project = get_object_or_404(BTPProject, pk=pk, company=company, customer__email=account.email)

    assignments = SiteAssignment.objects.filter(project=project, visible_to_client=True, is_active=True).select_related('employee')
    plan_steps = ProjectPlanStep.objects.filter(project=project, visible_to_client=True)
    documents = ProjectDocument.objects.filter(project=project, visible_to_client=True)
    reservations = ProjectReservation.objects.filter(project=project)
    change_requests = ClientChangeRequest.objects.filter(project=project)
    conversations = ClientConversation.objects.filter(project=project)
    time_entries = TimeEntry.objects.filter(project=project, visible_to_client=True, status='client_visible')

    status_order = ['study', 'quoted', 'won', 'in_progress', 'completed', 'invoiced']
    project_step = status_order.index(project.status) if project.status in status_order else 0

    return render(request, 'client_portal/project_detail.html', {
        'account': account, 'project': project,
        'assignments': assignments,
        'plan_steps': plan_steps,
        'documents': documents,
        'reservations': reservations,
        'change_requests': change_requests,
        'conversations': conversations,
        'time_entries': time_entries,
        'project_step': project_step,
    })


# ─── PLANNING ─────────────────────────────────────────────────────────────────

def project_planning(request, pk):
    redir = _require_portal_login(request)
    if redir:
        return redir
    company = _get_company(request)
    account = _get_portal_account(request)
    project = get_object_or_404(BTPProject, pk=pk, company=company, customer__email=account.email)
    steps = ProjectPlanStep.objects.filter(project=project, visible_to_client=True)

    if request.method == 'POST':
        step_pk = request.POST.get('validate_step')
        if step_pk:
            step = get_object_or_404(ProjectPlanStep, pk=step_pk, project=project, client_can_validate=True)
            step.validated_by_client = True
            step.validated_by_client_at = timezone.now()
            step.save()
            messages.success(request, f'Étape « {step.name} » validée.')
        return redirect('client_portal:project_planning', pk=pk)

    return render(request, 'client_portal/project_planning.html', {
        'account': account, 'project': project, 'steps': steps,
    })


# ─── DOCUMENTS ────────────────────────────────────────────────────────────────

def project_documents(request, pk):
    redir = _require_portal_login(request)
    if redir:
        return redir
    company = _get_company(request)
    account = _get_portal_account(request)
    project = get_object_or_404(BTPProject, pk=pk, company=company, customer__email=account.email)
    documents = ProjectDocument.objects.filter(project=project, visible_to_client=True)

    if request.method == 'POST' and account.can_upload:
        for f in request.FILES.getlist('files'):
            ProjectDocument.objects.create(
                project=project,
                name=f.name,
                file=f,
                doc_type='client_doc',
                visible_to_client=True,
                added_by=request.user,
            )
        messages.success(request, 'Documents ajoutés.')
        return redirect('client_portal:project_documents', pk=pk)

    return render(request, 'client_portal/project_documents.html', {
        'account': account, 'project': project, 'documents': documents,
    })


# ─── MESSAGERIE ───────────────────────────────────────────────────────────────

def project_messages(request, pk):
    redir = _require_portal_login(request)
    if redir:
        return redir
    company = _get_company(request)
    account = _get_portal_account(request)
    project = get_object_or_404(BTPProject, pk=pk, company=company, customer__email=account.email)
    conversations = ClientConversation.objects.filter(project=project)

    if request.method == 'POST' and account.can_message:
        subject = request.POST.get('subject', 'Message chantier')
        content = request.POST.get('content', '')
        if content:
            conv, _ = ClientConversation.objects.get_or_create(
                project=project, subject=subject,
                defaults={'status': 'open', 'created_by_client': True},
            )
            msg = ClientMessage.objects.create(
                conversation=conv,
                sender_name=account.full_name,
                is_from_client=True,
                content=content,
            )
            for f in request.FILES.getlist('attachments'):
                MessageAttachment.objects.create(message=msg, file=f, name=f.name)
            conv.unread_by_manager += 1
            conv.save(update_fields=['unread_by_manager', 'updated_at'])
            messages.success(request, 'Message envoyé.')
        return redirect('client_portal:project_messages', pk=pk)

    # Marquer messages comme lus
    ClientConversation.objects.filter(
        project=project, unread_by_client__gt=0
    ).update(unread_by_client=0)

    return render(request, 'client_portal/project_messages.html', {
        'account': account, 'project': project, 'conversations': conversations,
    })


def conversation_detail(request, pk, conv_pk):
    redir = _require_portal_login(request)
    if redir:
        return redir
    company = _get_company(request)
    account = _get_portal_account(request)
    project = get_object_or_404(BTPProject, pk=pk, company=company, customer__email=account.email)
    conv = get_object_or_404(ClientConversation, pk=conv_pk, project=project)
    msgs = conv.messages.filter(is_internal=False).select_related()

    if request.method == 'POST' and account.can_message:
        content = request.POST.get('content', '')
        if content:
            msg = ClientMessage.objects.create(
                conversation=conv,
                sender_name=account.full_name,
                is_from_client=True,
                content=content,
            )
            for f in request.FILES.getlist('attachments'):
                MessageAttachment.objects.create(message=msg, file=f, name=f.name)
            conv.unread_by_manager += 1
            conv.status = 'waiting_manager'
            conv.save()
        return redirect('client_portal:conversation_detail', pk=pk, conv_pk=conv_pk)

    conv.unread_by_client = 0
    conv.save(update_fields=['unread_by_client'])

    return render(request, 'client_portal/conversation_detail.html', {
        'account': account, 'project': project, 'conv': conv, 'msgs': msgs,
    })


# ─── RÉSERVES ─────────────────────────────────────────────────────────────────

def project_reservations(request, pk):
    redir = _require_portal_login(request)
    if redir:
        return redir
    company = _get_company(request)
    account = _get_portal_account(request)
    project = get_object_or_404(BTPProject, pk=pk, company=company, customer__email=account.email)
    reservations = ProjectReservation.objects.filter(project=project)

    if request.method == 'POST' and account.can_report_reservations:
        res = ProjectReservation.objects.create(
            project=project,
            title=request.POST.get('title', ''),
            description=request.POST.get('description', ''),
            room=request.POST.get('room', ''),
            importance=request.POST.get('importance', 'medium'),
            reported_by_client=True,
        )
        for f in request.FILES.getlist('photos'):
            ReservationPhoto.objects.create(reservation=res, photo=f)
        messages.success(request, 'Réserve signalée.')
        return redirect('client_portal:project_reservations', pk=pk)

    return render(request, 'client_portal/project_reservations.html', {
        'account': account, 'project': project, 'reservations': reservations,
    })


# ─── AVENANTS ─────────────────────────────────────────────────────────────────

def project_changes(request, pk):
    redir = _require_portal_login(request)
    if redir:
        return redir
    company = _get_company(request)
    account = _get_portal_account(request)
    project = get_object_or_404(BTPProject, pk=pk, company=company, customer__email=account.email)
    changes = ClientChangeRequest.objects.filter(project=project)

    if request.method == 'POST' and account.can_request_changes:
        cr = ClientChangeRequest.objects.create(
            project=project,
            title=request.POST.get('title', ''),
            description=request.POST.get('description', ''),
            requested_by_client=True,
        )
        messages.success(request, 'Demande de modification envoyée.')
        return redirect('client_portal:project_changes', pk=pk)

    return render(request, 'client_portal/project_changes.html', {
        'account': account, 'project': project, 'changes': changes,
    })


# ─── HEURES ───────────────────────────────────────────────────────────────────

def project_hours(request, pk):
    redir = _require_portal_login(request)
    if redir:
        return redir
    company = _get_company(request)
    account = _get_portal_account(request)
    project = get_object_or_404(BTPProject, pk=pk, company=company, customer__email=account.email)
    time_entries = TimeEntry.objects.filter(
        project=project, visible_to_client=True, status='client_visible'
    ).select_related('employee')
    total_hours = sum(e.hours for e in time_entries)
    return render(request, 'client_portal/project_hours.html', {
        'account': account, 'project': project,
        'time_entries': time_entries, 'total_hours': total_hours,
    })


# ─── INTERVENANTS ─────────────────────────────────────────────────────────────

def project_team(request, pk):
    redir = _require_portal_login(request)
    if redir:
        return redir
    company = _get_company(request)
    account = _get_portal_account(request)
    project = get_object_or_404(BTPProject, pk=pk, company=company, customer__email=account.email)
    assignments = SiteAssignment.objects.filter(
        project=project, visible_to_client=True, is_active=True
    ).select_related('employee', 'employee__skills', 'employee__certifications')
    return render(request, 'client_portal/project_team.html', {
        'account': account, 'project': project, 'assignments': assignments,
    })


# ─── NOTIFICATIONS ────────────────────────────────────────────────────────────

def notifications(request):
    redir = _require_portal_login(request)
    if redir:
        return redir
    account = _get_portal_account(request)
    notifs = ClientNotification.objects.filter(client_email=account.email)

    if request.method == 'POST':
        notif_pk = request.POST.get('mark_read')
        if notif_pk:
            ClientNotification.objects.filter(pk=notif_pk, client_email=account.email).update(is_read=True)
        elif request.POST.get('mark_all_read'):
            ClientNotification.objects.filter(client_email=account.email).update(is_read=True)
        return redirect('client_portal:notifications')

    return render(request, 'client_portal/notifications.html', {
        'account': account, 'notifications': notifs,
    })
