"""
apps/core/constants.py — Constantes globales réutilisables Orion ERP

Importer selon les besoins :
    from apps.core.constants import STATUS_ACTIVE, VAT_RATES, DEFAULT_PAGE_SIZE
"""

# ─── Statuts génériques ───────────────────────────────────────────────────────

STATUS_DRAFT = 'draft'           # Brouillon
STATUS_ACTIVE = 'active'         # Actif / en cours
STATUS_PENDING = 'pending'       # En attente
STATUS_CONFIRMED = 'confirmed'   # Confirmé
STATUS_VALIDATED = 'validated'   # Validé (verrouillé)
STATUS_SENT = 'sent'             # Envoyé (devis, facture…)
STATUS_ACCEPTED = 'accepted'     # Accepté
STATUS_REJECTED = 'rejected'     # Rejeté / refusé
STATUS_CANCELLED = 'cancelled'   # Annulé
STATUS_CLOSED = 'closed'         # Clôturé
STATUS_ARCHIVED = 'archived'     # Archivé
STATUS_DELETED = 'deleted'       # Supprimé (soft delete)
STATUS_PAID = 'paid'             # Payé
STATUS_PARTIAL = 'partial'       # Partiellement payé
STATUS_OVERDUE = 'overdue'       # En retard de paiement
STATUS_SHIPPED = 'shipped'       # Expédié
STATUS_DELIVERED = 'delivered'   # Livré
STATUS_RETURNED = 'returned'     # Retourné
STATUS_IN_PROGRESS = 'in_progress'  # En cours de traitement

# Choix Django pour les statuts courants (devis, factures, commandes)
DOCUMENT_STATUS_CHOICES = [
    (STATUS_DRAFT, 'Brouillon'),
    (STATUS_PENDING, 'En attente'),
    (STATUS_SENT, 'Envoyé'),
    (STATUS_ACCEPTED, 'Accepté'),
    (STATUS_VALIDATED, 'Validé'),
    (STATUS_REJECTED, 'Rejeté'),
    (STATUS_CANCELLED, 'Annulé'),
    (STATUS_ARCHIVED, 'Archivé'),
]

PAYMENT_STATUS_CHOICES = [
    (STATUS_PENDING, 'En attente'),
    (STATUS_PARTIAL, 'Partiellement payé'),
    (STATUS_PAID, 'Payé'),
    (STATUS_OVERDUE, 'En retard'),
    (STATUS_CANCELLED, 'Annulé'),
]

ORDER_STATUS_CHOICES = [
    (STATUS_DRAFT, 'Brouillon'),
    (STATUS_CONFIRMED, 'Confirmée'),
    (STATUS_IN_PROGRESS, 'En préparation'),
    (STATUS_SHIPPED, 'Expédiée'),
    (STATUS_DELIVERED, 'Livrée'),
    (STATUS_RETURNED, 'Retournée'),
    (STATUS_CANCELLED, 'Annulée'),
]


# ─── Devises ──────────────────────────────────────────────────────────────────

CURRENCY_EUR = 'EUR'
CURRENCY_USD = 'USD'
CURRENCY_GBP = 'GBP'
CURRENCY_CHF = 'CHF'
CURRENCY_CAD = 'CAD'
CURRENCY_JPY = 'JPY'
CURRENCY_AED = 'AED'
CURRENCY_MAD = 'MAD'
CURRENCY_TND = 'TND'

CURRENCY_CHOICES = [
    (CURRENCY_EUR, 'Euro (€)'),
    (CURRENCY_USD, 'Dollar américain ($)'),
    (CURRENCY_GBP, 'Livre sterling (£)'),
    (CURRENCY_CHF, 'Franc suisse (CHF)'),
    (CURRENCY_CAD, 'Dollar canadien (CA$)'),
    (CURRENCY_JPY, 'Yen japonais (¥)'),
    (CURRENCY_AED, 'Dirham émirien (AED)'),
    (CURRENCY_MAD, 'Dirham marocain (MAD)'),
    (CURRENCY_TND, 'Dinar tunisien (TND)'),
]

