"""
tests/test_siecle_watch_customizer_checkout.py
Tests for WebOrderLineCustomization model and configurator model integrity.
"""
import json
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth.models import User
from apps.websites.models import (
    Website, WebsiteTheme, Company, StoreCategory, StoreProduct,
    StoreOrder, StoreOrderItem,
    ProductCustomizationOption, ProductCustomizationConfiguration,
    WebOrderLineCustomization,
)


def _setup_env(slug='siecle-checkout-cfg'):
    theme, _ = WebsiteTheme.objects.get_or_create(name='Checkout Theme', defaults={'primary_color': '#000'})
    company, _ = Company.objects.get_or_create(name='SIÈCLE Checkout', defaults={'email': 'checkout@test.fr'})
    site, _ = Website.objects.get_or_create(
        slug=slug,
        defaults={'name': 'SIÈCLE', 'theme': theme, 'company': company},
    )
    cat, _ = StoreCategory.objects.get_or_create(name='Montres', slug=f'montres-co-{slug}', website=site)
    product, _ = StoreProduct.objects.get_or_create(
        slug=f'watch-checkout-{slug}', website=site,
        defaults={
            'name': 'Montre Checkout Test',
            'category': cat,
            'price': Decimal('199.00'),
            'stock_quantity': 30,
            'status': 'published',
            'is_customizable': True,
        },
    )
    return site, company, product


class ProductCustomizationOptionModelTest(TestCase):
    """Tests for ProductCustomizationOption model."""

    def setUp(self):
        self.site, self.company, self.product = _setup_env()

    def test_create_option(self):
        opt = ProductCustomizationOption.objects.create(
            company=self.company, product=self.product,
            group='case', code='case_gold',
            label='Doré champagne', color='#C9A45C',
            material='metal', price_delta=Decimal('35.00'),
        )
        self.assertEqual(opt.group, 'case')
        self.assertEqual(float(opt.price_delta), 35.0)

    def test_option_str(self):
        opt = ProductCustomizationOption.objects.create(
            company=self.company, product=self.product,
            group='dial', code='dial_black',
            label='Noir profond', color='#000',
            material='matte', price_delta=Decimal('0.00'),
        )
        self.assertIn('Noir profond', str(opt))

    def test_option_unique_per_product_group_code(self):
        ProductCustomizationOption.objects.create(
            company=self.company, product=self.product,
            group='hands', code='hands_gold',
            label='Doré', color='#C9A45C',
            material='metal', price_delta=Decimal('10.00'),
        )
        from django.db import IntegrityError
        with self.assertRaises(Exception):
            ProductCustomizationOption.objects.create(
                company=self.company, product=self.product,
                group='hands', code='hands_gold',
                label='Doré Dupe', color='#C9A45C',
                material='metal', price_delta=Decimal('10.00'),
            )

    def test_inactive_option_flag(self):
        opt = ProductCustomizationOption.objects.create(
            company=self.company, product=self.product,
            group='strap', code='strap_test',
            label='Test', color='#000',
            material='leather', price_delta=Decimal('5.00'),
            is_active=False,
        )
        active_opts = ProductCustomizationOption.objects.filter(
            product=self.product, is_active=True
        )
        self.assertNotIn(opt, active_opts)

    def test_all_groups_accepted(self):
        for group in ('case', 'dial', 'hands', 'strap'):
            ProductCustomizationOption.objects.create(
                company=self.company, product=self.product,
                group=group, code=f'{group}_x',
                label='Test', color='#000',
                material='metal', price_delta=Decimal('0'),
            )
        count = ProductCustomizationOption.objects.filter(product=self.product).count()
        self.assertEqual(count, 4)


