"""
tests/test_numbering.py — Tests du service de numérotation atomique
"""
from django.test import TestCase
from apps.core.models import Company, CompanySettings


class TestNextNumber(TestCase):
    """next_number() doit générer des numéros séquentiels sans doublons."""

    def setUp(self):
        self.company = Company.objects.create(
            name='Numbering Test Co',
            slug='numbering-test-co',
            status='active',
            is_active=True,
            invoice_prefix='FAC',
            quote_prefix='DEV',
            order_prefix='CMD',
        )
        CompanySettings.objects.create(
            company=self.company,
            next_invoice_number=1,
            next_quote_number=1,
            next_order_number=1,
        )

    def test_invoice_number_format(self):
        from apps.core.numbering import next_number
        from django.utils import timezone
        year = timezone.now().year
        num = next_number(self.company, 'invoice')
        self.assertTrue(num.startswith('FAC-'))
        self.assertIn(str(year), num)
        self.assertTrue(num.endswith('-0001'))

    def test_sequential_invoice_numbers(self):
        from apps.core.numbering import next_number
        n1 = next_number(self.company, 'invoice')
        n2 = next_number(self.company, 'invoice')
        self.assertNotEqual(n1, n2)
        # Les deux numéros doivent être consécutifs
        n1_seq = int(n1.split('-')[-1])
        n2_seq = int(n2.split('-')[-1])
        self.assertEqual(n2_seq, n1_seq + 1)

    def test_quote_number_independent_from_invoice(self):
        from apps.core.numbering import next_number
        inv = next_number(self.company, 'invoice')
        quote = next_number(self.company, 'quote')
        # Séquences indépendantes
        self.assertIn('FAC', inv)
        self.assertIn('DEV', quote)

    def test_invalid_sequence_type_raises(self):
        from apps.core.numbering import next_number
        with self.assertRaises(ValueError):
            next_number(self.company, 'invalid_type')
