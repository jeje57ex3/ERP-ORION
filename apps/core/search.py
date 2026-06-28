"""
Global search across company data.
Queries use the active company DB alias (set by middleware/router).
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.db.models import Q


RESULT_LIMIT = 5


def _search_crm(q):
    try:
        from apps.crm.models import Customer
        return [
            {
                'type': 'client', 'label': 'Client',
                'icon': 'bi-person', 'color': 'primary',
                'url': f'/crm/clients/{c.pk}/',
                'title': c.name,
                'subtitle': c.email or '',
            }
            for c in Customer.objects.filter(
                Q(name__icontains=q) | Q(email__icontains=q) | Q(phone__icontains=q)
            )[:RESULT_LIMIT]
        ]
    except Exception:
        return []


def _search_sales(q):
    results = []
    try:
        from apps.sales.models import Invoice, Quote
        for inv in Invoice.objects.filter(
            Q(number__icontains=q) | Q(subject__icontains=q)
        )[:RESULT_LIMIT]:
            results.append({
                'type': 'facture', 'label': 'Facture',
                'icon': 'bi-receipt', 'color': 'success',
                'url': f'/sales/factures/{inv.pk}/',
                'title': inv.number,
                'subtitle': inv.subject or '',
            })
        for quote in Quote.objects.filter(
            Q(number__icontains=q) | Q(subject__icontains=q)
        )[:RESULT_LIMIT]:
            results.append({
                'type': 'devis', 'label': 'Devis',
                'icon': 'bi-file-earmark-text', 'color': 'warning',
                'url': f'/sales/devis/{quote.pk}/',
                'title': quote.number,
                'subtitle': quote.subject or '',
            })
    except Exception:
        pass
    return results


def _search_btp(q):
    try:
        from apps.btp.models import Project
        return [
            {
                'type': 'chantier', 'label': 'Chantier',
                'icon': 'bi-building-gear', 'color': 'info',
                'url': f'/btp/chantiers/{p.pk}/',
                'title': p.name,
                'subtitle': getattr(p, 'reference', '') or '',
            }
            for p in Project.objects.filter(
                Q(name__icontains=q) | Q(reference__icontains=q)
            )[:RESULT_LIMIT]
        ]
    except Exception:
        return []


def _search_inventory(q):
    try:
        from apps.inventory.models import Product
        return [
            {
                'type': 'produit', 'label': 'Produit',
                'icon': 'bi-box-seam', 'color': 'secondary',
                'url': f'/inventory/produits/{p.pk}/',
                'title': p.name,
                'subtitle': p.reference or '',
            }
            for p in Product.objects.filter(
                Q(name__icontains=q) | Q(reference__icontains=q)
            )[:RESULT_LIMIT]
        ]
    except Exception:
        return []


@login_required
def global_search(request):
    q = request.GET.get('q', '').strip()
    results = []
    if len(q) >= 2:
        results += _search_crm(q)
        results += _search_sales(q)
        results += _search_btp(q)
        results += _search_inventory(q)

    return render(request, 'core/search_results.html', {
        'query': q,
        'results': results,
        'result_count': len(results),
        'page_title': f'Recherche : {q}' if q else 'Recherche globale',
        'active_module': 'dashboard',
    })
