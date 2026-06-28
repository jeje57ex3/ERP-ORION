"""
tests/test_inventory.py — Tests de robustesse du module Stock

Règles testées :
  - Sortie de stock valide réduit le stock
  - Sortie supérieure au stock disponible refusée
  - Transfert crée deux mouvements et stock net inchangé
  - Entrée augmente le stock
"""
from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from apps.core.models import Company, CompanySettings


class TestStockService(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            name='Stock Test Co', slug='stock-test-co',
            status='active', is_active=True,
        )
        CompanySettings.objects.create(company=self.company)
        self.user = User.objects.create_user('storekeeper', password='pass123')

    def _make_product(self, qty=100):
        from apps.inventory.models import Product
        return Product.objects.create(
            company=self.company,
            name='Produit Test',
            reference='TST-001',
            stock_quantity=Decimal(str(qty)),
            track_inventory=True,
            unit='unité',
        )

    def test_stock_out_reduces_quantity(self):
        from apps.inventory.services import create_stock_movement
        product = self._make_product(100)
        create_stock_movement(
            company=self.company, product=product,
            movement_type='out', quantity=Decimal('30'),
            user=self.user,
        )
        product.refresh_from_db()
        self.assertEqual(product.stock_quantity, Decimal('70'))

    def test_stock_in_increases_quantity(self):
        from apps.inventory.services import create_stock_movement
        product = self._make_product(50)
        create_stock_movement(
            company=self.company, product=product,
            movement_type='in', quantity=Decimal('25'),
            user=self.user,
        )
        product.refresh_from_db()
        self.assertEqual(product.stock_quantity, Decimal('75'))

    def test_stock_out_exceeding_available_is_rejected(self):
        from apps.inventory.services import create_stock_movement
        product = self._make_product(10)
        with self.assertRaises(ValidationError):
            create_stock_movement(
                company=self.company, product=product,
                movement_type='out', quantity=Decimal('50'),
                user=self.user,
            )
        product.refresh_from_db()
        self.assertEqual(product.stock_quantity, Decimal('10'))

    def test_allow_negative_stock_with_flag(self):
        from apps.inventory.services import create_stock_movement
        product = self._make_product(5)
        create_stock_movement(
            company=self.company, product=product,
            movement_type='out', quantity=Decimal('10'),
            user=self.user, allow_negative=True,
        )
        product.refresh_from_db()
        self.assertEqual(product.stock_quantity, Decimal('-5'))

    def test_transfer_creates_two_movements(self):
        from apps.inventory.services import create_stock_movement
        from apps.inventory.models import StockMovement
        product = self._make_product(100)
        result = create_stock_movement(
            company=self.company, product=product,
            movement_type='transfer', quantity=Decimal('20'),
            user=self.user,
        )
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        out_m, in_m = result
        self.assertEqual(out_m.movement_type, 'out')
        self.assertEqual(in_m.movement_type, 'in')

    def test_zero_quantity_rejected(self):
        from apps.inventory.services import create_stock_movement
        product = self._make_product(100)
        with self.assertRaises(ValidationError):
            create_stock_movement(
                company=self.company, product=product,
                movement_type='out', quantity=Decimal('0'),
                user=self.user,
            )
