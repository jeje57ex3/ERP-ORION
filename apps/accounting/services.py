"""
apps/accounting/services.py — Service de comptabilité Orion ERP

Fonctions :
  - create_journal_entry()     : crée une écriture en brouillon (atomique)
  - validate_journal_entry()   : valide après vérification équilibre
  - reverse_journal_entry()    : extourne une écriture validée
  - create_invoice_entry()     : écriture automatique depuis une facture
  - create_payment_entry()     : écriture automatique depuis un paiement
"""
import logging
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone

logger = logging.getLogger('orion')


def create_journal_entry(
    *,
    company,
    journal,
    entry_date,
    description: str,
    lines: list[dict],
    reference: str = '',
    source_type: str = 'manual',
    source_id: int = None,
    user=None,
    auto_validate: bool = False,
):
    """
    Crée une écriture comptable avec ses lignes, dans une transaction atomique.

    Args:
        company:        entreprise
        journal:        instance Journal
        entry_date:     date de l'écriture (date)
        description:    libellé principal
        lines:          liste de dicts: [{'account': obj, 'label': str, 'debit': D, 'credit': D}]
        reference:      référence externe
        source_type:    type de source (invoice/payment/manual/…)
        source_id:      ID de l'objet source
        user:           utilisateur créateur
        auto_validate:  valider immédiatement si équilibrée

    Returns:
        JournalEntry
    """
    from apps.accounting.models import JournalEntry, JournalEntryLine

    if not lines:
        raise ValidationError("Une écriture doit avoir au moins une ligne.")

    total_debit = sum(Decimal(str(l.get('debit', 0))) for l in lines)
    total_credit = sum(Decimal(str(l.get('credit', 0))) for l in lines)

    if auto_validate and abs(total_debit - total_credit) >= Decimal('0.01'):
        raise ValidationError(
            f"Écriture déséquilibrée: débit={total_debit}, crédit={total_credit}."
        )

    with transaction.atomic():
        entry = JournalEntry(
            company=company,
            journal=journal,
            entry_date=entry_date,
            description=description,
            reference=reference,
            source_type=source_type,
            source_id=source_id,
            created_by=user,
            status='draft',
        )
        # Bypass clean() pour le brouillon (pas encore de pk)
        JournalEntry.objects.bulk_create([entry]) if False else entry.save()

        for line_data in lines:
            JournalEntryLine.objects.create(
                entry=entry,
                account=line_data['account'],
                label=line_data.get('label', description),
                debit=Decimal(str(line_data.get('debit', 0))),
                credit=Decimal(str(line_data.get('credit', 0))),
                due_date=line_data.get('due_date'),
                partner_name=line_data.get('partner_name', ''),
                analytic_axis=line_data.get('analytic_axis', ''),
                project=line_data.get('project', ''),
            )

        if auto_validate:
            validate_journal_entry(entry, user)

        logger.info(
            "Écriture créée: %s | D=%.2f C=%.2f | %s",
            description, total_debit, total_credit, company.name
        )
        return entry


def validate_journal_entry(entry, user):
    """Valide une écriture après vérification de l'équilibre."""
    entry.validate(user)
    try:
        from apps.core.audit_service import log_validate
        log_validate(None, entry, module='accounting')
    except Exception:
        pass
    return entry


def reverse_journal_entry(entry, user, reverse_date=None):
    """Crée l'écriture d'extourne d'une écriture validée."""
    rev = entry.reverse(user, reverse_date)
    if rev.status == 'draft':
        validate_journal_entry(rev, user)
    try:
        from apps.core.audit_service import log_action
        log_action(None, 'other', module='accounting', obj=entry,
                   description=f"Extourne créée: {rev.entry_number or rev.pk}",
                   company=entry.company, user=user)
    except Exception:
        pass
    return rev


def get_account_balance(account, from_date=None, to_date=None):
    """Calcule le solde d'un compte (débit - crédit) sur une période."""
    from apps.accounting.models import JournalEntryLine
    from django.db.models import Sum

    qs = JournalEntryLine.objects.filter(
        account=account,
        entry__status='validated',
    )
    if from_date:
        qs = qs.filter(entry__entry_date__gte=from_date)
    if to_date:
        qs = qs.filter(entry__entry_date__lte=to_date)

    totals = qs.aggregate(
        total_debit=Sum('debit'),
        total_credit=Sum('credit'),
    )
    debit = totals['total_debit'] or Decimal(0)
    credit = totals['total_credit'] or Decimal(0)
    return debit - credit
