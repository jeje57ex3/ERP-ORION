"""
apps/sales/models.py — Devis, Commandes, Factures, Avoirs
"""
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.core.models import Company
from apps.crm.models import Customer


class Quote(models.Model):
    """Devis commercial."""
    STATUS_CHOICES = [
        ('draft', 'Brouillon'),
        ('sent', 'Envoyé'),
        ('accepted', 'Accepté'),
        ('refused', 'Refusé'),
        ('expired', 'Expiré'),
        ('cancelled', 'Annulé'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='quotes')
    number = models.CharField('Numéro', max_length=30, blank=True)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='quotes')
    status = models.CharField('Statut', max_length=20, choices=STATUS_CHOICES, default='draft')
    issue_date = models.DateField('Date', default=timezone.now)
    validity_date = models.DateField('Validité', null=True, blank=True)
    delivery_date = models.DateField('Livraison prévue', null=True, blank=True)
    subject = models.CharField('Objet', max_length=300, blank=True)
    notes = models.TextField('Notes client', blank=True)
    internal_notes = models.TextField('Notes internes', blank=True)
    payment_terms = models.PositiveIntegerField('Délai paiement (j)', default=30)
    discount_rate = models.DecimalField('Remise globale %', max_digits=5, decimal_places=2, default=0)
    total_ht = models.DecimalField('Total HT', max_digits=12, decimal_places=2, default=0)
    total_tva = models.DecimalField('Total TVA', max_digits=12, decimal_places=2, default=0)
    total_ttc = models.DecimalField('Total TTC', max_digits=12, decimal_places=2, default=0)
    salesperson = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_quotes')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Devis'
        verbose_name_plural = 'Devis'
        ordering = ['-issue_date', '-created_at']

    def __str__(self):
        return f'{self.number or "DEV"} — {self.customer.name}'

    def calculate_totals(self):
        total_ht = sum(line.total_ht for line in self.lines.all())
        total_tva = sum(line.total_tva for line in self.lines.all())
        discount = total_ht * self.discount_rate / 100
        self.total_ht = total_ht - discount
        self.total_tva = total_tva
        self.total_ttc = self.total_ht + self.total_tva
        self.save(update_fields=['total_ht', 'total_tva', 'total_ttc'])


class QuoteLine(models.Model):
    """Ligne de devis."""
    LINE_TYPES = [('product', 'Produit'), ('service', 'Service'), ('subtotal', 'Sous-total'), ('text', 'Texte')]

    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, related_name='lines')
    line_type = models.CharField('Type', max_length=10, choices=LINE_TYPES, default='product')
    description = models.TextField('Description')
    reference = models.CharField('Référence', max_length=100, blank=True)
    quantity = models.DecimalField('Quantité', max_digits=10, decimal_places=3, default=1)
    unit = models.CharField('Unité', max_length=20, blank=True)
    unit_price = models.DecimalField('PU HT', max_digits=12, decimal_places=4, default=0)
    discount_rate = models.DecimalField('Remise %', max_digits=5, decimal_places=2, default=0)
    vat_rate = models.DecimalField('TVA %', max_digits=5, decimal_places=2, default=20)
    total_ht = models.DecimalField('Total HT', max_digits=12, decimal_places=2, default=0)
    total_tva = models.DecimalField('Total TVA', max_digits=12, decimal_places=2, default=0)
    order = models.PositiveIntegerField('Ordre', default=0)

    class Meta:
        ordering = ['order']

    def save(self, *args, **kwargs):
        pu_after_discount = self.unit_price * (1 - self.discount_rate / 100)
        self.total_ht = pu_after_discount * self.quantity
        self.total_tva = self.total_ht * self.vat_rate / 100
        super().save(*args, **kwargs)

    def __str__(self):
        return self.description[:50]


class SalesOrder(models.Model):
    """Commande client."""
    STATUS_CHOICES = [
        ('draft', 'Brouillon'),
        ('confirmed', 'Confirmée'),
        ('in_preparation', 'En préparation'),
        ('shipped', 'Expédiée'),
        ('delivered', 'Livrée'),
        ('invoiced', 'Facturée'),
        ('cancelled', 'Annulée'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='sales_orders')
    number = models.CharField('Numéro', max_length=30, blank=True)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='orders')
    quote = models.OneToOneField(Quote, on_delete=models.SET_NULL, null=True, blank=True, related_name='order')
    status = models.CharField('Statut', max_length=20, choices=STATUS_CHOICES, default='draft')
    order_date = models.DateField('Date commande', default=timezone.now)
    delivery_date = models.DateField('Date livraison', null=True, blank=True)
    delivery_address = models.TextField('Adresse livraison', blank=True)
    notes = models.TextField('Notes', blank=True)
    total_ht = models.DecimalField('Total HT', max_digits=12, decimal_places=2, default=0)
    total_ttc = models.DecimalField('Total TTC', max_digits=12, decimal_places=2, default=0)
    salesperson = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Commande client'
        verbose_name_plural = 'Commandes clients'
        ordering = ['-order_date']

    def __str__(self):
        return f'{self.number or "CMD"} — {self.customer.name}'


