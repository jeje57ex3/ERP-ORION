from django.db import models


class WaitlistSubscriber(models.Model):
    BRAND_CHOICES = [
        ('siecle', 'SIÈCLE'),
        ('lunea', 'LUNEA'),
    ]

    brand_key = models.CharField(max_length=40, choices=BRAND_CHOICES)
    feature_key = models.CharField(max_length=80, default='general')
    email = models.EmailField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'launch'
        unique_together = [('brand_key', 'feature_key', 'email')]
        ordering = ['-created_at']
        verbose_name = 'Abonné liste d\'attente'
        verbose_name_plural = 'Abonnés liste d\'attente'

    def __str__(self):
        return f'{self.email} — {self.brand_key} / {self.feature_key}'


class ContactMessage(models.Model):
    brand_key = models.CharField(max_length=40)
    name = models.CharField(max_length=180)
    email = models.EmailField()
    subject = models.CharField(max_length=180)
    message = models.TextField()
    status = models.CharField(max_length=40, default='new')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    honeypot = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'launch'
        ordering = ['-created_at']
        verbose_name = 'Message contact'
        verbose_name_plural = 'Messages contact'

    def __str__(self):
        return f'[{self.brand_key}] {self.name} — {self.subject}'