CURRENCY_SYMBOLS = {
    CURRENCY_EUR: '€',
    CURRENCY_USD: '$',
    CURRENCY_GBP: '£',
    CURRENCY_CHF: 'CHF',
    CURRENCY_CAD: 'CA$',
    CURRENCY_JPY: '¥',
    CURRENCY_AED: 'AED',
    CURRENCY_MAD: 'MAD',
    CURRENCY_TND: 'TND',
}


# ─── Taux de TVA (France) ─────────────────────────────────────────────────────

VAT_RATE_ZERO = 0
VAT_RATE_SUPER_REDUCED = 2.1
VAT_RATE_REDUCED_1 = 5.5
VAT_RATE_REDUCED_2 = 10
VAT_RATE_NORMAL = 20

VAT_RATES = [
    (VAT_RATE_ZERO, '0 %'),
    (VAT_RATE_SUPER_REDUCED, '2,1 %'),
    (VAT_RATE_REDUCED_1, '5,5 %'),
    (VAT_RATE_REDUCED_2, '10 %'),
    (VAT_RATE_NORMAL, '20 %'),
]


# ─── Pays (Europe principale + DOM-TOM + Maghreb) ─────────────────────────────

COUNTRIES_FR = [
    ('FR', 'France'),
    ('BE', 'Belgique'),
    ('CH', 'Suisse'),
    ('LU', 'Luxembourg'),
    ('MC', 'Monaco'),
    ('DE', 'Allemagne'),
    ('ES', 'Espagne'),
    ('IT', 'Italie'),
    ('PT', 'Portugal'),
    ('NL', 'Pays-Bas'),
    ('AT', 'Autriche'),
    ('DK', 'Danemark'),
    ('SE', 'Suède'),
    ('NO', 'Norvège'),
    ('FI', 'Finlande'),
    ('PL', 'Pologne'),
    ('CZ', 'République tchèque'),
    ('GB', 'Royaume-Uni'),
    ('IE', 'Irlande'),
    ('US', 'États-Unis'),
    ('CA', 'Canada'),
    ('MA', 'Maroc'),
    ('DZ', 'Algérie'),
    ('TN', 'Tunisie'),
    ('SN', 'Sénégal'),
    ('CI', "Côte d'Ivoire"),
    ('CM', 'Cameroun'),
    ('GP', 'Guadeloupe'),
    ('MQ', 'Martinique'),
    ('GF', 'Guyane française'),
    ('RE', 'La Réunion'),
    ('YT', 'Mayotte'),
    ('NC', 'Nouvelle-Calédonie'),
    ('PF', 'Polynésie française'),
]


# ─── Upload de fichiers ───────────────────────────────────────────────────────

# Taille maximale d'un fichier uploadé (10 Mo)
MAX_UPLOAD_SIZE = 10 * 1024 * 1024

# Taille maximale d'une image (5 Mo)
MAX_IMAGE_SIZE = 5 * 1024 * 1024

ALLOWED_IMAGE_TYPES = [
    'image/jpeg',
    'image/png',
    'image/webp',
    'image/gif',
    'image/svg+xml',
]

ALLOWED_DOCUMENT_TYPES = [
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-powerpoint',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'text/plain',
    'text/csv',
    'application/zip',
    'application/x-zip-compressed',
]

ALLOWED_MEDIA_TYPES = ALLOWED_IMAGE_TYPES + ALLOWED_DOCUMENT_TYPES


# ─── Formats de dates (France) ───────────────────────────────────────────────

DATE_FORMAT_FR = '%d/%m/%Y'
DATETIME_FORMAT_FR = '%d/%m/%Y %H:%M'
DATETIME_LONG_FORMAT_FR = '%d/%m/%Y à %H:%M:%S'
TIME_FORMAT_FR = '%H:%M'
MONTH_FORMAT_FR = '%m/%Y'
YEAR_FORMAT_FR = '%Y'


# ─── Pagination ───────────────────────────────────────────────────────────────

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 200
PAGE_SIZE_CHOICES = [10, 25, 50, 100, 200]


# ─── Délais de paiement (jours) ───────────────────────────────────────────────

PAYMENT_TERMS_IMMEDIATE = 0
PAYMENT_TERMS_30_DAYS = 30
PAYMENT_TERMS_45_DAYS = 45
PAYMENT_TERMS_60_DAYS = 60
PAYMENT_TERMS_90_DAYS = 90

