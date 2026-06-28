from django.utils import timezone
from .models import SmartDocument, DocumentSignatureRequest


def create_document(company, title, file, document_type='other', *, brand_key='',
                    related_object_type='', related_object_id='', tags=None,
                    expires_at=None, created_by=None):
    return SmartDocument.objects.create(
        company=company, brand_key=brand_key,
        title=title, file=file, document_type=document_type,
        related_object_type=related_object_type,
        related_object_id=str(related_object_id) if related_object_id else '',
        tags=tags or [], expires_at=expires_at, created_by=created_by,
    )


def create_new_version(document, new_file, created_by=None):
    document.file = new_file
    document.version += 1
    document.updated_at = timezone.now()
    document.save(update_fields=['file', 'version', 'updated_at'])
    return document


def request_signature(company, document, signer_name, signer_email):
    return DocumentSignatureRequest.objects.create(
        company=company, document=document,
        signer_name=signer_name, signer_email=signer_email,
    )


def get_expiring_documents(company, days_ahead=30):
    from datetime import timedelta
    cutoff = timezone.now().date() + timedelta(days=days_ahead)
    return SmartDocument.objects.filter(
        company=company, expires_at__lte=cutoff, expires_at__isnull=False
    ).order_by('expires_at')


def search_documents(company, q='', document_type='', tags=None, brand_key=''):
    qs = SmartDocument.objects.filter(company=company)
    if q:
        qs = qs.filter(title__icontains=q)
    if document_type:
        qs = qs.filter(document_type=document_type)
    if brand_key:
        qs = qs.filter(brand_key=brand_key)
    return qs.order_by('-created_at')


def get_documents_for_object(company, object_type, object_id):
    return SmartDocument.objects.filter(
        company=company, related_object_type=object_type,
        related_object_id=str(object_id),
    ).order_by('-created_at')
