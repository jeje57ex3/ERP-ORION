from django.contrib import admin
from .models import SmartDocument, DocumentSignatureRequest


class SignatureRequestInline(admin.TabularInline):
    model = DocumentSignatureRequest
    extra = 0
    readonly_fields = ['status', 'signed_at', 'created_at', 'token']
    fields = ['signer_name', 'signer_email', 'status', 'signed_at']


@admin.register(SmartDocument)
class SmartDocumentAdmin(admin.ModelAdmin):
    list_display = ['title', 'document_type', 'version', 'brand_key', 'is_signed', 'expires_at', 'company', 'created_by', 'created_at']
    list_filter = ['document_type', 'brand_key', 'is_signed', 'company']
    search_fields = ['title', 'related_object_id']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [SignatureRequestInline]


@admin.register(DocumentSignatureRequest)
class DocumentSignatureRequestAdmin(admin.ModelAdmin):
    list_display = ['document', 'signer_name', 'signer_email', 'status', 'signed_at', 'company']
    list_filter = ['status', 'company']
    readonly_fields = ['token', 'signed_at', 'created_at']
