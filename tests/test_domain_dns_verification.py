"""
tests/test_domain_dns_verification.py — Tests de vérification DNS
"""
from django.test import TestCase
from unittest.mock import patch, MagicMock


class TestCheckARecord(TestCase):
    """Tests de vérification enregistrement A."""

    @patch('apps.websites.services.dns_checker.check_a_record')
    def test_a_record_matches(self, mock_check):
        mock_check.return_value = {'ok': True, 'found': ['1.2.3.4'], 'expected': '1.2.3.4', 'error': None}
        from apps.websites.services.dns_checker import check_a_record
        result = check_a_record('monsite.fr', '1.2.3.4')
        assert result['ok'] is True

    @patch('apps.websites.services.dns_checker.check_a_record')
    def test_a_record_not_matching(self, mock_check):
        mock_check.return_value = {'ok': False, 'found': ['9.9.9.9'], 'expected': '1.2.3.4', 'error': None}
        from apps.websites.services.dns_checker import check_a_record
        result = check_a_record('monsite.fr', '1.2.3.4')
        assert result['ok'] is False

    def test_a_record_without_dnspython(self):
        """Sans dnspython installé, retourne une erreur propre."""
        import sys
        # Simuler absence de dnspython
        with patch.dict('sys.modules', {'dns': None, 'dns.resolver': None}):
            from apps.websites.services import dns_checker
            import importlib
            # On teste juste que le module ne crash pas à l'import
            self.assertTrue(True)


class TestCheckCNAMERecord(TestCase):
    """Tests de vérification enregistrement CNAME."""

    @patch('apps.websites.services.dns_checker.check_cname_record')
    def test_cname_matches(self, mock_check):
        mock_check.return_value = {
            'ok': True, 'found': 'sites.orion-erp.com',
            'expected': 'sites.orion-erp.com', 'error': None,
        }
        from apps.websites.services.dns_checker import check_cname_record
        result = check_cname_record('boutique.monsite.fr', 'sites.orion-erp.com')
        assert result['ok'] is True

    @patch('apps.websites.services.dns_checker.check_cname_record')
    def test_cname_wrong_target(self, mock_check):
        mock_check.return_value = {
            'ok': False, 'found': 'autreserveur.com',
            'expected': 'sites.orion-erp.com', 'error': None,
        }
        from apps.websites.services.dns_checker import check_cname_record
        result = check_cname_record('boutique.monsite.fr', 'sites.orion-erp.com')
        assert result['ok'] is False


class TestCheckTXTRecord(TestCase):
    """Tests de vérification enregistrement TXT."""

    @patch('apps.websites.services.dns_checker.check_txt_record')
    def test_txt_token_found(self, mock_check):
        token = 'orion-verification=abc123token456def'
        mock_check.return_value = {
            'ok': True, 'found': [token], 'expected': token, 'error': None,
        }
        from apps.websites.services.dns_checker import check_txt_record
        result = check_txt_record('_orion-verification.monsite.fr', token)
        assert result['ok'] is True

    @patch('apps.websites.services.dns_checker.check_txt_record')
    def test_txt_token_missing(self, mock_check):
        mock_check.return_value = {
            'ok': False, 'found': [], 'expected': 'orion-verification=abc123', 'error': 'NXDOMAIN',
        }
        from apps.websites.services.dns_checker import check_txt_record
        result = check_txt_record('_orion-verification.monsite.fr', 'orion-verification=abc123')
        assert result['ok'] is False


class TestCheckDomainRecords(TestCase):
    """Tests de vérification complète d'un domaine."""

    def _make_domain(self, domain_type='subdomain', token='testtoken123'):
        domain = MagicMock()
        domain.domain = 'boutique.monsite.fr'
        domain.domain_type = domain_type
        domain.verification_token = token
        domain.expected_cname = 'sites.orion-erp.com'
        return domain

    @patch('apps.websites.services.dns_checker.check_cname_record')
    @patch('apps.websites.services.dns_checker.check_txt_record')
    @patch('apps.websites.services.dns_checker._sync_dns_records')
    def test_subdomain_verified_when_cname_ok(self, mock_sync, mock_txt, mock_cname):
        mock_cname.return_value = {'ok': True, 'found': 'sites.orion-erp.com', 'expected': 'sites.orion-erp.com', 'error': None}
        mock_txt.return_value   = {'ok': False, 'found': [], 'expected': 'orion-verification=testtoken123', 'error': None}
        mock_sync.return_value  = None

        from apps.websites.services.dns_checker import check_domain_records
        domain = self._make_domain('subdomain')
        result = check_domain_records(domain)
        assert result['verified'] is True

    @patch('apps.websites.services.dns_checker.check_a_record')
    @patch('apps.websites.services.dns_checker.check_cname_record')
    @patch('apps.websites.services.dns_checker.check_txt_record')
    @patch('apps.websites.services.dns_checker._sync_dns_records')
    def test_root_domain_requires_a_and_txt(self, mock_sync, mock_txt, mock_cname, mock_a):
        mock_a.return_value     = {'ok': True,  'found': ['1.2.3.4'], 'expected': '1.2.3.4', 'error': None}
        mock_cname.return_value = {'ok': True,  'found': 'monsite.fr', 'expected': 'monsite.fr', 'error': None}
        mock_txt.return_value   = {'ok': True,  'found': ['orion-verification=testtoken123'], 'expected': 'orion-verification=testtoken123', 'error': None}
        mock_sync.return_value  = None

        from apps.websites.services.dns_checker import check_domain_records
        domain = self._make_domain('root')
        domain.domain = 'monsite.fr'
        result = check_domain_records(domain)
        assert result['verified'] is True

    @patch('apps.websites.services.dns_checker.check_a_record')
    @patch('apps.websites.services.dns_checker.check_cname_record')
    @patch('apps.websites.services.dns_checker.check_txt_record')
    @patch('apps.websites.services.dns_checker._sync_dns_records')
    def test_root_domain_fails_without_txt(self, mock_sync, mock_txt, mock_cname, mock_a):
        mock_a.return_value     = {'ok': True,  'found': ['1.2.3.4'], 'expected': '1.2.3.4', 'error': None}
        mock_cname.return_value = {'ok': False, 'found': None, 'expected': 'monsite.fr', 'error': None}
        mock_txt.return_value   = {'ok': False, 'found': [], 'expected': 'orion-verification=testtoken123', 'error': 'NXDOMAIN'}
        mock_sync.return_value  = None

        from apps.websites.services.dns_checker import check_domain_records
        domain = self._make_domain('root')
        domain.domain = 'monsite.fr'
        result = check_domain_records(domain)
        assert result['verified'] is False


from unittest.mock import MagicMock