class Invoice(models.Model):
    """Facture client."""
    STATUS_CHOICES = [
        ('draft', 'Brouillon'),
        ('sent', 'Envoyée'),
        ('partial', 'Partiellement payée'),
        ('paid', 'Payée'),
        ('overdue', 'En retard'),
        ('cancelled', 'Annulée'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='invoices')
    number = models.CharField('Numéro', max_length=30, blank=True)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='invoices')
    order = models.ForeignKey(SalesOrder, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoices')
    quote = models.ForeignKey(Quote, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoices')
    status = models.CharField('Statut', max_length=20, choices=STATUS_CHOICES, default='draft')
    issue_date = models.DateField('Date émission', default=timezone.now)
    due_date = models.DateField('Date échéance', null=True, blank=True)
    subject = models.CharField('Objet', max_length=300, blank=True)
    notes = models.TextField('Notes', blank=True)
    payment_terms = models.PositiveIntegerField('Délai paiement (j)', default=30)
    total_ht = models.DecimalField('Total HT', max_digits=12, decimal_places=2, default=0)
    total_tva = models.DecimalField('Total TVA', max_digits=12, decimal_places=2, default=0)
    total_ttc = models.DecimalField('Total TTC', max_digits=12, decimal_places=2, default=0)
    amount_paid = models.DecimalField('Montant payé', max_digits=12, decimal_places=2, default=0)
    salesperson = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_invoices')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Facture'
        verbose_name_plural = 'Factures'
        ordering = ['-issue_date', '-created_at']

    def __str__(self):
        return f'{self.number or "FAC"} — {self.customer.name}'

    LOCKED_STATUSES = ('paid', 'cancelled')

    @property
    def amount_due(self):
        return self.total_ttc - self.amount_paid

    @property
    def is_overdue(self):
        return self.due_date and self.due_date < timezone.now().date() and self.status not in ['paid', 'cancelled']

    @property
    def is_locked(self):
        return self.status in self.LOCKED_STATUSES

    def clean(self):
        if self.pk:
            try:
                original = Invoice.objects.get(pk=self.pk)
                if original.status in self.LOCKED_STATUSES:
                    raise ValidationError(
                        f"Impossible de modifier une facture {original.get_status_display().lower()}. "
                        "Émettez un avoir pour corriger."
                    )
            except Invoice.DoesNotExist:
                pass

    def mark_sent(self):
        if self.status != 'draft':
            raise ValidationError("Seule une facture brouillon peut être envoyée.")
        self.status = 'sent'
        self.save(update_fields=['status', 'updated_at'])

    def record_payment(self, amount, user=None):
        """Enregistre un paiement partiel ou total. Lève une erreur si dépasse le solde."""
        from decimal import Decimal
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValidationError("Le montant du paiement doit être positif.")
        if amount > self.amount_due:
            raise ValidationError(
                f"Paiement ({amount} €) supérieur au solde dû ({self.amount_due} €)."
            )
        from django.db import transaction
        with transaction.atomic():
            Invoice.objects.filter(pk=self.pk).select_for_update()
            self.amount_paid += amount
            if self.amount_paid >= self.total_ttc:
                self.status = 'paid'
            elif self.amount_paid > 0:
                self.status = 'partial'
            self.save(update_fields=['amount_paid', 'status', 'updated_at'])
        self.refresh_from_db()
        return self


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='lines')
    description = models.TextField('Description')
    reference = models.CharField('Référence', max_length=100, blank=True)
    quantity = models.DecimalField('Quantité', max_digits=10, decimal_places=3, default=1)
    unit = models.CharField('Unité', max_length=20, blank=True)
    unit_price = models.DecimalField('PU HT', max_digits=12, decimal_places=4, default=0)
    discount_rate = models.DecimalField('Remise %', max_digits=5, decimal_places=2, default=0)
    vat_rate = models.DecimalField('TVA %', max_digits=5, decimal_places=2, default=20)
    total_ht = models.DecimalField('Total HT', max_digits=12, decimal_places=2, default=0)
    total_tva = models.DecimalField('Total TVA', max_digits=12, decimal_places=2, default=0)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def save(self, *args, **kwargs):
        pu = self.unit_price * (1 - self.discount_rate / 100)
        self.total_ht = pu * self.quantity
        self.total_tva = self.total_ht * self.vat_rate / 100
        super().save(*args, **kwargs)
