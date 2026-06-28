from django.utils import timezone
from datetime import timedelta
from .models import AnalyticsForecast, AnalyticsInsight


def upsert_forecast(company, forecast_type, period, value, *, brand_key='',
                    lower_bound=None, upper_bound=None, confidence=0.8,
                    model_version='v1', raw_data=None):
    forecast, _ = AnalyticsForecast.objects.update_or_create(
        company=company, forecast_type=forecast_type, period=period, brand_key=brand_key,
        defaults={
            'value': value, 'lower_bound': lower_bound, 'upper_bound': upper_bound,
            'confidence': confidence, 'model_version': model_version,
            'raw_data': raw_data or {},
        },
    )
    return forecast


def create_insight(company, insight_type, title, message, *, brand_key='',
                   source_module='', data=None, score=0.0, expires_at=None):
    return AnalyticsInsight.objects.create(
        company=company, brand_key=brand_key, insight_type=insight_type,
        title=title, message=message, source_module=source_module,
        data=data or {}, score=score, expires_at=expires_at,
    )


def get_active_insights(company, *, brand_key=None, insight_type=None, limit=20):
    now = timezone.now()
    qs = AnalyticsInsight.objects.filter(
        company=company, is_dismissed=False,
    ).filter(
        __import__('django.db.models', fromlist=['Q']).Q(expires_at__isnull=True) |
        __import__('django.db.models', fromlist=['Q']).Q(expires_at__gt=now)
    )
    if brand_key:
        qs = qs.filter(brand_key=brand_key)
    if insight_type:
        qs = qs.filter(insight_type=insight_type)
    return qs.order_by('-score', '-created_at')[:limit]


def dismiss_insight(insight):
    insight.is_dismissed = True
    insight.save(update_fields=['is_dismissed'])
    return insight


def mark_insight_read(insight):
    insight.is_read = True
    insight.save(update_fields=['is_read'])
    return insight


def get_forecasts(company, forecast_type, *, brand_key='', periods=None):
    qs = AnalyticsForecast.objects.filter(
        company=company, forecast_type=forecast_type, brand_key=brand_key,
    )
    if periods:
        qs = qs.filter(period__in=periods)
    return qs.order_by('period')


def compute_revenue_forecast(company, brand_key=''):
    """Simple moving-average forecast from existing SalesOrder data."""
    try:
        from apps.sales.models import SalesOrder
        from django.db.models import Sum
        from datetime import date
        today = date.today()
        months = []
        for i in range(3, 0, -1):
            month_start = (today.replace(day=1) - timedelta(days=30 * i))
            month_start = month_start.replace(day=1)
            if i > 1:
                month_end = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
            else:
                month_end = today
            qs = SalesOrder.objects.filter(company=company, created_at__date__gte=month_start,
                                           created_at__date__lte=month_end)
            if brand_key:
                qs = qs.filter(brand_key=brand_key)
            total = qs.aggregate(t=Sum('total_amount'))['t'] or 0
            months.append(float(total))
        avg = sum(months) / len(months) if months else 0
        next_period = (today.replace(day=1) + timedelta(days=32)).replace(day=1).strftime('%Y-%m')
        return upsert_forecast(company, 'revenue', next_period, avg,
                               brand_key=brand_key, confidence=0.7,
                               raw_data={'history': months})
    except Exception:
        return None


def get_analytics_stats(company):
    return {
        'total_forecasts': AnalyticsForecast.objects.filter(company=company).count(),
        'active_insights': AnalyticsInsight.objects.filter(
            company=company, is_dismissed=False
        ).count(),
        'unread_insights': AnalyticsInsight.objects.filter(
            company=company, is_dismissed=False, is_read=False
        ).count(),
    }
