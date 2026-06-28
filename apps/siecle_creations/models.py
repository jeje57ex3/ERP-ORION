from django.db import models
from django.conf import settings
from apps.core.models import Company

CATEGORY_CHOICES = [
    ('montre', 'Montre'), ('bijou', 'Bijou'), ('accessoire', 'Accessoire'),
    ('coffret', 'Coffret cadeau'), ('piece_unique', 'Pièce unique'), ('edition_limitee', 'Édition limitée'),
]

STATUS_CHOICES = [
    ('draft', 'Brouillon'), ('published', 'Publié'),
    ('archived', 'Archivé'), ('sold_out', 'Épuisé'),
]

ORDER_STATUS_CHOICES = [
    ('pending', 'En attente'), ('confirmed', 'Confirmée'),
    ('in_production', 'En production'), ('shipped', 'Expédiée'),
    ('delivered', 'Livrée'), ('cancelled', 'Annulée'),
]


class Creation(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='siecle_creations')
    brand_key = models.CharField(max_length=40, default='siecle')
    reference = models.CharField(max_length=80, unique=True)
    title = models.CharField(max_length=180)
    category = models.CharField(max_length=40, choices=CATEGORY_CHOICES)
    description = models.TextField(blank=True)
    materials = models.TextField(blank=True)
    price_ht = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    price_ttc = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    stock_qty = models.PositiveIntegerField(default=0)
    images = models.JSONField(default=list, blank=True)
    tags = models.JSONField(default=list, blank=True)
    weight_grams = models.PositiveIntegerField(null=True, blank=True)
    dimensions = models.CharField(max_length=100, blank=True)
    is_limited_edition = models.BooleanField(default=False)
    limited_qty = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='draft')
    published_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_siecle_creations',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'siecle_creations'
        verbose_name = 'Création Siècle'
        verbose_name_plural = 'Créations Siècle'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'status', 'category']),
            models.Index(fields=['company', 'brand_key']),
        ]

    def __str__(self):
        return f'[{self.reference}] {self.title}'


class CreationOrder(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='siecle_orders')
    brand_key = models.CharField(max_length=40, default='siecle')
    creation = models.ForeignKey(Creation, on_delete=models.SET_NULL, null=True, related_name='orders')
    customer = models.ForeignKey(
        'crm.Customer', on_delete=models.SET_NULL, null=True,
        related_name='siecle_orders',
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=30, choices=ORDER_STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)
    shipping_address = models.TextField(blank=True)
    personalization = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_siecle_orders',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'siecle_creations'
        verbose_name = 'Commande Siècle'
        verbose_name_plural = 'Commandes Siècle'
        ordering = ['-created_at']

    def __str__(self):
        return f'Commande #{self.pk} — {self.creation}'
