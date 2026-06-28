"""
apps/core/utils.py — Utilitaires généraux Orion ERP

Fonctions pures, sans dépendances circulaires.
Peuvent être importées depuis n'importe quelle app.

Exemples :
    from apps.core.utils import format_currency, generate_reference, is_valid_siret
"""
import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

from django.utils.text import slugify as django_slugify

from apps.core.constants import (
    CURRENCY_EUR,
    CURRENCY_SYMBOLS,
    DATE_FORMAT_FR,
    DATETIME_FORMAT_FR,
)


# ─── Formatage monétaire ──────────────────────────────────────────────────────

def format_currency(amount, currency: str = CURRENCY_EUR) -> str:
    """
    Formate un montant en chaîne localisée française.

    Exemples :
        format_currency(1234.5)        → "1 234,50 €"
        format_currency(99.9, 'USD')   → "99,90 $"
        format_currency(None)          → "0,00 €"
    """
    if amount is None:
        amount = 0
    # Arrondi à 2 décimales
    value = Decimal(str(amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    # Partie entière avec espace comme séparateur de milliers
    int_part = int(value)
    dec_part = abs(value - int_part)
    int_str = f'{abs(int_part):,}'.replace(',', ' ')  # espace fine
    dec_str = f'{dec_part:.2f}'[2:]  # 2 chiffres après la virgule
    sign = '-' if value < 0 else ''
    symbol = CURRENCY_SYMBOLS.get(currency, currency)
    formatted = f'{sign}{int_str},{dec_str} {symbol}'
    return formatted


# ─── Formatage de dates ───────────────────────────────────────────────────────

def format_date_fr(d) -> str:
    """
    Formate une date en format français "JJ/MM/AAAA".
    Retourne '' si la valeur est None.

        format_date_fr(date(2026, 6, 12)) → "12/06/2026"
    """
    if d is None:
        return ''
    if isinstance(d, datetime):
        d = d.date()
    return d.strftime(DATE_FORMAT_FR)


def format_datetime_fr(dt) -> str:
    """
    Formate un datetime en format français "JJ/MM/AAAA HH:MM".
    Retourne '' si la valeur est None.

        format_datetime_fr(datetime(2026, 6, 12, 14, 30)) → "12/06/2026 14:30"
    """
    if dt is None:
        return ''
    return dt.strftime(DATETIME_FORMAT_FR)


# ─── Formatage téléphone ──────────────────────────────────────────────────────

def format_phone_fr(phone: str) -> str:
    """
    Normalise et formate un numéro de téléphone français au format "0X XX XX XX XX".
    Les numéros internationaux (+33…) sont convertis.
    Retourne la chaîne originale si le format est inconnu.

        format_phone_fr('0612345678')   → "06 12 34 56 78"
        format_phone_fr('+33612345678') → "06 12 34 56 78"
    """
    if not phone:
        return ''
    # Suppression des caractères non numériques sauf le +
    digits = re.sub(r'[^\d+]', '', phone.strip())
    # Conversion +33 → 0
    if digits.startswith('+33'):
        digits = '0' + digits[3:]
    # Numéro français à 10 chiffres
    if re.match(r'^0[1-9]\d{8}$', digits):
        return ' '.join([digits[i:i+2] for i in range(0, 10, 2)])
    # Format inconnu : retour de la valeur originale nettoyée
    return phone.strip()


# ─── Manipulation de texte ────────────────────────────────────────────────────

def truncate_text(text: str, max_len: int = 100, suffix: str = '…') -> str:
    """
    Tronque un texte à max_len caractères en coupant sur un espace.
    Ajoute suffix si tronqué.

        truncate_text("Bonjour le monde", 10) → "Bonjour le…"
    """
    if not text:
        return ''
    if len(text) <= max_len:
        return text
    # Couper sur le dernier espace avant max_len
    truncated = text[:max_len].rsplit(' ', 1)[0]
    return truncated + suffix


def slugify_unique(text: str, model_class, field: str = 'slug') -> str:
    """
    Génère un slug unique pour model_class en testant la disponibilité en base.
    Si le slug de base existe déjà, ajoute un suffixe numérique (-2, -3…).

        slugify_unique("Facture janvier", Invoice) → "facture-janvier" (ou "facture-janvier-2")
    """
    base_slug = django_slugify(text)
    if not base_slug:
        base_slug = 'objet'
    slug = base_slug
    counter = 2
    while model_class.objects.filter(**{field: slug}).exists():
        slug = f'{base_slug}-{counter}'
        counter += 1
    return slug


# ─── Réseau ───────────────────────────────────────────────────────────────────

def get_client_ip(request) -> str:
    """
    Retourne l'adresse IP réelle du client, même derrière un proxy ou load balancer.
    Prend en compte les en-têtes X-Forwarded-For, X-Real-IP, CF-Connecting-IP.
    """
    # Cloudflare
    cf_ip = request.META.get('HTTP_CF_CONNECTING_IP')
    if cf_ip:
        return cf_ip.strip()
    # Proxy / load balancer standard
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    # Nginx X-Real-IP
    x_real = request.META.get('HTTP_X_REAL_IP')
    if x_real:
        return x_real.strip()
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


# ─── Génération de références ─────────────────────────────────────────────────

def generate_reference(prefix: str, number: int, digits: int = 5) -> str:
    """
    Génère une référence formatée avec préfixe et numérotation.

        generate_reference('FAC', 42)       → "FAC-00042"
        generate_reference('DEV', 1, 4)     → "DEV-0001"
        generate_reference('CMD', 1000, 5)  → "CMD-01000"
    """
    return f'{prefix}-{str(number).zfill(digits)}'


# ─── Affichage de tailles de fichiers ────────────────────────────────────────

def file_size_display(size_bytes: int) -> str:
    """
    Convertit un nombre d'octets en chaîne lisible en français.

        file_size_display(500)         → "500 o"
        file_size_display(2048)        → "2,0 Ko"
        file_size_display(1500000)     → "1,4 Mo"
        file_size_display(2147483648)  → "2,0 Go"
    """
    if size_bytes is None or size_bytes < 0:
        return '0 o'
    if size_bytes < 1024:
        return f'{size_bytes} o'
    elif size_bytes < 1024 ** 2:
        return f'{size_bytes / 1024:.1f} Ko'.replace('.', ',')
    elif size_bytes < 1024 ** 3:
        return f'{size_bytes / (1024 ** 2):.1f} Mo'.replace('.', ',')
    else:
        return f'{size_bytes / (1024 ** 3):.1f} Go'.replace('.', ',')


# ─── Validation SIRET ─────────────────────────────────────────────────────────

def is_valid_siret(siret: str) -> bool:
    """
    Valide un numéro SIRET français par l'algorithme de Luhn.
    Le SIRET doit contenir exactement 14 chiffres (espaces ignorés).

        is_valid_siret('73282932000074') → True
        is_valid_siret('12345678901234') → False
    """
    if not siret:
        return False
    # Suppression des espaces et tirets
    cleaned = re.sub(r'[\s\-]', '', siret)
    if not cleaned.isdigit() or len(cleaned) != 14:
        return False
    # Algorithme de Luhn
    total = 0
    for i, digit in enumerate(reversed(cleaned)):
        n = int(digit)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


# ─── Accès sécurisé à des attributs imbriqués ────────────────────────────────

def safe_get(obj, *attrs, default=None):
    """
    Accède de façon sécurisée à des attributs imbriqués sur un objet.
    Retourne default si l'un des attributs est absent ou None.

        safe_get(user, 'profile', 'company', 'name')
        → user.profile.company.name  (ou None si l'un est absent)

        safe_get(order, 'customer', 'city', default='Ville inconnue')
    """
    current = obj
    for attr in attrs:
        if current is None:
            return default
        try:
            current = getattr(current, attr)
        except AttributeError:
            return default
    return current if current is not None else default
