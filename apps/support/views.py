from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import Ticket, TicketMessage
from .forms import TicketForm, TicketMessageForm


@login_required
def index(request):
    return redirect('support:ticket_list')


@login_required
def ticket_list(request):
    company = request.current_company
    qs = Ticket.objects.filter(company=company)
    status = request.GET.get('status', '')
    priority = request.GET.get('priority', '')
    ticket_type = request.GET.get('type', '')
    search = request.GET.get('q', '')
    if status:
        qs = qs.filter(status=status)
    if priority:
        qs = qs.filter(priority=priority)
    if ticket_type:
        qs = qs.filter(ticket_type=ticket_type)
    if search:
        from django.db.models import Q
        qs = qs.filter(Q(subject__icontains=search) | Q(number__icontains=search))
    count_open = Ticket.objects.filter(company=company, status='open').count()
    count_in_progress = Ticket.objects.filter(company=company, status='in_progress').count()
    count_waiting = Ticket.objects.filter(company=company, status='waiting').count()
    count_critical = Ticket.objects.filter(company=company, priority='critical').exclude(status__in=['resolved', 'closed']).count()
    return render(request, 'support/ticket_list.html', {
        'tickets': qs, 'status': status, 'priority': priority, 'ticket_type': ticket_type, 'search': search,
        'status_choices': Ticket.STATUS_CHOICES, 'priority_choices': Ticket.PRIORITY_CHOICES,
        'type_choices': Ticket.TYPE_CHOICES,
        'count_open': count_open, 'count_in_progress': count_in_progress,
        'count_waiting': count_waiting, 'count_critical': count_critical,
        'page_title': 'Tickets support', 'active_module': 'support',
    })


@login_required
def ticket_detail(request, pk):
    company = request.current_company
    ticket = get_object_or_404(Ticket, pk=pk, company=company)
    msg_form = TicketMessageForm()
    if request.method == 'POST':
        msg_form = TicketMessageForm(request.POST, request.FILES)
        if msg_form.is_valid():
            msg = msg_form.save(commit=False)
            msg.ticket = ticket
            msg.user = request.user
            msg.save()
            messages.success(request, 'Message ajouté.')
            return redirect('support:ticket_detail', pk=pk)
    return render(request, 'support/ticket_detail.html', {'ticket': ticket, 'msg_form': msg_form})


@login_required
def ticket_create(request):
    company = request.current_company
    form = TicketForm(company=company)
    if request.method == 'POST':
        form = TicketForm(request.POST, company=company)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.company = company
            ticket.created_by = request.user
            count = Ticket.objects.filter(company=company).count()
            ticket.number = f'TKT-{count + 1:04d}'
            ticket.save()
            messages.success(request, f'Ticket {ticket.number} créé avec succès.')
            return redirect('support:ticket_detail', pk=ticket.pk)
    return render(request, 'support/ticket_form.html', {'form': form, 'action': 'create'})


@login_required
def ticket_edit(request, pk):
    company = request.current_company
    ticket = get_object_or_404(Ticket, pk=pk, company=company)
    form = TicketForm(instance=ticket, company=company)
    if request.method == 'POST':
        form = TicketForm(request.POST, instance=ticket, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, 'Ticket mis à jour.')
            return redirect('support:ticket_detail', pk=pk)
    return render(request, 'support/ticket_form.html', {'form': form, 'ticket': ticket, 'action': 'edit'})


@login_required
def ticket_delete(request, pk):
    company = request.current_company
    ticket = get_object_or_404(Ticket, pk=pk, company=company)
    if request.method == 'POST':
        ticket.delete()
        messages.success(request, 'Ticket supprimé.')
        return redirect('support:ticket_list')
    return render(request, 'support/ticket_confirm_delete.html', {'ticket': ticket})


@login_required
def ticket_resolve(request, pk):
    company = request.current_company
    ticket = get_object_or_404(Ticket, pk=pk, company=company)
    if request.method == 'POST':
        ticket.status = 'resolved'
        ticket.resolved_at = timezone.now()
        ticket.save()
        TicketMessage.objects.create(ticket=ticket, user=request.user, message='Ticket marqué comme résolu.', is_internal=True)
        messages.success(request, 'Ticket marqué comme résolu.')
    return redirect('support:ticket_detail', pk=pk)


@login_required
def ticket_close(request, pk):
    company = request.current_company
    ticket = get_object_or_404(Ticket, pk=pk, company=company)
    if request.method == 'POST':
        ticket.status = 'closed'
        ticket.save()
        messages.success(request, 'Ticket fermé.')
    return redirect('support:ticket_detail', pk=pk)


@login_required
def claim_list(request):
    company = request.current_company
    qs = Ticket.objects.filter(company=company, ticket_type='claim')
    status = request.GET.get('status', '')
    if status:
        qs = qs.filter(status=status)
    return render(request, 'support/claim_list.html', {
        'claims': qs, 'status': status, 'status_choices': Ticket.STATUS_CHOICES,
    })


