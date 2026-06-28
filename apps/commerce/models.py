from django.db import models
from apps.core.models import Company
from apps.crm.models import Customer
from apps.inventory.models import Product


class Store(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='stores')
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)
    opening_hours = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Magasin'

    def __str__(self):
        return self.name


class POSSession(models.Model):
    STATUS_CHOICES = [('open', 'Ouverte'), ('closed', 'Fermée')]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='pos_sessions')
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='sessions')
    session_date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='open')
    opening_cash = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    closing_cash = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    total_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cashier = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Session caisse'

    def __str__(self):
        return f'Session {self.store.name} - {self.session_date}'


class POSTicket(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='pos_tickets')
    session = models.ForeignKey(POSSession, on_delete=models.CASCADE, related_name='tickets')
    ticket_number = models.CharField(max_length=30, blank=True)
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True)
    total_ht = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_tva = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_ttc = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_method = models.CharField(max_length=20, default='cash')
    is_refunded = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Ticket de caisse'

    def __str__(self):
        return f'{self.ticket_number or "TK"} - {self.total_ttc} EUR'


class LoyaltyCard(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='loyalty_cards')
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='loyalty_cards')
    card_number = models.CharField(max_length=20, unique=True)
    points = models.PositiveIntegerField(default=0)
    total_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Carte de fidélité'

    def __str__(self):
        return f'{self.card_number} - {self.customer.name}'
