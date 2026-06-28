from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import Creation, CreationOrder
from . import services


@login_required
def dashboard(request):
    company = request.current_company
    stats = services.get_creation_stats(company)
    recent = Creation.objects.filter(company=company).order_by('-updated_at')[:5]
    return render(request, 'siecle_creations/dashboard.html', {
        'stats': stats,
        'recent': recent,
    })


@login_required
def catalog(request):
    company = request.current_company
    category = request.GET.get('category', '')
    status = request.GET.get('status', 'published')
    creations = services.get_catalog(company, category=category or None, status=status or None,
                                     brand_key='siecle')
    return render(request, 'siecle_creations/catalog.html', {
        'creations': creations,
        'category': category,
        'status': status,
    })


@login_required
def creation_detail(request, pk):
    company = request.current_company
    creation = get_object_or_404(Creation, pk=pk, company=company)
    orders = CreationOrder.objects.filter(creation=creation).order_by('-created_at')[:10]
    return render(request, 'siecle_creations/creation_detail.html', {
        'creation': creation,
        'orders': orders,
    })


@login_required
def publish_creation(request, pk):
    company = request.current_company
    creation = get_object_or_404(Creation, pk=pk, company=company)
    if request.method == 'POST':
        services.publish_creation(creation)
        messages.success(request, f'Création "{creation.title}" publiée.')
    return redirect('siecle_creations:detail', pk=pk)


@login_required
def archive_creation(request, pk):
    company = request.current_company
    creation = get_object_or_404(Creation, pk=pk, company=company)
    if request.method == 'POST':
        services.archive_creation(creation)
        messages.success(request, f'Création "{creation.title}" archivée.')
    return redirect('siecle_creations:catalog')


@login_required
def collections_view(request):
    """Éditions limitées et pièces uniques — alias URL /erp/siecle/creation/collections/"""
    company = request.current_company
    creations = Creation.objects.filter(
        company=company, is_limited_edition=True
    ).order_by('-created_at')
    return render(request, 'siecle_creations/catalog.html', {
        'creations': creations,
        'category': 'edition_limitee',
        'status': '',
        'page_subtitle': 'Éditions limitées & pièces uniques SIÈCLE',
    })


@login_required
def campaigns_view(request):
    """Vue campagnes/commandes — alias URL /erp/siecle/creation/campaigns/"""
    company = request.current_company
    orders = CreationOrder.objects.filter(company=company).select_related(
        'creation', 'customer'
    ).order_by('-created_at')[:50]
    return render(request, 'siecle_creations/campaigns.html', {
        'orders': orders,
    })
