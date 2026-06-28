"""
tests/test_customer_360.py
Tests du module Customer 360.
"""
import pytest
from decimal import Decimal
from django.contrib.auth.models import User
from apps.core.models import Company
from apps.crm.models import Customer
from apps.customer_360.models import CustomerScore, CustomerTimelineEvent
from apps.customer_360.services import (
    add_timeline_event, upsert_score, get_customer_360_data,
)


@pytest.fixture
def company(db):
    return Company.objects.create(name='360 SA', slug='c360-sa', status='active', is_active=True)


@pytest.fixture
def customer(db, company):
    return Customer.objects.create(
        company=company, name='Test Client',
        email='client@test.com', customer_type='individual',
    )


class TestAddTimelineEvent:
    def test_creates_event(self, db, company, customer):
        event = add_timeline_event(company, customer, 'order', 'Nouvelle commande')
        assert event.pk is not None
        assert event.event_type == 'order'

    def test_filters_by_company(self, db, company, customer):
        add_timeline_event(company, customer, 'note', 'Note')
        other = Company.objects.create(name='Other', slug='c360-other', status='active', is_active=True)
        events = CustomerTimelineEvent.objects.filter(company=other)
        assert events.count() == 0

    def test_brand_key_stored(self, db, company, customer):
        event = add_timeline_event(company, customer, 'order', 'SIÈCLE order', brand_key='siecle')
        assert event.brand_key == 'siecle'


class TestUpsertScore:
    def test_creates_score(self, db, company, customer):
        score = upsert_score(company, customer, 'loyalty', Decimal('75'))
        assert score.pk is not None
        assert score.score == Decimal('75')

    def test_updates_existing_score(self, db, company, customer):
        upsert_score(company, customer, 'loyalty', Decimal('50'))
        upsert_score(company, customer, 'loyalty', Decimal('80'))
        count = CustomerScore.objects.filter(company=company, customer=customer, score_type='loyalty').count()
        assert count == 1
        assert CustomerScore.objects.get(company=company, customer=customer, score_type='loyalty').score == Decimal('80')

    def test_brand_key_creates_separate_score(self, db, company, customer):
        upsert_score(company, customer, 'loyalty', Decimal('60'), brand_key='siecle')
        upsert_score(company, customer, 'loyalty', Decimal('70'), brand_key='lunea')
        count = CustomerScore.objects.filter(company=company, customer=customer, score_type='loyalty').count()
        assert count == 2


class TestGet360Data:
    def test_returns_customer(self, db, company, customer):
        data = get_customer_360_data(company, customer)
        assert data['customer'] == customer

    def test_returns_scores_and_timeline(self, db, company, customer):
        add_timeline_event(company, customer, 'note', 'Test note')
        upsert_score(company, customer, 'overall', Decimal('65'))
        data = get_customer_360_data(company, customer)
        assert len(data['timeline']) >= 1
        assert len(data['scores']) >= 1

    def test_company_isolation(self, db, company, customer):
        other = Company.objects.create(name='Other', slug='c360-o2', status='active', is_active=True)
        other_cust = Customer.objects.create(company=other, name='Other client', customer_type='individual')
        add_timeline_event(other, other_cust, 'note', 'Other note')
        data = get_customer_360_data(company, customer)
        assert all(e.company_id == company.pk for e in data['timeline'])
