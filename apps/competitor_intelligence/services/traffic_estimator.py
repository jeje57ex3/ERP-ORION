"""
competitor_intelligence/services/traffic_estimator.py
Estimation légale du trafic concurrentiel.
IMPORTANT: Toujours afficher les données comme "estimées".
"""
import csv
import io
from django.utils import timezone


def add_manual_traffic_estimate(company, competitor, visitors_monthly, source='', confidence_score=5, source_type='manual', site=None):
    """
    Ajoute une estimation manuelle de trafic.
    Les visiteurs doivent toujours être présentés comme ESTIMÉS.
    """
    from apps.competitor_intelligence.models import CompetitorTrafficEstimate

    estimate = CompetitorTrafficEstimate.objects.create(
        company=company,
        competitor=competitor,
        site=site,
        estimated_monthly_visitors=visitors_monthly,
        estimated_daily_visitors=visitors_monthly // 30 if visitors_monthly else None,
        traffic_source=source,
        confidence_score=confidence_score,
        source_type=source_type,
    )
    return estimate


def import_traffic_estimates_from_csv(company, csv_content: str):
    """
    Importe des estimations de trafic depuis un CSV.
    Colonnes : competitor_name, monthly_visitors, source, confidence, source_type
    """
    from apps.competitor_intelligence.models import Competitor

    reader = csv.DictReader(io.StringIO(csv_content))
    created, errors = 0, []

    for i, row in enumerate(reader, start=2):
        try:
            competitor_name = row.get('competitor_name', '').strip()
            if not competitor_name:
                continue
            try:
                competitor = Competitor.objects.get(company=company, name__iexact=competitor_name)
            except Competitor.DoesNotExist:
                errors.append(f'Ligne {i}: concurrent "{competitor_name}" introuvable')
                continue

            visitors = row.get('monthly_visitors', '').strip()
            if visitors:
                visitors = int(visitors.replace(' ', '').replace(',', ''))
            else:
                visitors = None

            add_manual_traffic_estimate(
                company=company,
                competitor=competitor,
                visitors_monthly=visitors,
                source=row.get('source', '').strip(),
                confidence_score=int(row.get('confidence', 5)),
                source_type=row.get('source_type', 'csv').strip() or 'csv',
            )
            created += 1
        except Exception as e:
            errors.append(f'Ligne {i}: {e}')

    return {'created': created, 'errors': errors}


def calculate_traffic_trend(competitor):
    """
    Calcule la tendance du trafic estimé d'un concurrent sur les 6 derniers mois.
    """
    from apps.competitor_intelligence.models import CompetitorTrafficEstimate
    from datetime import timedelta
    from django.db.models import Avg

    now = timezone.now()
    points = []
    for months_ago in range(5, -1, -1):
        start = now - timedelta(days=30 * (months_ago + 1))
        end   = now - timedelta(days=30 * months_ago)
        avg   = CompetitorTrafficEstimate.objects.filter(
            competitor=competitor,
            measured_at__range=(start, end),
        ).aggregate(avg=Avg('estimated_monthly_visitors'))['avg']
        points.append({
            'period': start.strftime('%m/%Y'),
            'avg_visitors': int(avg) if avg else None,
        })
    return points


def compare_competitor_traffic(company, competitors):
    """Compare le trafic estimé de plusieurs concurrents."""
    from apps.competitor_intelligence.models import CompetitorTrafficEstimate
    from django.db.models import Avg

    results = []
    for c in competitors:
        latest = CompetitorTrafficEstimate.objects.filter(
            company=company, competitor=c,
        ).order_by('-measured_at').first()
        results.append({
            'competitor':               c,
            'estimated_monthly':        latest.estimated_monthly_visitors if latest else None,
            'confidence':               latest.confidence_score if latest else None,
            'source_type':              latest.get_source_type_display() if latest else '—',
            'measured_at':              latest.measured_at if latest else None,
        })
    return sorted(results, key=lambda x: x['estimated_monthly'] or 0, reverse=True)
