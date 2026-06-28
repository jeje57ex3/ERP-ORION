"""
tests/test_accounting.py — Tests de robustesse du module Comptabilité

Règles testées :
  - Écriture équilibrée validable
  - Écriture déséquilibrée refusée
  - Écriture validée non modifiable
  - Extourne possible uniquement sur écriture validée
  - Paiement ne dépasse pas le solde dû
"""
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from apps.core.models import Company, CompanySettings


class TestJournalEntryRobustness(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            name='Accounting Test Co', slug='accounting-test-co',
            status='active', is_active=True,
        )
        CompanySettings.objects.create(company=self.company)
        self.user = User.objects.create_user('accountant', password='pass123')

    def _make_entry(self, balanced=True):
        from apps.accounting.models import Journal, Account, JournalEntry, JournalEntryLine
        from django.utils import timezone

        journal, _ = Journal.objects.get_or_create(
            company=self.company, code='VTE',
            defaults={'name': 'Ventes', 'journal_type': 'sale'},
        )
        account_client, _ = Account.objects.get_or_create(
            company=self.company, number='411000',
            defaults={'name': 'Clients', 'account_type': 'receivable'},
        )
        account_revenue, _ = Account.objects.get_or_create(
            company=self.company, number='706000',
            defaults={'name': 'Prestations', 'account_type': 'revenue'},
        )

        entry = JournalEntry(
            company=self.company, journal=journal,
            entry_date=timezone.now().date(), description='Test écriture',
            created_by=self.user, status='draft',
        )
        # Bypass clean() pour le brouillon initial
        JournalEntry.objects.bulk_create([]) if False else None
        entry.save()

        JournalEntryLine.objects.create(entry=entry, account=account_client, debit=1000, credit=0)
        if balanced:
            JournalEntryLine.objects.create(entry=entry, account=account_revenue, debit=0, credit=1000)
        else:
            JournalEntryLine.objects.create(entry=entry, account=account_revenue, debit=0, credit=500)
        return entry

    def test_balanced_entry_can_be_validated(self):
        entry = self._make_entry(balanced=True)
        entry.validate(self.user)
        entry.refresh_from_db()
        self.assertEqual(entry.status, 'validated')

    def test_unbalanced_entry_cannot_be_validated(self):
        entry = self._make_entry(balanced=False)
        with self.assertRaises(ValidationError):
            entry.validate(self.user)

    def test_validated_entry_cannot_be_modified(self):
        entry = self._make_entry(balanced=True)
        entry.validate(self.user)
        entry.refresh_from_db()
        entry.description = 'Modification interdite'
        with self.assertRaises(ValidationError):
            entry.save()

    def test_validated_entry_can_be_reversed(self):
        entry = self._make_entry(balanced=True)
        entry.validate(self.user)
        entry.refresh_from_db()
        rev = entry.reverse(self.user)
        self.assertIsNotNone(rev)
        entry.refresh_from_db()
        self.assertEqual(entry.status, 'reversed')

    def test_draft_entry_cannot_be_reversed(self):
        entry = self._make_entry(balanced=True)
        with self.assertRaises(ValidationError):
            entry.reverse(self.user)


class TestInvoicePaymentRobustness(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            name='Invoice Test Co', slug='invoice-test-co',
            status='active', is_active=True,
        )
        CompanySettings.objects.create(company=self.company)
        self.user = User.objects.create_user('salesperson', password='pass123')

    def _make_invoice(self):
        from apps.crm.models import Customer
        from apps.sales.models import Invoice
        from django.utils import timezone

        customer = Customer.objects.create(
            company=self.company, name='Client Test',
            customer_type='company', status='active',
        )
        return Invoice.objects.create(
            company=self.company, customer=customer,
            number='FAC-2026-0001',
            issue_date=timezone.now().date(),
            status='sent', total_ht=1000, total_tva=200,
            total_ttc=1200, amount_paid=0,
        )

    def test_payment_within_amount_due_accepted(self):
        invoice = self._make_invoice()
        invoice.record_payment(600)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, 'partial')
        self.assertEqual(float(invoice.amount_paid), 600.0)

    def test_payment_exceeding_amount_due_rejected(self):
        invoice = self._make_invoice()
        with self.assertRaises(ValidationError):
            invoice.record_payment(1500)

    def test_full_payment_marks_invoice_paid(self):
        invoice = self._make_invoice()
        invoice.record_payment(1200)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, 'paid')

    def test_paid_invoice_cannot_be_modified(self):
        invoice = self._make_invoice()
        invoice.record_payment(1200)
        invoice.refresh_from_db()
        invoice.subject = 'Modification interdite'
        with self.assertRaises(ValidationError):
            invoice.save()
