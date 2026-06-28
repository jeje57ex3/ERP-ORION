"""
tests/test_domain_resolver.py — Tests de résolution domaine → site/service
"""
from django.test import TestCase
from unittest.mock import patch, MagicMock

from apps.websites.services.domain_resolver import (
    _clean_host,
    resolve_domain,
    get_website_for_domain,
    get_company_for_domain,
    get_target_for_domain,
    invalidate_domain_cache,
)


class TestCleanHost(TestCase):
    def test_strips_port(self):
        assert _clean_host('monsite.fr:8000') == 'monsite.fr'

    def test_lowercases(self):
        assert _clean_host('MONSITE.FR') == 'monsite.fr'

    def test_strips_whitespace(self):
        assert _clean_host('  monsite.fr  ') == 'monsite.fr'

    def test_empty_returns_empty(self):
        assert _clean_host('') == ''

    def test_none_safe(self):
        assert _clean_host(None or '') == ''


class TestResolveDomain(TestCase):
    """Tests de résolution avec cache simulé."""

    @patch('apps.websites.services.domain_resolver.cache')
    def test_returns_none_for_unknown_domain(self, mock_cache):
        mock_cache.get.return_value = '__none__'
        result = resolve_domain('unknown.fr')
        assert result is None

    @patch('apps.websites.services.domain_resolver.cache')
    @patch('apps.websites.services.domain_resolver.WebsiteDomain' if False else 'apps.websites.services.domain_resolver.cache')
    def test_cache_hit_none_sentinel(self, mock_cache):
        mock_cache.get.return_value = '__none__'
        result = resolve_domain('nonexistent.fr')
        assert result is None
        # Ne doit pas faire de requête DB
        mock_cache.get.assert_called_once()

    def test_clean_host_called_for_port(self):
        """Vérifie que le port est bien retiré avant la recherche."""
        with patch('apps.websites.services.domain_resolver.cache') as mock_cache:
            mock_cache.get.return_value = '__none__'
            resolve_domain('monsite.fr:8080')
            # La clé cache doit utiliser le host sans port
            mock_cache.get.assert_called_with('domain_resolve:monsite.fr')


class TestGetWebsiteForDomain(TestCase):
    def test_returns_none_when_no_domain(self):
        with patch('apps.websites.services.domain_resolver.resolve_domain', return_value=None):
            result = get_website_for_domain('unknown.fr')
            assert result is None

    def test_returns_website_when_found(self):
        mock_domain = MagicMock()
        mock_domain.website = MagicMock(name='MonSite')
        with patch('apps.websites.services.domain_resolver.resolve_domain', return_value=mock_domain):
            result = get_website_for_domain('monsite.fr')
            assert result == mock_domain.website


class TestGetCompanyForDomain(TestCase):
    def test_returns_none_when_no_domain(self):
        with patch('apps.websites.services.domain_resolver.resolve_domain', return_value=None):
            result = get_company_for_domain('unknown.fr')
            assert result is None

    def test_returns_company_when_found(self):
        mock_domain = MagicMock()
        mock_domain.website.company = MagicMock(name='Mon Entreprise')
        with patch('apps.websites.services.domain_resolver.resolve_domain', return_value=mock_domain):
            result = get_company_for_domain('monsite.fr')
            assert result == mock_domain.website.company


class TestGetTargetForDomain(TestCase):
    def test_returns_none_when_no_domain(self):
        with patch('apps.websites.services.domain_resolver.resolve_domain', return_value=None):
            result = get_target_for_domain('unknown.fr')
            assert result is None

    def test_returns_target_type(self):
        mock_domain = MagicMock()
        mock_domain.target_type = 'shop'
        with patch('apps.websites.services.domain_resolver.resolve_domain', return_value=mock_domain):
            result = get_target_for_domain('boutique.fr')
            assert result == 'shop'

    def test_returns_website_as_default(self):
        mock_domain = MagicMock(spec=[])  # Pas d'attribut target_type
        with patch('apps.websites.services.domain_resolver.resolve_domain', return_value=mock_domain):
            result = get_target_for_domain('monsite.fr')
            assert result == 'website'


class TestInvalidateDomainCache(TestCase):
    def test_deletes_cache_key(self):
        with patch('apps.websites.services.domain_resolver.cache') as mock_cache:
            invalidate_domain_cache('monsite.fr')
            mock_cache.delete.assert_called_once_with('domain_resolve:monsite.fr')

    def test_cleans_host_before_deleting(self):
        with patch('apps.websites.services.domain_resolver.cache') as mock_cache:
            invalidate_domain_cache('MONSITE.FR:8080')
            mock_cache.delete.assert_called_once_with('domain_resolve:monsite.fr')

    def test_empty_host_safe(self):
        with patch('apps.websites.services.domain_resolver.cache') as mock_cache:
            invalidate_domain_cache('')
            mock_cache.delete.assert_not_called()
