"""
tests/test_predictive_analytics.py
Tests du module Analytique Prédictive.
"""
import pytest
from django.utils import timezone
from datetime import timedelta
from apps.core.models import Company
from apps.predictive_analytics.models import AnalyticsForecast, AnalyticsInsight
from apps.predictive_analytics.services import (
    upsert_forecast, create_insight, get_active_insights,
    dismiss_insight, mark_insight_read, get_forecasts, get_analytics_stats,
)


@pytest.fixture
def company(db):
    return Company.objects.create(name='Analytics SA', slug='analytics-sa', status='active', is_active=True)


@pytest.fixture
def insight(db, company):
    return create_insight(company, 'opportunity', 'Ventes en hausse',
                          'Le CA augmente de 15% ce mois.', score=0.85)


class TestUpsertForecast:
    def test_creates_forecast(self, db, company):
        f = upsert_forecast(company, 'revenue', '2026-07', 50000)
        assert f.pk is not None
        assert float(f.value) == 50000.0
        assert f.period == '2026-07'

    def test_updates_existing(self, db, company):
        f1 = upsert_forecast(company, 'revenue', '2026-07', 50000)
        f2 = upsert_forecast(company, 'revenue', '2026-07', 60000)
        assert f1.pk == f2.pk
        assert float(f2.value) == 60000.0

    def test_brand_key_separate_records(self, db, company):
        f1 = upsert_forecast(company, 'revenue', '2026-07', 10000, brand_key='siecle')
        f2 = upsert_forecast(company, 'revenue', '2026-07', 20000, brand_key='lunea')
        assert f1.pk != f2.pk

    def test_confidence_stored(self, db, company):
        f = upsert_forecast(company, 'cash_flow', '2026-07', 5000, confidence=0.9)
        assert f.confidence == 0.9


class TestCreateInsight:
    def test_creates_insight(self, db, company):
        ins = create_insight(company, 'risk', 'Risque churn', 'Perte potentielle client.', score=0.7)
        assert ins.pk is not None
        assert ins.insight_type == 'risk'

    def test_stores_metadata(self, db, company):
        ins = create_insight(company, 'trend', 'Tendance', 'msg', data={'metric': 42}, score=0.5)
        assert ins.data == {'metric': 42}

    def test_brand_key_stored(self, db, company):
        ins = create_insight(company, 'opportunity', 'Opp', 'msg', brand_key='siecle')
        assert ins.brand_key == 'siecle'


class TestGetActiveInsights:
    def test_returns_active(self, db, company, insight):
        result = list(get_active_insights(company))
        assert insight in result

    def test_excludes_dismissed(self, db, company, insight):
        dismiss_insight(insight)
        result = list(get_active_insights(company))
        assert insight not in result

    def test_excludes_expired(self, db, company):
        expired = create_insight(company, 'trend', 'Old', 'msg',
                                 expires_at=timezone.now() - timedelta(hours=1))
        result = list(get_active_insights(company))
        assert expired not in result

    def test_filter_by_type(self, db, company, insight):
        result = list(get_active_insights(company, insight_type='opportunity'))
        assert insight in result
        result_risk = list(get_active_insights(company, insight_type='risk'))
        assert insight not in result_risk

    def test_limit_respected(self, db, company):
        for i in range(10):
            create_insight(company, 'trend', f'T{i}', 'msg')
        result = list(get_active_insights(company, limit=5))
        assert len(result) <= 5


class TestMarkInsightRead:
    def test_marks_read(self, db, company, insight):
        mark_insight_read(insight)
        insight.refresh_from_db()
        assert insight.is_read is True


class TestGetForecasts:
    def test_returns_for_type(self, db, company):
        upsert_forecast(company, 'revenue', '2026-07', 1000)
        upsert_forecast(company, 'cash_flow', '2026-07', 500)
        result = list(get_forecasts(company, 'revenue'))
        types = [f.forecast_type for f in result]
        assert all(t == 'revenue' for t in types)

    def test_filters_by_periods(self, db, company):
        upsert_forecast(company, 'revenue', '2026-07', 1000)
        upsert_forecast(company, 'revenue', '2026-08', 2000)
        result = list(get_forecasts(company, 'revenue', periods=['2026-07']))
        assert len(result) == 1


class TestAnalyticsStats:
    def test_stats_keys(self, db, company, insight):
        stats = get_analytics_stats(company)
        assert 'total_forecasts' in stats
        assert 'active_insights' in stats
        assert 'unread_insights' in stats
        assert stats['active_insights'] >= 1
