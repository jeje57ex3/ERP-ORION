"""apps/sales/views.py — Vues CRUD Ventes"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum
from django.utils import timezone
from .models import Quote, SalesOrder, Invoice
from .forms import QuoteForm, SalesOrderForm, InvoiceForm
from apps.crm.models import Customer


@login_required
def index(request):
    return redirect('sales:quote_list')


# ─────────────────────────────────────────────────────────────
# DEVIS
# ─────────────────────────────────────────────────────────────

@login_required
def quote_list(request):
    company = request.current_company
    qs = Quote.objects.filter(company=company).select_related('customer', 'salesperson')

    q = request.GET.get('q', '')
    status = request.GET.get('status', '')

    if q:
        qs = qs.filter(Q(number__icontains=q) | Q(customer__name__icontains=q) | Q(subject__icontains=q))
    if status:
        qs = qs.filter(status=status)

    total_ht = qs.aggregate(t=Sum('total_ht'))['t'] or 0
    count_draft = Quote.objects.filter(company=company, status='draft').count()
    count_sent = Quote.objects.filter(company=company, status='sent').count()

    return render(request, 'sales/quote_list.html', {
        'page_title': 'Devis',
        'quotes': qs,
        'q': q,
        'status': status,
        'status_choices': Quote.STATUS_CHOICES,
        'total_ht': total_ht,
        'count_draft': count_draft,
        'count_sent': count_sent,
    })


@login_required
def quote_detail(request, pk):
    company = request.current_company
    quote = get_object_or_404(Quote, pk=pk, company=company)
    lines = quote.lines.all()
    return render(request, 'sales/quote_detail.html', {
        'page_title': f'Devis {quote.number or pk}',
        'quote': quote,
        'lines': lines,
    })


@login_required
def quote_create(request):
    company = request.current_company
    if request.method == 'POST':
        form = QuoteForm(request.POST)
        if form.is_valid():
            quote = form.save(commit=False)
            quote.company = company
            quote.created_by = request.user
            # Génère le numéro
            last = Quote.objects.filter(company=company).count()
            prefix = getattr(company, 'quote_prefix', 'DEV') or 'DEV'
            quote.number = f'{prefix}-{str(last + 1).zfill(4)}'
            quote.save()
            messages.success(request, f'Devis {quote.number} créé avec succès.')
            return redirect('sales:quote_detail', pk=quote.pk)
    else:
        form = QuoteForm()
        form.fields['customer'].queryset = Customer.objects.filter(company=company, is_active=True)
        customer_pk = request.GET.get('customer')
        if customer_pk:
            form.fields['customer'].initial = customer_pk

    return render(request, 'sales/quote_form.html', {
        'page_title': 'Nouveau devis',
        'form': form,
        'action': 'create',
    })


@login_required
def quote_edit(request, pk):
    company = request.current_company
    quote = get_object_or_404(Quote, pk=pk, company=company)
    if request.method == 'POST':
        form = QuoteForm(request.POST, instance=quote)
        if form.is_valid():
            form.save()
            messages.success(request, 'Devis mis à jour.')
            return redirect('sales:quote_detail', pk=quote.pk)
    else:
        form = QuoteForm(instance=quote)
        form.fields['customer'].queryset = Customer.objects.filter(company=company, is_active=True)

    return render(request, 'sales/quote_form.html', {
        'page_title': f'Modifier devis {quote.number}',
        'form': form,
        'quote': quote,
        'action': 'edit',
    })


@login_required
def quote_delete(request, pk):
    company = request.current_company
    quote = get_object_or_404(Quote, pk=pk, company=company)
    if request.method == 'POST':
        num = quote.number
        quote.delete()
        messages.success(request, f'Devis {num} supprimé.')
        return redirect('sales:quote_list')
    return render(request, 'sales/quote_confirm_delete.html', {
        'page_title': 'Supprimer le devis',
        'quote': quote,
    })


@login_required
def quote_send(request, pk):
    company = request.current_company
    quote = get_object_or_404(Quote, pk=pk, company=company)
    quote.status = 'sent'
    quote.save()
    messages.success(request, f'Devis {quote.number} marqué comme envoyé.')
    return redirect('sales:quote_detail', pk=quote.pk)


@login_required
def quote_accept(request, pk):
    company = request.current_company
    quote = get_object_or_404(Quote, pk=pk, company=company)
    quote.status = 'accepted'
    quote.save()
    messages.success(request, f'Devis {quote.number} accepté.')
    return redirect('sales:quote_detail', pk=quote.pk)


@login_required
def quote_convert_order(request, pk):
    """Convertit un devis en commande."""
    company = request.current_company
    quote = get_object_or_404(Quote, pk=pk, company=company)
    last = SalesOrder.objects.filter(company=company).count()
    order = SalesOrder.objects.create(
        company=company,
        customer=quote.customer,
        quote=quote,
        number=f'CMD-{str(last + 1).zfill(4)}',
        total_ht=quote.total_ht,
        total_ttc=quote.total_ttc,
        salesperson=quote.salesperson,
    )
    quote.status = 'accepted'
    quote.save()
    messages.success(request, f'Commande {order.number} créée depuis le devis.')
    return redirect('sales:order_detail', pk=order.pk)


# ─────────────────────────────────────────────────────────────
# COMMANDES
# ─────────────────────────────────────────────────────────────

@login_required
def order_list(request):
    company = request.current_company
    qs = SalesOrder.objects.filter(company=company).select_related('customer', 'salesperson')

    q = request.GET.get('q', '')
    status = request.GET.get('status', '')

    if q:
        qs = qs.filter(Q(number__icontains=q) | Q(customer__name__icontains=q))
    if status:
        qs = qs.filter(status=status)

    return render(request, 'sales/order_list.html', {
        'page_title': 'Commandes clients',
        'orders': qs,
        'q': q,
        'status': status,
        'status_choices': SalesOrder.STATUS_CHOICES,
    })


@login_required
def order_detail(request, pk):
    company = request.current_company
    order = get_object_or_404(SalesOrder, pk=pk, company=company)
    return render(request, 'sales/order_detail.html', {
        'page_title': f'Commande {order.number or pk}',
        'order': order,
    })


@login_required
def order_create(request):
    company = request.current_company
    if request.method == 'POST':
        form = SalesOrderForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            order.company = company
            last = SalesOrder.objects.filter(company=company).count()
            order.number = f'CMD-{str(last + 1).zfill(4)}'
            order.save()
            messages.success(request, f'Commande {order.number} créée.')
            return redirect('sales:order_detail', pk=order.pk)
    else:
        form = SalesOrderForm()
        form.fields['customer'].queryset = Customer.objects.filter(company=company, is_active=True)

    return render(request, 'sales/order_form.html', {
        'page_title': 'Nouvelle commande',
        'form': form,
        'action': 'create',
    })


@login_required
def order_update_status(request, pk, new_status):
    company = request.current_company
    order = get_object_or_404(SalesOrder, pk=pk, company=company)
    valid = dict(SalesOrder.STATUS_CHOICES)
    if new_status in valid:
        order.status = new_status
        order.save()
        messages.success(request, f'Commande {order.number} : statut mis à jour → {valid[new_status]}.')
    return redirect('sales:order_detail', pk=order.pk)


# ─────────────────────────────────────────────────────────────
# FACTURES
# ─────────────────────────────────────────────────────────────

@login_required
def invoice_list(request):
    company = request.current_company
    qs = Invoice.objects.filter(company=company).select_related('customer', 'salesperson')

    q = request.GET.get('q', '')
    status = request.GET.get('status', '')

    if q:
        qs = qs.filter(Q(number__icontains=q) | Q(customer__name__icontains=q) | Q(subject__icontains=q))
    if status:
        qs = qs.filter(status=status)

    total_ht = qs.aggregate(t=Sum('total_ht'))['t'] or 0
    total_ttc = qs.aggregate(t=Sum('total_ttc'))['t'] or 0
    total_paid = qs.aggregate(t=Sum('amount_paid'))['t'] or 0

    return render(request, 'sales/invoice_list.html', {
        'page_title': 'Factures',
        'invoices': qs,
        'q': q,
        'status': status,
        'status_choices': Invoice.STATUS_CHOICES,
        'total_ht': total_ht,
        'total_ttc': total_ttc,
        'total_paid': total_paid,
    })


@login_required
def invoice_detail(request, pk):
    company = request.current_company
    invoice = get_object_or_404(Invoice, pk=pk, company=company)
    lines = invoice.lines.all()
    return render(request, 'sales/invoice_detail.html', {
        'page_title': f'Facture {invoice.number or pk}',
        'invoice': invoice,
        'lines': lines,
    })


@login_required
def invoice_create(request):
    company = request.current_company
    if request.method == 'POST':
        form = InvoiceForm(request.POST)
        if form.is_valid():
            invoice = form.save(commit=False)
            invoice.company = company
            invoice.created_by = request.user
            last = Invoice.objects.filter(company=company).count()
            prefix = getattr(company, 'invoice_prefix', 'FAC') or 'FAC'
            invoice.number = f'{prefix}-{str(last + 1).zfill(4)}'
            invoice.save()
            messages.success(request, f'Facture {invoice.number} créée.')
            return redirect('sales:invoice_detail', pk=invoice.pk)
    else:
        form = InvoiceForm()
        form.fields['customer'].queryset = Customer.objects.filter(company=company, is_active=True)
        customer_pk = request.GET.get('customer')
        if customer_pk:
            form.fields['customer'].initial = customer_pk

    return render(request, 'sales/invoice_form.html', {
        'page_title': 'Nouvelle facture',
        'form': form,
        'action': 'create',
    })


@login_required
def invoice_edit(request, pk):
    company = request.current_company
    invoice = get_object_or_404(Invoice, pk=pk, company=company)
    if request.method == 'POST':
        form = InvoiceForm(request.POST, instance=invoice)
        if form.is_valid():
            form.save()
            messages.success(request, 'Facture mise à jour.')
            return redirect('sales:invoice_detail', pk=invoice.pk)
    else:
        form = InvoiceForm(instance=invoice)
        form.fields['customer'].queryset = Customer.objects.filter(company=company, is_active=True)

    return render(request, 'sales/invoice_form.html', {
        'page_title': f'Modifier facture {invoice.number}',
        'form': form,
        'invoice': invoice,
        'action': 'edit',
    })


@login_required
def invoice_delete(request, pk):
    company = request.current_company
    invoice = get_object_or_404(Invoice, pk=pk, company=company)
    if request.method == 'POST':
        num = invoice.number
        invoice.delete()
        messages.success(request, f'Facture {num} supprimée.')
        return redirect('sales:invoice_list')
    return render(request, 'sales/invoice_confirm_delete.html', {
        'page_title': 'Supprimer la facture',
        'invoice': invoice,
    })


@login_required
def invoice_mark_paid(request, pk):
    company = request.current_company
    invoice = get_object_or_404(Invoice, pk=pk, company=company)
    invoice.status = 'paid'
    invoice.amount_paid = invoice.total_ttc
    invoice.save()
    messages.success(request, f'Facture {invoice.number} marquée comme payée.')
    return redirect('sales:invoice_detail', pk=invoice.pk)


@login_required
def invoice_send(request, pk):
    company = request.current_company
    invoice = get_object_or_404(Invoice, pk=pk, company=company)
    invoice.status = 'sent'
    invoice.save()
    messages.success(request, f'Facture {invoice.number} marquée comme envoyée.')
    return redirect('sales:invoice_detail', pk=invoice.pk)
