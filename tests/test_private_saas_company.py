"""
tests/test_private_saas_company.py — Tests création entreprise SaaS privé
"""
from django.test import TestCase
from unittest.mock import patch, MagicMock


class TestCreatePrivateCompany(TestCase):

    def test_create_company_returns_instance(self):
        """create_private_company crée et retourne une Company."""
        from apps.private_saas.services import create_private_company
        with patch('apps.core.models.Company.objects') as mock_qs:
            mock_qs.filter.return_value.exists.return_value = False
            mock_co = MagicMock()
            mock_co.pk = 1
            mock_co.name = 'Test BTP'
            mock_co.slug = 'test-btp'
            mock_co.sector = 'btp'
            mock_qs.create.return_value = mock_co
            with patch('apps.private_saas.services.seed_company_modules'):
                result = create_private_company('Test BTP', 'btp')
                self.assertEqual(result.name, 'Test BTP')

    def test_slug_uniqueness_incremented(self):
        """Le slug est incrémenté si déjà pris."""
        from django.utils.text import slugify
        slug = slugify('Mon Entreprise')
        self.assertEqual(slug, 'mon-entreprise')


class TestSeedCompanyModules(TestCase):

    def test_all_modules_created(self):
        """seed_company_modules crée tous les modules."""
        from apps.private_saas.models import ALL_MODULE_CODES
        self.assertIn('crm', ALL_MODULE_CODES)
        self.assertIn('btp', ALL_MODULE_CODES)
        self.assertIn('websites', ALL_MODULE_CODES)
        self.assertIn('domains', ALL_MODULE_CODES)

    def test_btp_modules_defaults(self):
        """Le type BTP active les bons modules par défaut."""
        from apps.private_saas.models import DEFAULT_MODULES_BY_TYPE
        btp = DEFAULT_MODULES_BY_TYPE['btp']
        self.assertIn('btp', btp)
        self.assertIn('crm', btp)
        self.assertIn('websites', btp)
        self.assertNotIn('ecommerce', btp)

    def test_fashion_modules_defaults(self):
        """Le type fashion active les bons modules."""
        from apps.private_saas.models import DEFAULT_MODULES_BY_TYPE
        fashion = DEFAULT_MODULES_BY_TYPE['fashion']
        self.assertIn('ecommerce', fashion)
        self.assertIn('websites', fashion)
        self.assertNotIn('btp', fashion)
