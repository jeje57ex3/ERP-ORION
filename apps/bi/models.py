from django.db import models
from apps.core.models import Company


class Report(models.Model):
    REPORT_TYPES = [
        ('sales', 'CA ventes'), ('purchases', 'Achats'), ('inventory', 'Stocks'),
        ('hr', 'RH'), ('crm', 'CRM'), ('custom', 'Personnalisé'),
    ]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='reports')
    name = models.CharField(max_length=200)
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES, default='custom')
    description = models.TextField(blank=True)
    config = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Rapport'

    def __str__(self):
        return self.name
