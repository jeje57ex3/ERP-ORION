from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum

from .models import Product, ProductCategory, Warehouse, StockMovement
from .forms import ProductForm, ProductCategoryForm, WarehouseForm, StockMovementForm


@login_required
def index(request):
    return redirect('inventory:product_list')


# --- Products ---

@login_required
def product_list(request):
    company = request.current_company
    q = request.GET.get('q', '')
    category_id = request.GET.get('category', '')
    low_stock = request.GET.get('low_stock', '')
    products = Product.objects.filter(company=company)
    if q:
        products = products.filter(Q(name__icontains=q) | Q(reference__icontains=q) | Q(barcode__icontains=q))
    if category_id:
        products = products.filter(category_id=category_id)
    all_products = Product.objects.filter(company=company, track_inventory=True)
    count_low = sum(1 for p in all_products if p.needs_reorder)
    products_list = list(products)
    if low_stock == '1':
        products_list = [p for p in products_list if p.needs_reorder]
    categories = ProductCategory.objects.filter(company=company)
    ctx = {
        'products': products_list,
        'q': q,
        'category_id': category_id,
        'low_stock': low_stock,
        'categories': categories,
        'count_active': Product.objects.filter(company=company, is_active=True).count(),
        'count_low_stock': count_low,
        'page_title': 'Produits',
        'active_module': 'inventory',
    }
    return render(request, 'inventory/product_list.html', ctx)


@login_required
def product_detail(request, pk):
    company = request.current_company
    product = get_object_or_404(Product, pk=pk, company=company)
    movements = product.movements.all()[:20]
    ctx = {
        'product': product,
        'movements': movements,
        'tab': request.GET.get('tab', 'info'),
    }
    return render(request, 'inventory/product_detail.html', ctx)


@login_required
def product_create(request):
    company = request.current_company
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.company = company
            product.save()
            messages.success(request, f'Produit "{product.name}" créé.')
            return redirect('inventory:product_detail', pk=product.pk)
    else:
        form = ProductForm()
        form.fields['category'].queryset = ProductCategory.objects.filter(company=company)
    return render(request, 'inventory/product_form.html', {'form': form, 'action': 'create'})


@login_required
def product_edit(request, pk):
    company = request.current_company
    product = get_object_or_404(Product, pk=pk, company=company)
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, 'Produit mis à jour.')
            return redirect('inventory:product_detail', pk=product.pk)
    else:
        form = ProductForm(instance=product)
        form.fields['category'].queryset = ProductCategory.objects.filter(company=company)
    return render(request, 'inventory/product_form.html', {'form': form, 'product': product, 'action': 'edit'})


@login_required
def product_delete(request, pk):
    company = request.current_company
    product = get_object_or_404(Product, pk=pk, company=company)
    if request.method == 'POST':
        name = product.name
        product.delete()
        messages.success(request, f'Produit "{name}" supprimé.')
        return redirect('inventory:product_list')
    return render(request, 'inventory/product_confirm_delete.html', {'product': product})


# --- Warehouses ---

@login_required
def warehouse_list(request):
    company = request.current_company
    warehouses = Warehouse.objects.filter(company=company)
    ctx = {'warehouses': warehouses}
    return render(request, 'inventory/warehouse_list.html', ctx)


@login_required
def warehouse_detail(request, pk):
    company = request.current_company
    warehouse = get_object_or_404(Warehouse, pk=pk, company=company)
    locations = warehouse.locations.all()
    ctx = {'warehouse': warehouse, 'locations': locations}
    return render(request, 'inventory/warehouse_detail.html', ctx)


@login_required
def warehouse_create(request):
    company = request.current_company
    if request.method == 'POST':
        form = WarehouseForm(request.POST)
        if form.is_valid():
            wh = form.save(commit=False)
            wh.company = company
            wh.save()
            messages.success(request, f'Entrepôt "{wh.name}" créé.')
            return redirect('inventory:warehouse_list')
    else:
        form = WarehouseForm()
    return render(request, 'inventory/warehouse_form.html', {'form': form, 'action': 'create'})


@login_required
def warehouse_edit(request, pk):
    company = request.current_company
    warehouse = get_object_or_404(Warehouse, pk=pk, company=company)
    if request.method == 'POST':
        form = WarehouseForm(request.POST, instance=warehouse)
        if form.is_valid():
            form.save()
            messages.success(request, 'Entrepôt mis à jour.')
            return redirect('inventory:warehouse_list')
    else:
        form = WarehouseForm(instance=warehouse)
    return render(request, 'inventory/warehouse_form.html', {'form': form, 'warehouse': warehouse, 'action': 'edit'})


@login_required
def warehouse_delete(request, pk):
    company = request.current_company
    warehouse = get_object_or_404(Warehouse, pk=pk, company=company)
    if request.method == 'POST':
        name = warehouse.name
        warehouse.delete()
        messages.success(request, f'Entrepôt "{name}" supprimé.')
        return redirect('inventory:warehouse_list')
    return render(request, 'inventory/warehouse_confirm_delete.html', {'warehouse': warehouse})


# --- Stock Movements ---

@login_required
def movement_list(request):
    company = request.current_company
    q = request.GET.get('q', '')
    mv_type = request.GET.get('type', '')
    movements = StockMovement.objects.filter(company=company)
    if q:
        movements = movements.filter(Q(product__name__icontains=q) | Q(reference__icontains=q))
    if mv_type:
        movements = movements.filter(movement_type=mv_type)
    ctx = {
        'movements': movements[:100],
        'q': q,
        'mv_type': mv_type,
        'type_choices': StockMovement.MOVEMENT_TYPES,
    }
    return render(request, 'inventory/movement_list.html', ctx)


@login_required
def movement_create(request):
    company = request.current_company
    if request.method == 'POST':
        form = StockMovementForm(request.POST)
        if form.is_valid():
            mv = form.save(commit=False)
            mv.company = company
            mv.created_by = request.user
            mv.save()
            product = mv.product
            if mv.movement_type == 'in':
                product.stock_quantity += mv.quantity
            elif mv.movement_type in ('out', 'loss'):
                product.stock_quantity -= mv.quantity
            elif mv.movement_type == 'adjustment':
                product.stock_quantity = mv.quantity
            product.save()
            messages.success(request, f'Mouvement enregistré pour {product.name}.')
            return redirect('inventory:movement_list')
    else:
        form = StockMovementForm()
        form.fields['product'].queryset = Product.objects.filter(company=company, is_active=True)
    return render(request, 'inventory/movement_form.html', {'form': form, 'action': 'create'})
