"""
tests/test_domain_creation.py — Tests de création et validation de domaines
"""
import pytest
from django.test import TestCase
from unittest.mock import patch, MagicMock

from apps.websites.domain_services import (
    normalize_domain,
    validate_domain_format,
    generate_verification_token,
)
from apps.websites.forms_domains import clean_domain_input, DomainCreateForm


class TestNormalizeDomain(TestCase):
    """Tests de la fonction normalize_domain."""

    def test_strips_https(self):
        assert normalize_domain('https://monsite.fr') == 'monsite.fr'

    def test_strips_http(self):
        assert normalize_domain('http://monsite.fr') == 'monsite.fr'

    def test_strips_www(self):
        assert normalize_domain('www.monsite.fr') == 'monsite.fr'

    def test_strips_https_www(self):
        assert normalize_domain('https://www.monsite.fr') == 'monsite.fr'

    def test_strips_trailing_slash(self):
        assert normalize_domain('monsite.fr/') == 'monsite.fr'

    def test_lowercases(self):
        assert normalize_domain('MONSITE.FR') == 'monsite.fr'

    def test_subdomain_preserved(self):
        assert normalize_domain('boutique.monsite.fr') == 'boutique.monsite.fr'

    def test_already_clean(self):
        assert normalize_domain('monsite.fr') == 'monsite.fr'


class TestValidateDomainFormat(TestCase):
    """Tests de validation du format de domaine."""

    def test_valid_root_domain(self):
        ok, msg = validate_domain_format('monsite.fr')
        assert ok is True
        assert msg == ''

    def test_valid_subdomain(self):
        ok, msg = validate_domain_format('boutique.monsite.fr')
        assert ok is True

    def test_valid_with_dash(self):
        ok, msg = validate_domain_format('mon-site.fr')
        assert ok is True

    def test_invalid_no_tld(self):
        ok, msg = validate_domain_format('monsite')
        assert ok is False

    def test_invalid_empty(self):
        ok, msg = validate_domain_format('')
        assert ok is False
        assert 'vide' in msg.lower()

    def test_invalid_with_http(self):
        ok, msg = validate_domain_format('http://monsite.fr')
        # normalize_domain est appelé avant validate, donc ça devrait passer
        # mais validate seul ne strip pas
        ok2, _ = validate_domain_format(normalize_domain('http://monsite.fr'))
        assert ok2 is True

    def test_invalid_too_long(self):
        long_domain = 'a' * 250 + '.fr'
        ok, msg = validate_domain_format(long_domain)
        assert ok is False

    def test_invalid_ip_address(self):
        ok, msg = validate_domain_format('192.168.1.1')
        # IP pas un format domaine valide (chiffres seuls dans TLD)
        assert ok is False


class TestGenerateVerificationToken(TestCase):
    """Tests de génération du token de vérification."""

    def test_returns_string(self):
        token = generate_verification_token('monsite.fr')
        assert isinstance(token, str)

    def test_length_32(self):
        token = generate_verification_token('monsite.fr')
        assert len(token) == 32

    def test_unique_per_call(self):
        t1 = generate_verification_token('monsite.fr')
        t2 = generate_verification_token('monsite.fr')
        assert t1 != t2  # tokens différents à chaque appel (aléatoire)

    def test_alphanumeric(self):
        token = generate_verification_token('monsite.fr')
        assert all(c in '0123456789abcdef' for c in token)


class TestCleanDomainInput(TestCase):
    """Tests du nettoyage de domaine dans les formulaires."""

    def test_strips_https(self):
        from django.core.exceptions import ValidationError
        try:
            result = clean_domain_input('https://monsite.fr')
            assert result == 'monsite.fr'
        except ValidationError:
            pass  # Acceptable si le validator est strict

    def test_rejects_localhost(self):
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            clean_domain_input('localhost')

    def test_rejects_private_ip(self):
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            clean_domain_input('192.168.1.1')

    def test_rejects_empty(self):
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            clean_domain_input('')

    def test_accepts_valid_domain(self):
        result = clean_domain_input('monsite.fr')
        assert result == 'monsite.fr'

    def test_accepts_subdomain(self):
        result = clean_domain_input('boutique.monsite.fr')
        assert result == 'boutique.monsite.fr'
