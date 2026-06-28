"""
competitor_intelligence/services/analysis_service.py
Analyse concurrentielle et scoring.
"""
from django.db.models import Avg, Count


def generate_competitor_score(competitor):
    """
    Calcule un score global pour un concurrent (0-100).
    Basé sur le nombre de produits, avantages, trafic estimé, promotions.
    """
    score = 0

    products_count = competitor.products.filter(is_active=True).count()
    score += min(products_count * 2, 30)

    advantages_count = competitor.advantages.count()
    score += min(advantages_count * 5, 25)

    latest_traffic = competitor.traffic_estimates.order_by('-measured_at').first()
    if latest_traffic and latest_traffic.estimated_monthly_visitors:
        visitors = latest_traffic.estimated_monthly_visitors
        if visitors > 1_000_000:
            score += 25
        elif visitors > 100_000:
            score += 15
        elif visitors > 10_000:
            score += 10
        else:
            score += 5

    promotions = competitor.products.filter(
        is_active=True, old_price__isnull=False,
    ).count()
    score += min(promotions * 3, 20)

    return min(score, 100)


def analyze_market_position(company, category=None):
    """Analyse la position sur le marché par rapport aux concurrents."""
    from apps.competitor_intelligence.models import Competitor, CompetitorProduct
    from django.db.models import Avg

    competitors = Competitor.objects.filter(company=company, is_active=True)
    product_qs  = CompetitorProduct.objects.filter(company=company, is_active=True, price__isnull=False)
    if category:
        product_qs = product_qs.filter(category__icontains=category)

    avg_price    = product_qs.aggregate(avg=Avg('price'))['avg']
    total_tracked = product_qs.count()

    ranking = []
    for c in competitors:
        score = generate_competitor_score(c)
        ranking.append({'competitor': c, 'score': score})
    ranking.sort(key=lambda x: x['score'], reverse=True)

    return {
        'competitors_count': competitors.count(),
        'products_tracked':  total_tracked,
        'avg_market_price':  avg_price,
        'ranking':           ranking,
    }


def generate_swot_analysis(company, competitor):
    """Génère une analyse SWOT simplifiée basée sur les données disponibles."""
    from apps.competitor_intelligence.models import CompetitorAdvantage

    their_advantages = list(
        CompetitorAdvantage.objects.filter(company=company, competitor=competitor)
        .order_by('-score')
        .values('title', 'advantage_type', 'score')[:5]
    )

    return {
        'competitor':        competitor,
        'their_strengths':   their_advantages,
        'opportunities':     _detect_opportunities(company, competitor),
        'threats':           _detect_threats(company, competitor),
    }


def _detect_opportunities(company, competitor):
    """Détecte les opportunités basées sur les lacunes du concurrent."""
    from apps.competitor_intelligence.services.product_tracker import calculate_product_gap
    gap = calculate_product_gap(company, competitor)
    opportunities = [f'Catégorie manquante : {cat}' for cat in gap['missing_categories'][:3]]
    return opportunities


def _detect_threats(company, competitor):
    """Détecte les menaces basées sur les avantages du concurrent."""
    from apps.competitor_intelligence.models import CompetitorAdvantage
    threats = []
    top_adv = CompetitorAdvantage.objects.filter(
        company=company, competitor=competitor, score__gte=7,
    ).order_by('-score')[:3]
    for adv in top_adv:
        threats.append(f'{adv.get_advantage_type_display()} : {adv.title}')
    return threats


def compare_multiple_competitors(company, competitor_ids):
    """Compare plusieurs concurrents sur les métriques clés."""
    from apps.competitor_intelligence.models import Competitor, CompetitorProduct
    from django.db.models import Avg, Count

    results = []
    for cid in competitor_ids:
        try:
            c = Competitor.objects.get(pk=cid, company=company)
        except Competitor.DoesNotExist:
            continue

        products = CompetitorProduct.objects.filter(company=company, competitor=c, is_active=True)
        latest_traffic = c.traffic_estimates.order_by('-measured_at').first()

        results.append({
            'competitor':        c,
            'score':             generate_competitor_score(c),
            'products_count':    products.count(),
            'avg_price':         products.aggregate(avg=Avg('price'))['avg'],
            'promotions_count':  products.filter(old_price__isnull=False).count(),
            'advantages_count':  c.advantages.count(),
            'monthly_visitors':  latest_traffic.estimated_monthly_visitors if latest_traffic else None,
            'unread_alerts':     c.alerts.filter(is_read=False).count(),
        })

    results.sort(key=lambda x: x['score'], reverse=True)
    return results


def generate_recommendations(company, competitor):
    """Génère des recommandations stratégiques basées sur l'analyse."""
    from apps.competitor_intelligence.services.price_tracker import calculate_price_index
    recommendations = []

    price_data = calculate_price_index(company)
    if price_data['gap_percent'] is not None:
        if price_data['gap_percent'] > 10:
            recommendations.append('Nos prix sont significativement plus élevés. Envisagez une révision tarifaire.')
        elif price_data['gap_percent'] < -10:
            recommendations.append('Nos prix sont très compétitifs. Mettez cet avantage en avant.')

    from apps.competitor_intelligence.services.product_tracker import calculate_product_gap
    gap = calculate_product_gap(company, competitor)
    if gap['gap_count'] > 0:
        cats = ', '.join(gap['missing_categories'][:3])
        recommendations.append(f'Gamme à développer : {cats}.')

    top_adv = competitor.advantages.order_by('-score').first()
    if top_adv:
        recommendations.append(f'Surveiller : {top_adv.title} (score {top_adv.score}/10).')

    return recommendations