PAYMENT_TERMS_CHOICES = [
    (PAYMENT_TERMS_IMMEDIATE, 'Comptant'),
    (PAYMENT_TERMS_30_DAYS, '30 jours'),
    (PAYMENT_TERMS_45_DAYS, '45 jours'),
    (PAYMENT_TERMS_60_DAYS, '60 jours'),
    (PAYMENT_TERMS_90_DAYS, '90 jours'),
]


# ─── Modes de paiement ───────────────────────────────────────────────────────

PAYMENT_METHOD_CASH = 'cash'
PAYMENT_METHOD_CHECK = 'check'
PAYMENT_METHOD_TRANSFER = 'transfer'
PAYMENT_METHOD_CARD = 'card'
PAYMENT_METHOD_DIRECT_DEBIT = 'direct_debit'
PAYMENT_METHOD_PAYPAL = 'paypal'
PAYMENT_METHOD_STRIPE = 'stripe'
PAYMENT_METHOD_ALMA = 'alma'
PAYMENT_METHOD_OTHER = 'other'

PAYMENT_METHOD_CHOICES = [
    (PAYMENT_METHOD_CASH, 'Espèces'),
    (PAYMENT_METHOD_CHECK, 'Chèque'),
    (PAYMENT_METHOD_TRANSFER, 'Virement bancaire'),
    (PAYMENT_METHOD_CARD, 'Carte bancaire'),
    (PAYMENT_METHOD_DIRECT_DEBIT, 'Prélèvement automatique'),
    (PAYMENT_METHOD_PAYPAL, 'PayPal'),
    (PAYMENT_METHOD_STRIPE, 'Stripe'),
    (PAYMENT_METHOD_ALMA, 'Alma (paiement fractionné)'),
    (PAYMENT_METHOD_OTHER, 'Autre'),
]


# ─── Unités de mesure ─────────────────────────────────────────────────────────

UNIT_PIECE = 'pce'
UNIT_KG = 'kg'
UNIT_GRAM = 'g'
UNIT_LITER = 'l'
UNIT_METER = 'm'
UNIT_SQUARE_METER = 'm2'
UNIT_CUBIC_METER = 'm3'
UNIT_HOUR = 'h'
UNIT_DAY = 'jour'
UNIT_FORFAIT = 'forfait'
UNIT_BOX = 'carton'
UNIT_PACK = 'lot'

UNIT_CHOICES = [
    (UNIT_PIECE, 'Pièce'),
    (UNIT_KG, 'Kilogramme (kg)'),
    (UNIT_GRAM, 'Gramme (g)'),
    (UNIT_LITER, 'Litre (L)'),
    (UNIT_METER, 'Mètre linéaire (m)'),
    (UNIT_SQUARE_METER, 'Mètre carré (m²)'),
    (UNIT_CUBIC_METER, 'Mètre cube (m³)'),
    (UNIT_HOUR, 'Heure (h)'),
    (UNIT_DAY, 'Jour'),
    (UNIT_FORFAIT, 'Forfait'),
    (UNIT_BOX, 'Carton'),
    (UNIT_PACK, 'Lot'),
]


# ─── Priorités ────────────────────────────────────────────────────────────────

PRIORITY_LOW = 'low'
PRIORITY_NORMAL = 'normal'
PRIORITY_HIGH = 'high'
PRIORITY_URGENT = 'urgent'

PRIORITY_CHOICES = [
    (PRIORITY_LOW, 'Faible'),
    (PRIORITY_NORMAL, 'Normale'),
    (PRIORITY_HIGH, 'Haute'),
    (PRIORITY_URGENT, 'Urgente'),
]

PRIORITY_COLORS = {
    PRIORITY_LOW: 'secondary',
    PRIORITY_NORMAL: 'primary',
    PRIORITY_HIGH: 'warning',
    PRIORITY_URGENT: 'danger',
}


# ─── Longueurs de champs fréquentes ──────────────────────────────────────────

MAX_LENGTH_NAME = 200
MAX_LENGTH_SHORT = 100
MAX_LENGTH_CODE = 50
MAX_LENGTH_PHONE = 20
MAX_LENGTH_EMAIL = 254
MAX_LENGTH_URL = 500
MAX_LENGTH_REF = 30
MAX_LENGTH_SLUG = 100
