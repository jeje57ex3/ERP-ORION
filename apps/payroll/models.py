from django.db import models
from apps.core.models import Company
from apps.hr.models import Employee


class PayrollPeriod(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='payroll_periods')
    year = models.PositiveIntegerField()
    month = models.PositiveIntegerField()
    is_closed = models.BooleanField(default=False)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Période de paie'
        unique_together = ['company', 'year', 'month']

    def __str__(self):
        return f'{self.month:02d}/{self.year}'


class Payslip(models.Model):
    STATUS_CHOICES = [('draft', 'Brouillon'), ('validated', 'Validé'), ('paid', 'Payé')]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='payslips')
    period = models.ForeignKey(PayrollPeriod, on_delete=models.CASCADE, related_name='payslips')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='payslips')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    gross_salary = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    employer_contributions = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    employee_contributions = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_salary = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_taxable = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    paid_at = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Bulletin de paie'
        unique_together = ['period', 'employee']

    def __str__(self):
        return f'Bulletin {self.employee} - {self.period}'
