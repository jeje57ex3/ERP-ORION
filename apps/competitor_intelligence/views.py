"""
apps/competitor_intelligence/views.py — Vues analyse concurrentielle Orion ERP
"""
import io
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import FileResponse, Http404, JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q, Count, Avg

from .models import (
    Competitor, CompetitorSite, CompetitorProduct, CompetitorPriceHistory,
    CompetitorAdvantage, CompetitorTrafficEstimate, CompetitorComparison, CompetitorAlert,
)
from .forms import (
    CompetitorForm, CompetitorSiteForm, CompetitorProductForm,
    CompetitorAdvantageForm, TrafficEstimateForm, CSVImportForm, ComparisonForm,
)
from .services.analysis_service import (
    generate_competitor_score, analyze_market_position,
    compare_multiple_competitors, generate_swot_analysis, generate_recommendations,
)
from .services.price_tracker import calculate_price_index
from .services.traffic_estimator import compare_competitor_traffic


def _get_company(request):
    return getattr(request, 'current_company', None)


@login_required
def dashboard(request):
    company = _get_company(request)
    competitors = Competitor.objects.filter(company=company, is_active=True).annotate(
        products_count=Count('products', filter=Q(products__is_active=True)),
        alerts_count=Count('alerts', filter=Q(alerts__is_read=False)),
    )
    price_index  = calculate_price_index(company) if company else {}
    market_pos   = analyze_market_position(company) if company else {}
    recent_alerts = CompetitorAlert.objects.filter(company=company, is_read=False).order_by('-created_at')[:6]

    return render(request, 'competitor_intelligence/dashboard.html', {
        'page_title':    'Analyse concurrentielle',
        'competitors':   competitors[:6],
        'competitors_count': competitors.count(),
        'price_index':   price_index,
        'market_pos':    market_pos,
        'recent_alerts': recent_alerts,
        'unread_alerts': CompetitorAlert.objects.filter(company=company, is_read=False).count(),
    })


@login_required
def competitor_list(request):
    company = _get_company(request)
    qs = Competitor.objects.filter(company=company).annotate(
        products_count=Count('products', filter=Q(products__is_active=True)),
        alerts_count=Count('alerts', filter=Q(alerts__is_read=False)),
    ).order_by('name')

    search = request.GET.get('q', '')
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(industry__icontains=search))

    active_filter = request.GET.get('active', '')
    if active_filter == '1':
        qs = qs.filter(is_active=True)
    elif active_filter == '0':
        qs = qs.filter(is_active=False)

    return render(request, 'competitor_intelligence/competitor_list.html', {
        'page_title':  'Concurrents',
        'competitors': qs,
        'search':      search,
    })


@login_required
def competitor_detail(request, pk):
    company    = _get_company(request)
    competitor = get_object_or_404(Competitor, pk=pk, company=company)
    products   = competitor.products.filter(is_active=True).order_by('category', 'name')
    advantages = competitor.advantages.order_by('-score')[:10]
    alerts     = competitor.alerts.order_by('-created_at')[:10]
    traffic    = competitor.traffic_estimates.order_by('-measured_at').first()
    score      = generate_competitor_score(competitor)
    swot       = generate_swot_analysis(company, competitor)
    recommendations = generate_recommendations(company, competitor)

    return render(request, 'competitor_intelligence/competitor_detail.html', {
        'page_title':       competitor.name,
        'competitor':       competitor,
        'products':         products,
        'advantages':       advantages,
        'alerts':           alerts,
        'traffic':          traffic,
        'score':            score,
        'swot':             swot,
        'recommendations':  recommendations,
    })


