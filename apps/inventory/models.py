"""
apps/inventory/models.py — Stocks, Produits, Entrepôts, Mouvements
"""
from django.db import models
from django.contrib.auth.models import User
from apps.core.models import Company


class ProductCategory(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='product_categories')
    name = models.CharField('Nom', max_length=100)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children')
    description = models.TextField('Description', blank=True)

    class Meta:
        verbose_name = 'Catégorie produit'
        verbose_name_plural = 'Catégories produits'

    def __str__(self):
        return self.name


class Product(models.Model):
    """Produit ou service."""
    TYPE_CHOICES = [
        ('product', 'Produit physique'),
        ('service', 'Service'),
        ('consumable', 'Consommable'),
        ('digital', 'Produit numérique'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='products')
    category = models.ForeignKey(ProductCategory, on_delete=models.SET_NULL, null=True, blank=True)
    product_type = models.CharField('Type', max_length=20, choices=TYPE_CHOICES, default='product')
    reference = models.CharField('Référence', max_length=100, blank=True)
    name = models.CharField('Nom', max_length=200)
    description = models.TextField('Description', blank=True)
    description_sale = models.TextField('Description vente', blank=True)
    image = models.ImageField('Image', upload_to='products/', blank=True, null=True)
    barcode = models.CharField('Code-barres', max_length=50, blank=True)

    # Prix
    sale_price = models.DecimalField('Prix vente HT', max_digits=12, decimal_places=4, default=0)
    purchase_price = models.DecimalField('Prix achat HT', max_digits=12, decimal_places=4, default=0)
    vat_rate = models.DecimalField('TVA %', max_digits=5, decimal_places=2, default=20)

    # Stock
    track_inventory = models.BooleanField('Gérer le stock', default=True)
    stock_quantity = models.DecimalField('Stock actuel', max_digits=12, decimal_places=3, default=0)
    min_stock_quantity = models.DecimalField('Stock minimum', max_digits=12, decimal_places=3, default=0)
    max_stock_quantity = models.DecimalField('Stock maximum', max_digits=12, decimal_places=3, null=True, blank=True)
    unit = models.CharField('Unité', max_length=20, default='unité')
    weight = models.DecimalField('Poids (kg)', max_digits=8, decimal_places=3, null=True, blank=True)

    # Fournisseur principal
    supplier_reference = models.CharField('Réf fournisseur', max_length=100, blank=True)
    lead_time_days = models.PositiveIntegerField('Délai approvisionnement (j)', default=0)

    is_active = models.BooleanField('Actif', default=True)
    is_published = models.BooleanField('Publié sur site web', default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Produit'
        verbose_name_plural = 'Produits'
        ordering = ['name']

    def __str__(self):
        return f'{self.reference} — {self.name}' if self.reference else self.name

    @property
    def needs_reorder(self):
        return self.track_inventory and self.stock_quantity <= self.min_stock_quantity


class Warehouse(models.Model):
    """Entrepôt / dépôt."""
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='warehouses')
    name = models.CharField('Nom', max_length=100)
    code = models.CharField('Code', max_length=10, blank=True)
    address = models.TextField('Adresse', blank=True)
    manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField('Actif', default=True)

    class Meta:
        verbose_name = 'Entrepôt'
        verbose_name_plural = 'Entrepôts'

    def __str__(self):
        return self.name


class StockLocation(models.Model):
    """Emplacement dans un entrepôt."""
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='locations')
    name = models.CharField('Nom', max_length=100)
    code = models.CharField('Code', max_length=20, blank=True)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField('Actif', default=True)

    class Meta:
        verbose_name = 'Emplacement'

    def __str__(self):
        return f'{self.warehouse.name} / {self.name}'


class StockMovement(models.Model):
    """Mouvement de stock (entrée, sortie, transfert)."""
    MOVEMENT_TYPES = [
        ('in', 'Entrée'),
        ('out', 'Sortie'),
        ('transfer', 'Transfert'),
        ('adjustment', 'Ajustement'),
        ('return', 'Retour'),
        ('loss', 'Perte'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='stock_movements')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='movements')
    movement_type = models.CharField('Type', max_length=20, choices=MOVEMENT_TYPES)
    quantity = models.DecimalField('Quantité', max_digits=12, decimal_places=3)
    unit_cost = models.DecimalField('Coût unitaire', max_digits=12, decimal_places=4, null=True, blank=True)
    from_location = models.ForeignKey(StockLocation, on_delete=models.SET_NULL, null=True, blank=True, related_name='outgoing')
    to_location = models.ForeignKey(StockLocation, on_delete=models.SET_NULL, null=True, blank=True, related_name='incoming')
    reference = models.CharField('Référence', max_length=100, blank=True)
    notes = models.TextField('Notes', blank=True)
    lot_number = models.CharField('N° lot', max_length=50, blank=True)
    serial_number = models.CharField('N° série', max_length=50, blank=True)
    movement_date = models.DateTimeField('Date', auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name = 'Mouvement stock'
        verbose_name_plural = 'Mouvements stock'
        ordering = ['-movement_date']

    def __str__(self):
        return f'{self.get_movement_type_display()} — {self.product.name} — {self.quantity}'
