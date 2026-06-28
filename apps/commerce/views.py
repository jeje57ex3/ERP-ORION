from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum
from .models import Store, POSSession, POSTicket, LoyaltyCard
from .forms import StoreForm, POSSessionForm, POSTicketForm


@login_required
def index(request):
    return redirect('commerce:store_list')


# --- STORES ---

@login_required
def store_list(request):
    company = request.current_company
    stores = Store.objects.filter(company=company)
    total = stores.count()
    active = stores.filter(is_active=True).count()
    return render(request, 'commerce/store_list.html', {
        'stores': stores, 'total': total, 'active': active,
    })


@login_required
def store_detail(request, pk):
    company = request.current_company
    store = get_object_or_404(Store, pk=pk, company=company)
    sessions = POSSession.objects.filter(company=company, store=store).order_by('-opened_at')[:10]
    return render(request, 'commerce/store_detail.html', {'store': store, 'sessions': sessions})


@login_required
def store_create(request):
    form = StoreForm()
    if request.method == 'POST':
        form = StoreForm(request.POST)
        if form.is_valid():
            store = form.save(commit=False)
            store.company = request.current_company
            store.save()
            messages.success(request, f'Magasin « {store.name} » créé.')
            return redirect('commerce:store_detail', pk=store.pk)
    return render(request, 'commerce/store_form.html', {'form': form, 'action': 'create'})


@login_required
def store_edit(request, pk):
    company = request.current_company
    store = get_object_or_404(Store, pk=pk, company=company)
    form = StoreForm(instance=store)
    if request.method == 'POST':
        form = StoreForm(request.POST, instance=store)
        if form.is_valid():
            form.save()
            messages.success(request, 'Magasin mis à jour.')
            return redirect('commerce:store_detail', pk=pk)
    return render(request, 'commerce/store_form.html', {'form': form, 'store': store, 'action': 'edit'})


@login_required
def store_delete(request, pk):
    company = request.current_company
    store = get_object_or_404(Store, pk=pk, company=company)
    if request.method == 'POST':
        name = store.name
        store.delete()
        messages.success(request, f'Magasin « {name} » supprimé.')
        return redirect('commerce:store_list')
    return render(request, 'commerce/store_confirm_delete.html', {'store': store})


# --- POS SESSIONS ---

@login_required
def pos_list(request):
    company = request.current_company
    store_id = request.GET.get('store', '')
    status = request.GET.get('status', '')
    qs = POSSession.objects.filter(company=company).select_related('store', 'cashier')
    if store_id:
        qs = qs.filter(store_id=store_id)
    if status:
        qs = qs.filter(status=status)
    open_count = POSSession.objects.filter(company=company, status='open').count()
    stores = Store.objects.filter(company=company, is_active=True)
    return render(request, 'commerce/pos_session_list.html', {
        'sessions': qs, 'open_count': open_count,
        'stores': stores, 'store_id': store_id, 'status': status,
    })


@login_required
def pos_session_create(request):
    company = request.current_company
    form = POSSessionForm(company=company)
    if request.method == 'POST':
        form = POSSessionForm(request.POST, company=company)
        if form.is_valid():
            session = form.save(commit=False)
            session.company = company
            session.cashier = request.user
            session.save()
            messages.success(request, 'Session caisse ouverte.')
            return redirect('commerce:pos_list')
    return render(request, 'commerce/pos_session_form.html', {'form': form, 'action': 'create'})


@login_required
def pos_session_close(request, pk):
    company = request.current_company
    session = get_object_or_404(POSSession, pk=pk, company=company)
    if request.method == 'POST':
        from django.utils import timezone
        session.status = 'closed'
        closing_cash = request.POST.get('closing_cash')
        if closing_cash:
            session.closing_cash = closing_cash
        session.closed_at = timezone.now()
        session.save()
        messages.success(request, 'Session caisse fermée.')
    return redirect('commerce:pos_list')


# --- POS TICKETS ---

@login_required
def pos_ticket_list(request):
    company = request.current_company
    qs = POSTicket.objects.filter(company=company).select_related('session__store', 'customer')
    search = request.GET.get('q', '')
    if search:
        qs = qs.filter(Q(ticket_number__icontains=search))
    total_ca = qs.aggregate(Sum('total_ttc'))['total_ttc__sum'] or 0
    return render(request, 'commerce/pos_ticket_list.html', {
        'tickets': qs, 'search': search, 'total_ca': total_ca,
    })


# --- LOYALTY ---

@login_required
def loyalty_list(request):
    company = request.current_company
    qs = LoyaltyCard.objects.filter(company=company).select_related('customer')
    search = request.GET.get('q', '')
    if search:
        qs = qs.filter(Q(card_number__icontains=search) | Q(customer__name__icontains=search))
    total_active = LoyaltyCard.objects.filter(company=company, is_active=True).count()
    return render(request, 'commerce/loyalty_list.html', {
        'cards': qs, 'search': search, 'total_active': total_active,
    })




def _stub(request, *args, **kwargs):
    from django.http import HttpResponse
    return HttpResponse('<h3 style="font-family:sans-serif;padding:2rem">En cours de developpement.</h3>')
pos_session_export = login_required(_stub)

