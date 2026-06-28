from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from .models import BillOfMaterials, ManufacturingOrder, WorkCenter
from .forms import BOMForm, ManufacturingOrderForm, WorkCenterForm


@login_required
def index(request):
    return redirect('production:order_list')


# --- MANUFACTURING ORDERS ---

@login_required
def order_list(request):
    company = request.current_company
    qs = ManufacturingOrder.objects.filter(company=company).select_related('product')
    status = request.GET.get('status', '')
    if status:
        qs = qs.filter(status=status)
    total = ManufacturingOrder.objects.filter(company=company).count()
    in_progress = ManufacturingOrder.objects.filter(company=company, status='in_progress').count()
    planned = ManufacturingOrder.objects.filter(company=company, status='planned').count()
    return render(request, 'production/mo_list.html', {
        'orders': qs, 'status': status,
        'status_choices': ManufacturingOrder.STATUS_CHOICES,
        'total': total, 'in_progress': in_progress, 'planned': planned,
    })


@login_required
def order_detail(request, pk):
    company = request.current_company
    order = get_object_or_404(ManufacturingOrder, pk=pk, company=company)
    return render(request, 'production/mo_detail.html', {'order': order})


@login_required
def order_create(request):
    company = request.current_company
    form = ManufacturingOrderForm(company=company)
    if request.method == 'POST':
        form = ManufacturingOrderForm(request.POST, company=company)
        if form.is_valid():
            mo = form.save(commit=False)
            mo.company = company
            count = ManufacturingOrder.objects.filter(company=company).count()
            mo.order_number = f'OF-{count + 1:04d}'
            mo.save()
            messages.success(request, f'Ordre de fabrication {mo.order_number} créé.')
            return redirect('production:order_detail', pk=mo.pk)
    return render(request, 'production/mo_form.html', {'form': form, 'action': 'create'})


@login_required
def order_edit(request, pk):
    company = request.current_company
    order = get_object_or_404(ManufacturingOrder, pk=pk, company=company)
    form = ManufacturingOrderForm(instance=order, company=company)
    if request.method == 'POST':
        form = ManufacturingOrderForm(request.POST, instance=order, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, 'Ordre de fabrication mis à jour.')
            return redirect('production:order_detail', pk=pk)
    return render(request, 'production/mo_form.html', {'form': form, 'order': order, 'action': 'edit'})


# --- BOM ---

@login_required
def bom_list(request):
    company = request.current_company
    boms = BillOfMaterials.objects.filter(company=company).select_related('product')
    return render(request, 'production/bom_list.html', {'boms': boms})


@login_required
def bom_detail(request, pk):
    company = request.current_company
    bom = get_object_or_404(BillOfMaterials, pk=pk, company=company)
    return render(request, 'production/bom_detail.html', {'bom': bom})


@login_required
def bom_create(request):
    company = request.current_company
    form = BOMForm(company=company)
    if request.method == 'POST':
        form = BOMForm(request.POST, company=company)
        if form.is_valid():
            bom = form.save(commit=False)
            bom.company = company
            bom.save()
            messages.success(request, f'Nomenclature « {bom.name} » créée.')
            return redirect('production:bom_detail', pk=bom.pk)
    return render(request, 'production/bom_form.html', {'form': form, 'action': 'create'})


@login_required
def bom_edit(request, pk):
    company = request.current_company
    bom = get_object_or_404(BillOfMaterials, pk=pk, company=company)
    form = BOMForm(instance=bom, company=company)
    if request.method == 'POST':
        form = BOMForm(request.POST, instance=bom, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, 'Nomenclature mise à jour.')
            return redirect('production:bom_detail', pk=pk)
    return render(request, 'production/bom_form.html', {'form': form, 'bom': bom, 'action': 'edit'})


# --- WORK CENTERS ---

@login_required
def planning(request):
    company = request.current_company
    work_centers = WorkCenter.objects.filter(company=company)
    return render(request, 'production/workcenter_list.html', {'work_centers': work_centers})


@login_required
def workcenter_create(request):
    company = request.current_company
    form = WorkCenterForm()
    if request.method == 'POST':
        form = WorkCenterForm(request.POST)
        if form.is_valid():
            wc = form.save(commit=False)
            wc.company = company
            wc.save()
            messages.success(request, f'Centre de travail « {wc.name} » créé.')
            return redirect('production:planning')
    return render(request, 'production/workcenter_form.html', {'form': form})


