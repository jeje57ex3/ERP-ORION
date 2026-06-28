"""
apps/websites/security.py — Sécurité des formulaires publics de sites web
"""
import hashlib
import re
import logging
from django.core.cache import cache
from django.utils.html import strip_tags
import bleach

logger = logging.getLogger('orion')

ALLOWED_HTML_TAGS = ['p', 'b', 'i', 'u', 'em', 'strong', 'a', 'ul', 'ol', 'li', 'br']
ALLOWED_HTML_ATTRS = {'a': ['href', 'title']}

RATE_LIMIT_PERIOD = 3600  # 1 heure
RATE_LIMIT_MAX = 10       # max 10 soumissions par heure par IP


def check_honeypot(post_data: dict, field_name: str = 'website_url_field') -> bool:
    """Retourne True si le honeypot est vide (formulaire valide), False si spam."""
    return not bool(post_data.get(field_name, ''))


def get_ip_hash(ip_address: str) -> str:
    """Retourne un hash de l'IP (pas de stockage direct de l'IP)."""
    if not ip_address:
        return ''
    return hashlib.sha256(ip_address.encode()).hexdigest()[:16]


def rate_limit_submission(ip_address: str, website_id: int) -> tuple[bool, int]:
    """
    Vérifie la limite de soumissions par IP par heure.
    Retourne (allowed, remaining_submissions).
    """
    ip_hash = get_ip_hash(ip_address)
    key = f'ws_form_rate_{website_id}_{ip_hash}'
    count = cache.get(key, 0)
    if count >= RATE_LIMIT_MAX:
        return False, 0
    cache.set(key, count + 1, RATE_LIMIT_PERIOD)
    return True, RATE_LIMIT_MAX - count - 1


def sanitize_html_content(content: str) -> str:
    """Nettoie le contenu HTML pour éviter les injections XSS."""
    try:
        return bleach.clean(content, tags=ALLOWED_HTML_TAGS, attributes=ALLOWED_HTML_ATTRS)
    except ImportError:
        return strip_tags(content)


def validate_public_upload(file) -> tuple[bool, str]:
    """Valide un fichier uploadé depuis un formulaire public."""
    ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.pdf', '.doc', '.docx'}
    MAX_SIZE = 10 * 1024 * 1024  # 10 Mo

    if not file:
        return True, ''

    import os
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, f'Extension {ext} non autorisée.'
    if file.size > MAX_SIZE:
        return False, f'Fichier trop lourd (max 10 Mo).'
    return True, ''


def log_suspicious_submission(ip_address: str, website_id: int, reason: str) -> None:
    """Enregistre une soumission suspecte dans les logs."""
    logger.warning(
        f'[WEBSITES] Soumission suspecte — website={website_id} ip={ip_address} raison={reason}'
    )
