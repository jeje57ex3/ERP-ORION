from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from .models import AnalyticsInsight
from .services import get_active_insights, get_analytics_stats, dismiss_insight, mark_insight_read, get_forecasts


@login_required
def analytics_dashboard(request):
    company = request.current_company
    if not company:
        return redirect('core:dashboard')
    insight_type = request.GET.get('type', '')
    brand_key = request.GET.get('brand', '')
    insights = get_active_insights(company,
                                   insight_type=insight_type or None,
                                   brand_key=brand_key or None)
    stats = get_analytics_stats(company)
    revenue_forecasts = get_forecasts(company, 'revenue', brand_key=brand_key)
    return render(request, 'predictive_analytics/dashboard.html', {
        'page_title': 'Analytique prédictive',
        'insights': insights, 'stats': stats,
        'revenue_forecasts': revenue_forecasts,
        'filter_type': insight_type, 'filter_brand': brand_key,
    })


@login_required
@require_POST
def dismiss_insight_view(request, pk):
    company = request.current_company
    insight = AnalyticsInsight.objects.get(pk=pk, company=company)
    dismiss_insight(insight)
    return redirect('predictive_analytics:dashboard')
