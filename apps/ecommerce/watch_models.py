"""
SIÈCLE — Modèles configurateur montre personnalisée.
"""
from django.db import models
from django.contrib.auth.models import User
from apps.core.models import Company


class WatchCustomizationOption(models.Model):
    CATEGORY_CHOICES = [
        ('case', 'Boîtier'), ('dial', 'Cadran'), ('hands', 'Aiguilles'),
        ('strap', 'Bracelet'), ('bezel', 'Lunette'), ('crown', 'Couronne'),
        ('glass', 'Verre'), ('engraving', 'Gravure'),
    ]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='watch_options')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120)
    color_hex = models.CharField(max_length=7, blank=True)
    material = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='watches/options/', blank=True, null=True)
    extra_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['category', 'order', 'name']
        unique_together = [('company', 'category', 'slug')]
        verbose_name = 'Option montre'
        verbose_name_plural = 'Options montre'

    def __str__(self):
        return f'{self.get_category_display()} — {self.name}'


class WatchPreset(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='watch_presets')
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120)
    description = models.TextField(blank=True)
    preview_image = models.ImageField(upload_to='watches/presets/', blank=True, null=True)
    configuration_json = models.JSONField(default=dict)
    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']
        unique_together = [('company', 'slug')]
        verbose_name = 'Preset montre'
        verbose_name_plural = 'Presets montre'

    def __str__(self):
        return self.name


class SavedWatchConfiguration(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='saved_watch_configs')
    brand_key = models.CharField(max_length=20, default='siecle')
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_watches', null=True, blank=True)
    session_key = models.CharField(max_length=100, blank=True)
    share_token = models.CharField(max_length=32, unique=True, blank=True)
    name = models.CharField(max_length=200, blank=True)
    configuration_json = models.JSONField(default=dict)
    preview_image = models.ImageField(upload_to='watches/configs/', blank=True, null=True)
    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    options_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    engraving_text = models.CharField(max_length=60, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Configuration montre sauvegardée'
        verbose_name_plural = 'Configurations montres sauvegardées'

    def __str__(self):
        return self.name or f'Config #{self.pk}'

    def save(self, *args, **kwargs):
        if not self.share_token:
            import secrets
            self.share_token = secrets.token_hex(16)
        super().save(*args, **kwargs)