class ProductCustomizationConfigurationModelTest(TestCase):
    """Tests for ProductCustomizationConfiguration model."""

    def setUp(self):
        self.site, self.company, self.product = _setup_env('siecle-cfg-model')

    def test_create_configuration(self):
        config = ProductCustomizationConfiguration.objects.create(
            company=self.company,
            product=self.product,
            configuration_json={'case': 'case_gold', 'dial': 'dial_black', 'hands': 'hands_silver', 'strap': 'strap_black_leather'},
            configuration_labels_json={'case': 'Doré champagne', 'dial': 'Noir profond', 'hands': 'Argent', 'strap': 'Cuir noir'},
            base_price=Decimal('199.00'),
            options_price=Decimal('35.00'),
            final_price=Decimal('234.00'),
        )
        self.assertEqual(float(config.final_price), 234.0)
        self.assertIsNotNone(config.pk)

    def test_configuration_str(self):
        config = ProductCustomizationConfiguration.objects.create(
            company=self.company, product=self.product,
            configuration_json={}, configuration_labels_json={},
            base_price=Decimal('199'), options_price=Decimal('0'), final_price=Decimal('199'),
        )
        self.assertIn('199', str(config))

    def test_configuration_without_customer(self):
        config = ProductCustomizationConfiguration.objects.create(
            company=self.company, product=self.product,
            customer=None,
            configuration_json={}, configuration_labels_json={},
            base_price=Decimal('199'), options_price=Decimal('0'), final_price=Decimal('199'),
        )
        self.assertIsNone(config.customer)

    def test_configuration_with_customer(self):
        user = User.objects.create_user(
            username='cfg-user@test.fr', email='cfg-user@test.fr', password='pass123!'
        )
        config = ProductCustomizationConfiguration.objects.create(
            company=self.company, product=self.product,
            customer=user,
            configuration_json={}, configuration_labels_json={},
            base_price=Decimal('199'), options_price=Decimal('0'), final_price=Decimal('199'),
        )
        self.assertEqual(config.customer, user)


class WebOrderLineCustomizationModelTest(TestCase):
    """Tests for WebOrderLineCustomization — links order lines to watch config."""

    def setUp(self):
        self.site, self.company, self.product = _setup_env('siecle-order-cust')
        # Create a minimal order + order item
        self.order = StoreOrder.objects.create(
            website=self.site,
            company=self.company,
            order_number='TEST-WATCH-001',
            status='pending',
            payment_status='pending',
            customer_name='Test User',
            customer_email='test@test.fr',
            grand_total=Decimal('234.00'),
        )
        self.order_item = StoreOrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name=self.product.name,
            quantity=1,
            unit_price=Decimal('234.00'),
            total_price=Decimal('234.00'),
        )

    def test_create_line_customization(self):
        cust = WebOrderLineCustomization.objects.create(
            order_line=self.order_item,
            configuration_json={'case': 'case_gold', 'dial': 'dial_black', 'hands': 'hands_gold', 'strap': 'strap_black_leather'},
            configuration_labels_json={'case': 'Doré champagne', 'dial': 'Noir profond', 'hands': 'Doré', 'strap': 'Cuir noir'},
            base_price=Decimal('199.00'),
            options_price=Decimal('35.00'),
            final_price=Decimal('234.00'),
        )
        self.assertEqual(cust.order_line, self.order_item)
        self.assertEqual(float(cust.final_price), 234.0)

    def test_line_customization_str(self):
        cust = WebOrderLineCustomization.objects.create(
            order_line=self.order_item,
            configuration_json={},
            configuration_labels_json={},
            base_price=Decimal('199'), options_price=Decimal('0'), final_price=Decimal('199'),
        )
        self.assertIn(str(self.order_item.pk), str(cust))

    def test_config_summary_method(self):
        cust = WebOrderLineCustomization.objects.create(
            order_line=self.order_item,
            configuration_json={'case': 'case_gold'},
            configuration_labels_json={'case': 'Doré champagne', 'dial': 'Noir profond'},
            base_price=Decimal('199'), options_price=Decimal('35'), final_price=Decimal('234'),
        )
        summary = cust.config_summary()
        self.assertIn('Doré champagne', summary)
        self.assertIn('Noir profond', summary)

    def test_one_to_one_constraint(self):
        WebOrderLineCustomization.objects.create(
            order_line=self.order_item,
            configuration_json={}, configuration_labels_json={},
            base_price=Decimal('199'), options_price=Decimal('0'), final_price=Decimal('199'),
        )
        from django.db import IntegrityError
        with self.assertRaises(Exception):
            WebOrderLineCustomization.objects.create(
                order_line=self.order_item,
                configuration_json={}, configuration_labels_json={},
                base_price=Decimal('199'), options_price=Decimal('0'), final_price=Decimal('199'),
            )

    def test_access_via_order_item_reverse(self):
        WebOrderLineCustomization.objects.create(
            order_line=self.order_item,
            configuration_json={'strap': 'strap_steel'},
            configuration_labels_json={'strap': 'Maille acier'},
            base_price=Decimal('199'), options_price=Decimal('35'), final_price=Decimal('234'),
        )
        item = StoreOrderItem.objects.get(pk=self.order_item.pk)
        self.assertEqual(item.watch_customization.configuration_json['strap'], 'strap_steel')
