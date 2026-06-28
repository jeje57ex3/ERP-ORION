from django.db import models
from apps.core.models import Company


FORECAST_TYPE_CHOICES = [
    ('revenue', 'Chiffre d\'affaires'), ('cash_flow', 'Trésorerie'),
    ('sales_volume', 'Volume ventes'), ('churn_risk', 'Risque churn'),
    ('inventory_demand', 'Demande stock'), ('project_delay', 'Retard projet'),
    ('employee_load', 'Charge salarié'), ('custom', 'Personnalisé'),
]

INSIGHT_TYPE_CHOICES = [
    ('opportunity', 'Opportunité'), ('risk', 'Risque'),
    ('trend', 'Tendance'), ('anomaly', 'Anomalie'), ('recommendation', 'Recommandation'),
]


class AnalyticsForecast(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='analytics_forecasts')
    brand_key = models.CharField(max_length=40, blank=True)
    forecast_type = models.CharField(max_length=80, choices=FORECAST_TYPE_CHOICES)
    period = models.CharField(max_length=20)
    value = models.DecimalField(max_digits=18, decimal_places=4)
    lower_bound = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    upper_bound = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    confidence = models.FloatField(default=0.8)
    model_version = models.CharField(max_length=40, default='v1')
    raw_data = models.JSONField(default=dict, blank=True)
    computed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'predictive_analytics'
        verbose_name = 'Prévision analytique'
        verbose_name_plural = 'Prévisions analytiques'
        ordering = ['-computed_at']
        unique_together = [('company', 'forecast_type', 'period', 'brand_key')]
        indexes = [models.Index(fields=['company', 'forecast_type', 'period'])]

    def __str__(self):
        return f'{self.get_forecast_type_display()} — {self.period}'


class AnalyticsInsight(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='analytics_insights')
    brand_key = models.CharField(max_length=40, blank=True)
    insight_type = models.CharField(max_length=40, choices=INSIGHT_TYPE_CHOICES)
    title = models.CharField(max_length=180)
    message = models.TextField()
    source_module = models.CharField(max_length=80, blank=True)
    data = models.JSONField(default=dict, blank=True)
    score = models.FloatField(default=0.0)
    is_read = models.BooleanField(default=False)
    is_dismissed = models.BooleanField(default=False)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'predictive_analytics'
        verbose_name = 'Insight analytique'
        verbose_name_plural = 'Insights analytiques'
        ordering = ['-score', '-created_at']
        indexes = [models.Index(fields=['company', 'insight_type', 'is_dismissed'])]

    def __str__(self):
        return f'[{self.get_insight_type_display()}] {self.title}'