@login_required
def competitor_create(request):
    company = _get_company(request)
    if request.method == 'POST':
        form = CompetitorForm(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.company    = company
            obj.created_by = request.user
            obj.save()
            messages.success(request, f'Concurrent "{obj.name}" créé.')
            return redirect('competitor:detail', pk=obj.pk)
    else:
        form = CompetitorForm()
    return render(request, 'competitor_intelligence/competitor_create.html', {
        'page_title': 'Ajouter un concurrent',
        'form': form,
    })


@login_required
def competitor_edit(request, pk):
    company    = _get_company(request)
    competitor = get_object_or_404(Competitor, pk=pk, company=company)
    if request.method == 'POST':
        form = CompetitorForm(request.POST, request.FILES, instance=competitor)
        if form.is_valid():
            form.save()
            messages.success(request, 'Concurrent mis à jour.')
            return redirect('competitor:detail', pk=competitor.pk)
    else:
        form = CompetitorForm(instance=competitor)
    return render(request, 'competitor_intelligence/competitor_create.html', {
        'page_title': f'Modifier {competitor.name}',
        'form':       form,
        'competitor': competitor,
    })


@login_required
def product_list(request):
    company = _get_company(request)
    qs = CompetitorProduct.objects.filter(company=company, is_active=True).select_related('competitor')

    search    = request.GET.get('q', '')
    category  = request.GET.get('category', '')
    competitor_id = request.GET.get('competitor', '')

    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(brand__icontains=search))
    if category:
        qs = qs.filter(category__icontains=category)
    if competitor_id:
        qs = qs.filter(competitor_id=competitor_id)

    paginator = Paginator(qs.order_by('category', 'name'), 25)
    page_obj  = paginator.get_page(request.GET.get('page'))
    categories = qs.values_list('category', flat=True).distinct().order_by()
    competitors = Competitor.objects.filter(company=company, is_active=True)

    return render(request, 'competitor_intelligence/competitor_product_list.html', {
        'page_title':  'Produits concurrents',
        'page_obj':    page_obj,
        'categories':  sorted(set(c for c in categories if c)),
        'competitors': competitors,
        'search':      search,
        'category':    category,
        'competitor_id': competitor_id,
    })


@login_required
def add_product(request, competitor_pk):
    company    = _get_company(request)
    competitor = get_object_or_404(Competitor, pk=competitor_pk, company=company)
    if request.method == 'POST':
        form = CompetitorProductForm(request.POST)
        if form.is_valid():
            from .services.product_tracker import add_competitor_product_manually
            data = form.cleaned_data
            add_competitor_product_manually(company, competitor, data)
            messages.success(request, 'Produit concurrent ajouté.')
            return redirect('competitor:detail', pk=competitor.pk)
    else:
        form = CompetitorProductForm()
    return render(request, 'competitor_intelligence/product_form.html', {
        'page_title': f'Ajouter produit — {competitor.name}',
        'form':       form,
        'competitor': competitor,
    })


@login_required
def price_history(request):
    company = _get_company(request)
    qs = CompetitorPriceHistory.objects.filter(company=company).select_related(
        'competitor_product', 'competitor_product__competitor',
    ).order_by('-checked_at')

    competitor_id = request.GET.get('competitor', '')
    if competitor_id:
        qs = qs.filter(competitor_product__competitor_id=competitor_id)

    paginator = Paginator(qs, 30)
    page_obj  = paginator.get_page(request.GET.get('page'))
    competitors = Competitor.objects.filter(company=company, is_active=True)

    price_index = calculate_price_index(company)

    return render(request, 'competitor_intelligence/competitor_price_history.html', {
        'page_title':  'Prix & Historique',
        'page_obj':    page_obj,
        'competitors': competitors,
        'competitor_id': competitor_id,
        'price_index': price_index,
    })


@login_required
def traffic_view(request):
    company = _get_company(request)
    competitors = list(Competitor.objects.filter(company=company, is_active=True))
    traffic_comparison = compare_competitor_traffic(company, competitors)

    if request.method == 'POST':
        form = TrafficEstimateForm(request.POST)
        competitor_pk = request.POST.get('competitor_pk')
        if form.is_valid() and competitor_pk:
            try:
                c = Competitor.objects.get(pk=competitor_pk, company=company)
                est = form.save(commit=False)
                est.company    = company
                est.competitor = c
                est.save()
                messages.success(request, 'Estimation de trafic ajoutée.')
            except Competitor.DoesNotExist:
                pass
            return redirect('competitor:traffic')
    else:
        form = TrafficEstimateForm()

    return render(request, 'competitor_intelligence/traffic.html', {
        'page_title':        'Trafic estimé',
        'traffic_comparison': traffic_comparison,
        'competitors':        competitors,
        'form':               form,
    })


@login_required
def advantages_view(request):
    company = _get_company(request)
    qs = CompetitorAdvantage.objects.filter(company=company).select_related('competitor').order_by('-score')

    competitor_id = request.GET.get('competitor', '')
    if competitor_id:
        qs = qs.filter(competitor_id=competitor_id)

    competitors = Competitor.objects.filter(company=company, is_active=True)
    return render(request, 'competitor_intelligence/advantages.html', {
        'page_title':  'Avantages concurrents',
        'advantages':  qs,
        'competitors': competitors,
        'competitor_id': competitor_id,
    })


