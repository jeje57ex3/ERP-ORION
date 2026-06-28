"""
tests/test_smart_documents.py
Tests du module Documents Intelligents.
"""
import pytest
from django.utils import timezone
from datetime import timedelta
from apps.core.models import Company
from apps.smart_documents.models import SmartDocument, DocumentSignatureRequest
from apps.smart_documents.services import (
    create_document, create_new_version, request_signature,
    get_expiring_documents, search_documents, get_documents_for_object,
)


@pytest.fixture
def company(db):
    return Company.objects.create(name='Docs SA', slug='docs-sa', status='active', is_active=True)


@pytest.fixture
def user(db, django_user_model):
    return django_user_model.objects.create_user(username='doc_user', password='pass')


@pytest.fixture
def document(db, company, user):
    return SmartDocument.objects.create(
        company=company, title='Contrat test', document_type='contract',
        file='smart_documents/test.pdf', created_by=user,
    )


class TestCreateDocument:
    def test_creates_with_defaults(self, db, company, user):
        doc = create_document(company, 'Rapport Q1', 'smart_documents/r.pdf',
                              document_type='report', created_by=user)
        assert doc.pk is not None
        assert doc.version == 1
        assert doc.document_type == 'report'

    def test_brand_key_stored(self, db, company, user):
        doc = create_document(company, 'Catalogue', 'smart_documents/c.pdf',
                              brand_key='siecle', created_by=user)
        assert doc.brand_key == 'siecle'

    def test_related_object_stored(self, db, company, user):
        doc = create_document(company, 'Facture 42', 'smart_documents/f.pdf',
                              related_object_type='Invoice', related_object_id='42',
                              created_by=user)
        assert doc.related_object_type == 'Invoice'
        assert doc.related_object_id == '42'


class TestCreateNewVersion:
    def test_increments_version(self, db, document, user):
        v2 = create_new_version(document, 'smart_documents/v2.pdf', created_by=user)
        assert v2.version == 2
        assert v2.company == document.company

    def test_preserves_tags(self, db, document, user):
        document.tags = ['urgent', 'client']
        document.save()
        v2 = create_new_version(document, 'smart_documents/v2.pdf', created_by=user)
        assert v2.tags == ['urgent', 'client']


class TestRequestSignature:
    def test_creates_request(self, db, company, document):
        sig = request_signature(company, document, 'Jean Dupont', 'jean@example.com')
        assert sig.pk is not None
        assert sig.status == 'pending'
        assert len(sig.token) > 20

    def test_token_unique(self, db, company, document):
        s1 = request_signature(company, document, 'Alice', 'alice@example.com')
        s2 = request_signature(company, document, 'Bob', 'bob@example.com')
        assert s1.token != s2.token


class TestGetExpiringDocuments:
    def test_returns_expiring(self, db, company, document):
        document.expires_at = (timezone.now() + timedelta(days=15)).date()
        document.save()
        result = get_expiring_documents(company, days_ahead=30)
        assert document in result

    def test_excludes_far_future(self, db, company, document):
        document.expires_at = (timezone.now() + timedelta(days=90)).date()
        document.save()
        result = get_expiring_documents(company, days_ahead=30)
        assert document not in result

    def test_excludes_no_expiry(self, db, company, document):
        result = get_expiring_documents(company, days_ahead=30)
        assert document not in result


class TestSearchDocuments:
    def test_search_by_title(self, db, company, document):
        result = search_documents(company, q='Contrat')
        assert document in result

    def test_filter_by_type(self, db, company, document):
        result = search_documents(company, document_type='contract')
        assert document in result

    def test_filter_excludes_wrong_type(self, db, company, document):
        result = search_documents(company, document_type='invoice')
        assert document not in result


class TestGetDocumentsForObject:
    def test_returns_for_object(self, db, company, document):
        document.related_object_type = 'Invoice'
        document.related_object_id = '99'
        document.save()
        result = get_documents_for_object(company, 'Invoice', '99')
        assert document in result

    def test_excludes_different_object(self, db, company, document):
        document.related_object_type = 'Invoice'
        document.related_object_id = '99'
        document.save()
        result = get_documents_for_object(company, 'Invoice', '88')
        assert document not in result
