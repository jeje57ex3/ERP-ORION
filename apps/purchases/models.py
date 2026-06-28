from django.db import models
from django.contrib.auth.models import User
from apps.core.models import Company


class Supplier(models.Model):
    TYPE_CHOICES = [('individual', 'Particulier'), ('company', 'Société')]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='suppliers')
    supplier_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='company')
    code = models.CharField(max_length=20, blank=True)
    name = models.CharField('Nom / Raison sociale', max_length=200)
    contact_name = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    zip_code = models.CharField(max_length=10, blank=True)
    country = models.CharField(max_length=100, default='France')
    siret = models.CharField(max_length=14, blank=True)
    vat_number = models.CharField(max_length=20, blank=True)
    payment_terms = models.PositiveIntegerField(default=30)
    lead_time_days = models.PositiveIntegerField(default=7)
    discount_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Fournisseur'
        verbose_name_plural = 'Fournisseurs'
        ordering = ['name']

    def __str__(self):
        return self.name


class PurchaseOrder(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Brouillon'), ('sent', 'Envoyé'), ('confirmed', 'Confirmé'),
        ('received', 'Reçu'), ('partial', 'Partiellement reçu'), ('cancelled', 'Annulé'),
    ]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='purchase_orders')
    number = models.CharField(max_length=30, blank=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='orders')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    order_date = models.DateField(auto_now_add=True)
    expected_delivery = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    total_ht = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_ttc = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Commande achat'
        verbose_name_plural = 'Commandes achat'
        ordering = ['-order_date']

    def __str__(self):
        return f'{self.number or "PO"} - {self.supplier.name}'


class SupplierInvoice(models.Model):
    STATUS_CHOICES = [
        ('pending', 'En attente'), ('approved', 'Approuvée'),
        ('paid', 'Payée'), ('overdue', 'En retard'), ('disputed', 'Contestée'),
    ]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='supplier_invoices')
    number = models.CharField(max_length=30, blank=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='invoices')
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.SET_NULL, null=True, blank=True)
    supplier_ref = models.CharField('Référence fournisseur', max_length=50, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    issue_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    total_ht = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_tva = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_ttc = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Facture fournisseur'
        verbose_name_plural = 'Factures fournisseurs'

    def __str__(self):
        return f'{self.number or "FA"} - {self.supplier.name}'