@login_required
def add_advantage(request, competitor_pk):
    company    = _get_company(request)
    competitor = get_object_or_404(Competitor, pk=competitor_pk, company=company)
    if request.method == 'POST':
        form = CompetitorAdvantageForm(request.POST)
        if form.is_valid():
            adv = form.save(commit=False)
            adv.company    = company
            adv.competitor = competitor
            adv.created_by = request.user
            adv.save()
            messages.success(request, 'Avantage concurrent ajouté.')
            return redirect('competitor:detail', pk=competitor.pk)
    else:
        form = CompetitorAdvantageForm()
    return render(request, 'competitor_intelligence/advantage_form.html', {
        'page_title': f'Avantage — {competitor.name}',
        'form':       form,
        'competitor': competitor,
    })


@login_required
def compare_view(request):
    company     = _get_company(request)
    competitors = Competitor.objects.filter(company=company, is_active=True)

    selected_ids = request.GET.getlist('c')
    comparison_data = []
    if selected_ids:
        comparison_data = compare_multiple_competitors(company, [int(i) for i in selected_ids])

    return render(request, 'competitor_intelligence/competitor_compare.html', {
        'page_title':     'Comparaison multi-concurrents',
        'competitors':    competitors,
        'selected_ids':   selected_ids,
        'comparison_data': comparison_data,
    })


@login_required
def alerts_view(request):
    company = _get_company(request)
    qs = CompetitorAlert.objects.filter(company=company).select_related('competitor').order_by('-created_at')

    if request.GET.get('unread_only') == '1':
        qs = qs.filter(is_read=False)

    if request.method == 'POST' and request.POST.get('mark_read'):
        qs.filter(is_read=False).update(is_read=True)
        messages.success(request, 'Toutes les alertes marquées comme lues.')
        return redirect('competitor:alerts')

    paginator = Paginator(qs, 20)
    page_obj  = paginator.get_page(request.GET.get('page'))

    return render(request, 'competitor_intelligence/alerts.html', {
        'page_title': 'Alertes concurrentielles',
        'page_obj':   page_obj,
        'unread_count': CompetitorAlert.objects.filter(company=company, is_read=False).count(),
    })


@login_required
def reports_view(request):
    company     = _get_company(request)
    competitors = Competitor.objects.filter(company=company, is_active=True)

    if request.method == 'POST':
        ids      = request.POST.getlist('competitor_ids')
        fmt      = request.POST.get('format', 'excel')
        ids_int  = [int(i) for i in ids if i.isdigit()]

        if not ids_int:
            messages.error(request, 'Sélectionnez au moins un concurrent.')
            return redirect('competitor:reports')

        try:
            if fmt == 'pdf':
                from .services.report_service import generate_competitor_pdf_report
                buf = generate_competitor_pdf_report(company, ids_int)
                return FileResponse(buf, as_attachment=True, filename='analyse_concurrentielle.pdf',
                                    content_type='application/pdf')
            else:
                from .services.report_service import generate_competitor_excel_report
                buf = generate_competitor_excel_report(company, ids_int)
                return FileResponse(buf, as_attachment=True, filename='analyse_concurrentielle.xlsx',
                                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        except ImportError as e:
            messages.error(request, f'Dépendance manquante : {e}')

    return render(request, 'competitor_intelligence/competitor_report.html', {
        'page_title': 'Rapports concurrentiels',
        'competitors': competitors,
    })


@login_required
def csv_import(request):
    company     = _get_company(request)
    competitors = Competitor.objects.filter(company=company, is_active=True)

    if request.method == 'POST':
        form = CSVImportForm(request.POST, request.FILES, competitors=competitors)
        if form.is_valid():
            from .services.product_tracker import import_competitor_products_from_csv
            competitor_pk = form.cleaned_data['competitor']
            try:
                competitor = Competitor.objects.get(pk=competitor_pk, company=company)
                csv_file   = request.FILES['csv_file']
                content    = csv_file.read().decode('utf-8', errors='replace')
                result     = import_competitor_products_from_csv(company, competitor, content)
                messages.success(request,
                    f'{result["created"]} créés, {result["updated"]} mis à jour.'
                    + (f' {len(result["errors"])} erreurs.' if result["errors"] else '')
                )
            except Exception as e:
                messages.error(request, f'Erreur : {e}')
            return redirect('competitor:product_list')
    else:
        form = CSVImportForm(competitors=competitors)

    return render(request, 'competitor_intelligence/csv_import.html', {
        'page_title': 'Importer produits (CSV)',
        'form':       form,
    })


@login_required
def alert_mark_read(request, pk):
    company = _get_company(request)
    alert   = get_object_or_404(CompetitorAlert, pk=pk, company=company)
    alert.is_read = True
    alert.save(update_fields=['is_read'])
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'ok'})
    return redirect('competitor:alerts')
