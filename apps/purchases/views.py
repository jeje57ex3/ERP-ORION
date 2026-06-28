from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum
from django.utils import timezone

from .models import Supplier, PurchaseOrder, SupplierInvoice
from .forms import SupplierForm, PurchaseOrderForm, SupplierInvoiceForm


@login_required
def index(request):
    return redirect('purchases:supplier_list')


# --- Suppliers ---

@login_required
def supplier_list(request):
    company = request.current_company
    q = request.GET.get('q', '')
    active = request.GET.get('active', '')
    suppliers = Supplier.objects.filter(company=company)
    if q:
        suppliers = suppliers.filter(Q(name__icontains=q) | Q(code__icontains=q) | Q(contact_name__icontains=q))
    if active == '1':
        suppliers = suppliers.filter(is_active=True)
    elif active == '0':
        suppliers = suppliers.filter(is_active=False)
    ctx = {
        'suppliers': suppliers,
        'q': q,
        'active': active,
        'count_active': Supplier.objects.filter(company=company, is_active=True).count(),
        'page_title': 'Fournisseurs',
        'active_module': 'purchases',
    }
    return render(request, 'purchases/supplier_list.html', ctx)


@login_required
def supplier_detail(request, pk):
    company = request.current_company
    supplier = get_object_or_404(Supplier, pk=pk, company=company)
    orders = supplier.orders.all()[:10]
    invoices = supplier.invoices.all()[:10]
    ctx = {
        'supplier': supplier,
        'orders': orders,
        'invoices': invoices,
        'tab': request.GET.get('tab', 'info'),
    }
    return render(request, 'purchases/supplier_detail.html', ctx)


@login_required
def supplier_create(request):
    company = request.current_company
    if request.method == 'POST':
        form = SupplierForm(request.POST)
        if form.is_valid():
            supplier = form.save(commit=False)
            supplier.company = company
            supplier.save()
            messages.success(request, f'Fournisseur "{supplier.name}" créé avec succès.')
            return redirect('purchases:supplier_detail', pk=supplier.pk)
    else:
        form = SupplierForm()
    return render(request, 'purchases/supplier_form.html', {'form': form, 'action': 'create'})


@login_required
def supplier_edit(request, pk):
    company = request.current_company
    supplier = get_object_or_404(Supplier, pk=pk, company=company)
    if request.method == 'POST':
        form = SupplierForm(request.POST, instance=supplier)
        if form.is_valid():
            form.save()
            messages.success(request, 'Fournisseur mis à jour.')
            return redirect('purchases:supplier_detail', pk=supplier.pk)
    else:
        form = SupplierForm(instance=supplier)
    return render(request, 'purchases/supplier_form.html', {'form': form, 'supplier': supplier, 'action': 'edit'})


@login_required
def supplier_delete(request, pk):
    company = request.current_company
    supplier = get_object_or_404(Supplier, pk=pk, company=company)
    if request.method == 'POST':
        name = supplier.name
        supplier.delete()
        messages.success(request, f'Fournisseur "{name}" supprimé.')
        return redirect('purchases:supplier_list')
    return render(request, 'purchases/supplier_confirm_delete.html', {'supplier': supplier})


# --- Purchase Orders ---

@login_required
def order_list(request):
    company = request.current_company
    q = request.GET.get('q', '')
    status = request.GET.get('status', '')
    orders = PurchaseOrder.objects.filter(company=company)
    if q:
        orders = orders.filter(Q(number__icontains=q) | Q(supplier__name__icontains=q))
    if status:
        orders = orders.filter(status=status)
    ctx = {
        'orders': orders,
        'q': q,
        'status': status,
        'status_choices': PurchaseOrder.STATUS_CHOICES,
        'total_ht': orders.aggregate(s=Sum('total_ht'))['s'] or 0,
    }
    return render(request, 'purchases/order_list.html', ctx)


@login_required
def order_detail(request, pk):
    company = request.current_company
    order = get_object_or_404(PurchaseOrder, pk=pk, company=company)
    invoices = order.supplierinvoice_set.all() if hasattr(order, 'supplierinvoice_set') else []
    ctx = {'order': order, 'invoices': invoices}
    return render(request, 'purchases/order_detail.html', ctx)


@login_required
def order_create(request):
    company = request.current_company
    if request.method == 'POST':
        form = PurchaseOrderForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            order.company = company
            order.created_by = request.user
            count = PurchaseOrder.objects.filter(company=company).count() + 1
            order.number = f'BC-{count:04d}'
            order.save()
            messages.success(request, f'Commande achat {order.number} créée.')
            return redirect('purchases:order_detail', pk=order.pk)
    else:
        form = PurchaseOrderForm()
        form.fields['supplier'].queryset = Supplier.objects.filter(company=company, is_active=True)
    return render(request, 'purchases/order_form.html', {'form': form, 'action': 'create'})


@login_required
def order_edit(request, pk):
    company = request.current_company
    order = get_object_or_404(PurchaseOrder, pk=pk, company=company)
    if request.method == 'POST':
        form = PurchaseOrderForm(request.POST, instance=order)
        if form.is_valid():
            form.save()
            messages.success(request, 'Commande mise à jour.')
            return redirect('purchases:order_detail', pk=order.pk)
    else:
        form = PurchaseOrderForm(instance=order)
        form.fields['supplier'].queryset = Supplier.objects.filter(company=company, is_active=True)
    return render(request, 'purchases/order_form.html', {'form': form, 'order': order, 'action': 'edit'})


