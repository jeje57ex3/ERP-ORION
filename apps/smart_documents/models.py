from django.db import models
from django.conf import settings
from apps.core.models import Company


class SmartDocument(models.Model):
    DOCUMENT_TYPE_CHOICES = [
        ('contract', 'Contrat'), ('invoice', 'Facture'), ('quote', 'Devis'),
        ('report', 'Rapport'), ('id_card', 'Pièce identité'), ('certificate', 'Certificat'),
        ('plan', 'Plan'), ('photo', 'Photo'), ('other', 'Autre'),
    ]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='smart_documents')
    brand_key = models.CharField(max_length=40, blank=True)
    title = models.CharField(max_length=180)
    file = models.FileField(upload_to='smart_documents/')
    document_type = models.CharField(max_length=80, choices=DOCUMENT_TYPE_CHOICES, default='other')
    related_object_type = models.CharField(max_length=80, blank=True)
    related_object_id = models.CharField(max_length=80, blank=True)
    tags = models.JSONField(default=list, blank=True)
    version = models.PositiveIntegerField(default=1)
    expires_at = models.DateField(null=True, blank=True)
    is_signed = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='uploaded_smart_documents',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'smart_documents'
        verbose_name = 'Document intelligent'
        verbose_name_plural = 'Documents intelligents'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'document_type']),
            models.Index(fields=['company', 'related_object_type', 'related_object_id']),
        ]

    def __str__(self):
        return f'{self.title} (v{self.version})'


class DocumentSignatureRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'En attente'), ('sent', 'Envoyée'),
        ('signed', 'Signée'), ('declined', 'Refusée'), ('expired', 'Expirée'),
    ]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='signature_requests')
    document = models.ForeignKey(SmartDocument, on_delete=models.CASCADE, related_name='signature_requests')
    signer_name = models.CharField(max_length=180)
    signer_email = models.EmailField()
    status = models.CharField(max_length=40, choices=STATUS_CHOICES, default='pending')
    token = models.CharField(max_length=120, unique=True, blank=True)
    signed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'smart_documents'
        verbose_name = 'Demande de signature'
        verbose_name_plural = 'Demandes de signature'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.document.title} → {self.signer_name}'

    def save(self, *args, **kwargs):
        if not self.token:
            import secrets
            self.token = secrets.token_urlsafe(64)
        super().save(*args, **kwargs)
