import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone


class CustomDomain(models.Model):
    STATUS_CHOICES = [
        ('pending',     'En attente'),
        ('dns_pending', 'DNS en attente'),
        ('dns_valid',   'DNS valide'),
        ('ssl_pending', 'SSL en attente'),
        ('active',      'Actif'),
        ('error',       'Erreur'),
        ('disabled',    'Désactivé'),
    ]

    DOMAIN_TYPE_CHOICES = [
        ('root',      'Domaine racine'),
        ('www',       'Sous-domaine www'),
        ('subdomain', 'Sous-domaine'),
    ]

    TARGET_TYPE_CHOICES = [
        ('erp',     'Interface ERP'),
        ('shop',    'Boutique'),
        ('landing', 'Landing page'),
        ('api',     'API'),
    ]

    company = models.ForeignKey(
        'core.Company',
        on_delete=models.CASCADE,
        related_name='custom_domains',
    )

    domain = models.CharField(max_length=255, unique=True)

    brand_key = models.CharField(
        max_length=40,
        blank=True,
        help_text='Exemple : siecle, lunea.',
    )

    target_type = models.CharField(
        max_length=40,
        choices=TARGET_TYPE_CHOICES,
        default='shop',
    )

    domain_type = models.CharField(
        max_length=40,
        choices=DOMAIN_TYPE_CHOICES,
        default='root',
    )

    is_primary = models.BooleanField(default=False)
    redirect_to_primary = models.BooleanField(default=True)

    verification_token = models.CharField(max_length=120, blank=True)

    expected_cname = models.CharField(max_length=255, blank=True)
    expected_a_record = models.GenericIPAddressField(null=True, blank=True)
    expected_txt_name = models.CharField(max_length=255, blank=True)
    expected_txt_value = models.CharField(max_length=255, blank=True)

    dns_is_valid = models.BooleanField(default=False)
    ssl_is_valid = models.BooleanField(default=False)

    last_dns_check_at = models.DateTimeField(null=True, blank=True)
    last_ssl_check_at = models.DateTimeField(null=True, blank=True)

    last_error = models.TextField(blank=True)
    status = models.CharField(max_length=40, choices=STATUS_CHOICES, default='pending')

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'domain_manager'
        ordering = ['-is_primary', 'domain']
        verbose_name = 'Domaine personnalisé'
        verbose_name_plural = 'Domaines personnalisés'
        indexes = [
            models.Index(fields=['company', 'brand_key']),
            models.Index(fields=['status']),
            models.Index(fields=['is_primary']),
        ]

    def save(self, *args, **kwargs):
        if not self.verification_token:
            self.verification_token = secrets.token_urlsafe(32)

        if not self.expected_txt_value:
            self.expected_txt_value = self.verification_token

        if not self.expected_txt_name:
            prefix = getattr(settings, 'ORION_DOMAIN_VERIFY_TXT_PREFIX', 'orion-domain-verification')
            self.expected_txt_name = f'{prefix}.{self.domain}'

        if not self.expected_cname:
            self.expected_cname = getattr(settings, 'ORION_DOMAIN_TARGET_CNAME', '')

        if not self.expected_a_record:
            ip = getattr(settings, 'ORION_DOMAIN_TARGET_IP', None)
            if ip:
                self.expected_a_record = ip

        super().save(*args, **kwargs)

    def mark_dns_valid(self):
        self.dns_is_valid = True
        self.status = 'dns_valid'
        self.last_dns_check_at = timezone.now()
        self.last_error = ''
        self.save(update_fields=['dns_is_valid', 'status', 'last_dns_check_at', 'last_error', 'updated_at'])

    def mark_error(self, message):
        self.status = 'error'
        self.last_error = message
        self.save(update_fields=['status', 'last_error', 'updated_at'])

    def __str__(self):
        return self.domain
