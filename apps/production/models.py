from django.db import models
from apps.core.models import Company
from apps.inventory.models import Product


class BillOfMaterials(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='boms')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='boms')
    name = models.CharField(max_length=200)
    version = models.CharField(max_length=10, default='1.0')
    quantity = models.DecimalField(max_digits=10, decimal_places=3, default=1)
    unit = models.CharField(max_length=20, default='unité')
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Nomenclature (BOM)'

    def __str__(self):
        return f'{self.product.name} - v{self.version}'


class BOMLine(models.Model):
    bom = models.ForeignKey(BillOfMaterials, on_delete=models.CASCADE, related_name='lines')
    component = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=10, decimal_places=3, default=1)
    unit = models.CharField(max_length=20, default='unité')
    notes = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f'{self.component.name} x{self.quantity}'


class WorkCenter(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='work_centers')
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, blank=True)
    capacity = models.PositiveIntegerField(default=1)
    cost_per_hour = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Centre de travail'

    def __str__(self):
        return self.name


class ManufacturingOrder(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Brouillon'), ('planned', 'Planifié'), ('in_progress', 'En cours'),
        ('completed', 'Terminé'), ('cancelled', 'Annulé'),
    ]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='manufacturing_orders')
    order_number = models.CharField(max_length=30, blank=True)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    bom = models.ForeignKey(BillOfMaterials, on_delete=models.SET_NULL, null=True, blank=True)
    quantity_planned = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    quantity_produced = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    planned_start = models.DateField(null=True, blank=True)
    planned_end = models.DateField(null=True, blank=True)
    actual_start = models.DateField(null=True, blank=True)
    actual_end = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Ordre de fabrication'
        verbose_name_plural = 'Ordres de fabrication'

    def __str__(self):
        return f'{self.order_number or "OF"} - {self.product.name}'
