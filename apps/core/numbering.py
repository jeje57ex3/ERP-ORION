"""
apps/core/numbering.py — Service de numérotation séquentielle atomique

Génère des numéros uniques par entreprise sans doublons via SELECT FOR UPDATE.

Utilisation :
    from apps.core.numbering import next_number
    num = next_number(company, 'invoice')  # → "FAC-2026-0042"
"""
import logging
from django.db import transaction, models
from django.utils import timezone

logger = logging.getLogger('orion')

# Format : prefix-YYYY-NNNN
SEQUENCES = {
    'invoice':        ('FAC', 'next_invoice_number'),
    'quote':          ('DEV', 'next_quote_number'),
    'order':          ('CMD', 'next_order_number'),
    'purchase_order': ('ACH', 'next_purchase_order_number'),
    'project':        ('CHT', 'next_project_number'),
    'ticket':         ('TKT', 'next_ticket_number'),
    'expense_report': ('NDF', 'next_expense_report_number'),
    'delivery':       ('BL',  'next_delivery_number'),
    'return':         ('RET', 'next_return_number'),
    'credit_note':    ('AVO', 'next_credit_note_number'),
    'journal_entry':  ('ECR', 'next_journal_entry_number'),
}


def next_number(company, sequence_type: str, alias: str = None) -> str:
    """
    Génère et retourne le prochain numéro pour un type de document.
    Utilise SELECT FOR UPDATE pour éviter les doublons en concurrence.

    Args:
        company: instance Company
        sequence_type: clé dans SEQUENCES (ex: 'invoice')
        alias: alias de base de données (None = défaut)

    Returns:
        str: numéro formaté ex. "FAC-2026-0042"
    """
    if sequence_type not in SEQUENCES:
        raise ValueError(f"Type de séquence inconnu : {sequence_type}")

    prefix, field_name = SEQUENCES[sequence_type]
    year = timezone.now().year

    try:
        from apps.core.models import CompanySettings
        using = alias or 'default'

        with transaction.atomic(using='default'):
            settings_obj = CompanySettings.objects.select_for_update().get(company=company)
            current = getattr(settings_obj, field_name, 1)
            setattr(settings_obj, field_name, current + 1)
            settings_obj.save(update_fields=[field_name])

        # Utilise le préfixe personnalisé si configuré sur l'entreprise
        custom_prefix = _get_company_prefix(company, sequence_type) or prefix
        return f"{custom_prefix}-{year}-{current:04d}"

    except Exception as e:
        logger.error("Erreur numérotation %s pour entreprise %s: %s", sequence_type, company, e)
        raise


def _get_company_prefix(company, sequence_type: str) -> str | None:
    """Retourne le préfixe personnalisé de l'entreprise si défini."""
    mapping = {
        'invoice': 'invoice_prefix',
        'quote': 'quote_prefix',
        'order': 'order_prefix',
    }
    field = mapping.get(sequence_type)
    if field:
        return getattr(company, field, None) or None
    return None


def ensure_company_settings(company):
    """Crée les CompanySettings si absents. À appeler à la création d'entreprise."""
    from apps.core.models import CompanySettings
    CompanySettings.objects.get_or_create(company=company)