@login_required
def order_delete(request, pk):
    company = request.current_company
    order = get_object_or_404(PurchaseOrder, pk=pk, company=company)
    if request.method == 'POST':
        number = order.number
        order.delete()
        messages.success(request, f'Commande achat {number} supprimée.')
        return redirect('purchases:order_list')
    return render(request, 'purchases/order_confirm_delete.html', {'order': order})


@login_required
def order_receive(request, pk):
    company = request.current_company
    order = get_object_or_404(PurchaseOrder, pk=pk, company=company)
    if request.method == 'POST':
        order.status = 'received'
        order.save()
        messages.success(request, f'Commande {order.number} marquée comme reçue.')
        return redirect('purchases:order_detail', pk=order.pk)
    return render(request, 'purchases/order_receive_confirm.html', {'order': order})


# --- Supplier Invoices ---

@login_required
def supplier_invoice_list(request):
    company = request.current_company
    q = request.GET.get('q', '')
    status = request.GET.get('status', '')
    invoices = SupplierInvoice.objects.filter(company=company)
    if q:
        invoices = invoices.filter(Q(number__icontains=q) | Q(supplier__name__icontains=q) | Q(supplier_ref__icontains=q))
    if status:
        invoices = invoices.filter(status=status)
    today = timezone.now().date()
    ctx = {
        'invoices': invoices,
        'q': q,
        'status': status,
        'status_choices': SupplierInvoice.STATUS_CHOICES,
        'total_ttc': invoices.aggregate(s=Sum('total_ttc'))['s'] or 0,
        'count_pending': SupplierInvoice.objects.filter(company=company, status='pending').count(),
        'count_overdue': SupplierInvoice.objects.filter(company=company, status='overdue').count(),
        'today': today,
    }
    return render(request, 'purchases/supplier_invoice_list.html', ctx)


@login_required
def supplier_invoice_detail(request, pk):
    company = request.current_company
    invoice = get_object_or_404(SupplierInvoice, pk=pk, company=company)
    today = timezone.now().date()
    ctx = {'invoice': invoice, 'today': today}
    return render(request, 'purchases/supplier_invoice_detail.html', ctx)


@login_required
def supplier_invoice_create(request):
    company = request.current_company
    if request.method == 'POST':
        form = SupplierInvoiceForm(request.POST)
        if form.is_valid():
            invoice = form.save(commit=False)
            invoice.company = company
            invoice.save()
            messages.success(request, f'Facture fournisseur {invoice.number or invoice.supplier_ref} créée.')
            return redirect('purchases:supplier_invoice_detail', pk=invoice.pk)
    else:
        form = SupplierInvoiceForm()
        form.fields['supplier'].queryset = Supplier.objects.filter(company=company, is_active=True)
        form.fields['purchase_order'].queryset = PurchaseOrder.objects.filter(company=company)
    return render(request, 'purchases/supplier_invoice_form.html', {'form': form, 'action': 'create'})


@login_required
def supplier_invoice_edit(request, pk):
    company = request.current_company
    invoice = get_object_or_404(SupplierInvoice, pk=pk, company=company)
    if request.method == 'POST':
        form = SupplierInvoiceForm(request.POST, instance=invoice)
        if form.is_valid():
            form.save()
            messages.success(request, 'Facture fournisseur mise à jour.')
            return redirect('purchases:supplier_invoice_detail', pk=invoice.pk)
    else:
        form = SupplierInvoiceForm(instance=invoice)
        form.fields['supplier'].queryset = Supplier.objects.filter(company=company, is_active=True)
        form.fields['purchase_order'].queryset = PurchaseOrder.objects.filter(company=company)
    return render(request, 'purchases/supplier_invoice_form.html', {'form': form, 'invoice': invoice, 'action': 'edit'})


@login_required
def supplier_invoice_delete(request, pk):
    company = request.current_company
    invoice = get_object_or_404(SupplierInvoice, pk=pk, company=company)
    if request.method == 'POST':
        invoice.delete()
        messages.success(request, 'Facture fournisseur supprimée.')
        return redirect('purchases:supplier_invoice_list')
    return render(request, 'purchases/supplier_invoice_confirm_delete.html', {'invoice': invoice})


@login_required
def supplier_invoice_approve(request, pk):
    company = request.current_company
    invoice = get_object_or_404(SupplierInvoice, pk=pk, company=company)
    if request.method == 'POST':
        invoice.status = 'approved'
        invoice.save()
        messages.success(request, f'Facture {invoice.supplier_ref or invoice.pk} approuvée.')
        return redirect('purchases:supplier_invoice_detail', pk=invoice.pk)
    return redirect('purchases:supplier_invoice_detail', pk=invoice.pk)


@login_required
def supplier_invoice_mark_paid(request, pk):
    company = request.current_company
    invoice = get_object_or_404(SupplierInvoice, pk=pk, company=company)
    if request.method == 'POST':
        invoice.status = 'paid'
        invoice.save()
        messages.success(request, f'Facture {invoice.supplier_ref or invoice.pk} marquée payée.')
        return redirect('purchases:supplier_invoice_detail', pk=invoice.pk)
    return redirect('purchases:supplier_invoice_detail', pk=invoice.pk)
