from django.db import models
from django.contrib.auth.models import User
from apps.core.models import Company


class DocumentCategory(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Catégorie document'

    def __str__(self):
        return self.name


class Document(models.Model):
    DOCUMENT_TYPES = [
        ('contract', 'Contrat'), ('invoice', 'Facture'), ('quote', 'Devis'),
        ('plan', 'Plan'), ('report', 'Rapport'), ('certificate', 'Certificat'),
        ('photo', 'Photo'), ('other', 'Autre'),
    ]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='documents')
    category = models.ForeignKey(DocumentCategory, on_delete=models.SET_NULL, null=True, blank=True)
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES, default='other')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to='documents/%Y/%m/', blank=True, null=True)
    file_size = models.PositiveIntegerField(default=0)
    version = models.CharField(max_length=20, default='1.0')
    tags = models.CharField(max_length=300, blank=True)
    is_confidential = models.BooleanField(default=False)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Document'
        ordering = ['-created_at']

    def __str__(self):
        return self.title
