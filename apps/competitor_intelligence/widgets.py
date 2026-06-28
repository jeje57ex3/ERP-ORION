"""
apps/competitor_intelligence/widgets.py — Widgets dashboard Orion ERP
Chaque widget peut être inclus dans le dashboard personnalisable.
"""


class BaseCompetitorWidget:
    template_name = None
    title = ''
    icon  = 'bi-binoculars'

    def __init__(self, company, request=None):
        self.company = company
        self.request = request

    def get_context(self):
        return {'company': self.company, 'widget_title': self.title}

    def render(self):
        from django.template.loader import render_to_string
        ctx = self.get_context()
        return render_to_string(self.template_name, ctx)


class PriceIndexWidget(BaseCompetitorWidget):
    template_name = 'competitor_intelligence/widgets/price_index_widget.html'
    title = 'Indice Prix'
    icon  = 'bi-tag'

    def get_context(self):
        from apps.competitor_intelligence.services.price_tracker import calculate_price_index
        ctx = super().get_context()
        ctx['price_data'] = calculate_price_index(self.company)
        return ctx


class TrafficEstimateWidget(BaseCompetitorWidget):
    template_name = 'competitor_intelligence/widgets/traffic_estimate_widget.html'
    title = 'Trafic estimé concurrents'
    icon  = 'bi-bar-chart-line'

    def get_context(self):
        from apps.competitor_intelligence.models import Competitor
        from apps.competitor_intelligence.services.traffic_estimator import compare_competitor_traffic
        ctx = super().get_context()
        competitors = list(Competitor.objects.filter(company=self.company, is_active=True)[:5])
        ctx['traffic_data'] = compare_competitor_traffic(self.company, competitors)
        return ctx


class ProductGapWidget(BaseCompetitorWidget):
    template_name = 'competitor_intelligence/widgets/product_gap_widget.html'
    title = 'Écart produits'
    icon  = 'bi-grid-3x3'

    def get_context(self):
        from apps.competitor_intelligence.models import Competitor
        from apps.competitor_intelligence.services.product_tracker import calculate_product_gap
        ctx = super().get_context()
        competitors = Competitor.objects.filter(company=self.company, is_active=True)[:3]
        gaps = []
        for c in competitors:
            gap = calculate_product_gap(self.company, c)
            gaps.append({'competitor': c, **gap})
        ctx['gaps'] = gaps
        return ctx


class CompetitorAlertsWidget(BaseCompetitorWidget):
    template_name = 'competitor_intelligence/widgets/competitor_alerts_widget.html'
    title = 'Alertes concurrentes'
    icon  = 'bi-bell'

    def get_context(self):
        from apps.competitor_intelligence.models import CompetitorAlert
        ctx = super().get_context()
        ctx['alerts'] = CompetitorAlert.objects.filter(
            company=self.company, is_read=False,
        ).select_related('competitor').order_by('-created_at')[:8]
        return ctx


class MarketPositionWidget(BaseCompetitorWidget):
    template_name = 'competitor_intelligence/widgets/market_position_widget.html'
    title = 'Position marché'
    icon  = 'bi-bullseye'

    def get_context(self):
        from apps.competitor_intelligence.services.analysis_service import analyze_market_position
        ctx = super().get_context()
        ctx['market_data'] = analyze_market_position(self.company)
        return ctx


class MultiSiteComparisonWidget(BaseCompetitorWidget):
    template_name = 'competitor_intelligence/widgets/multi_site_comparison_widget.html'
    title = 'Comparaison multi-sites'
    icon  = 'bi-layout-split'

    def get_context(self):
        from apps.competitor_intelligence.models import Competitor
        from apps.competitor_intelligence.services.analysis_service import (
            compare_multiple_competitors, generate_competitor_score,
        )
        ctx = super().get_context()
        ids = list(Competitor.objects.filter(company=self.company, is_active=True).values_list('pk', flat=True)[:6])
        ctx['comparison'] = compare_multiple_competitors(self.company, ids)
        return ctx


class TopCompetitorProductsWidget(BaseCompetitorWidget):
    template_name = 'competitor_intelligence/widgets/top_products_widget.html'
    title = 'Top produits concurrents'
    icon  = 'bi-star'

    def get_context(self):
        from apps.competitor_intelligence.models import CompetitorProduct
        ctx = super().get_context()
        ctx['products'] = CompetitorProduct.objects.filter(
            company=self.company, is_active=True, price__isnull=False,
        ).select_related('competitor').order_by('price')[:10]
        return ctx


class PriceChangeWidget(BaseCompetitorWidget):
    template_name = 'competitor_intelligence/widgets/price_change_widget.html'
    title = 'Variations de prix récentes'
    icon  = 'bi-graph-down-arrow'

    def get_context(self):
        from apps.competitor_intelligence.models import CompetitorAlert
        ctx = super().get_context()
        ctx['changes'] = CompetitorAlert.objects.filter(
            company=self.company,
            alert_type__in=['price_drop', 'price_increase'],
        ).select_related('competitor').order_by('-created_at')[:5]
        return ctx


AVAILABLE_WIDGETS = {
    'price_index':        PriceIndexWidget,
    'traffic_estimate':   TrafficEstimateWidget,
    'product_gap':        ProductGapWidget,
    'competitor_alerts':  CompetitorAlertsWidget,
    'market_position':    MarketPositionWidget,
    'multi_site':         MultiSiteComparisonWidget,
    'top_products':       TopCompetitorProductsWidget,
    'price_changes':      PriceChangeWidget,
}
