"""
apps/accounting/models.py — Module Comptabilité avancé
Plan comptable, journaux, écritures, TVA, paiements, banque, trésorerie, immobilisations, NDF.
"""
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.core.models import Company


# ─── EXERCICE & PÉRIODE ───────────────────────────────────────────────────────

class FiscalYear(models.Model):
    STATUS_CHOICES = [
        ('open', 'Ouvert'), ('closing', 'En cours de clôture'), ('closed', 'Clôturé'),
    ]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='fiscal_years')
    name = models.CharField('Nom', max_length=100)
    start_date = models.DateField('Début')
    end_date = models.DateField('Fin')
    status = models.CharField('Statut', max_length=10, choices=STATUS_CHOICES, default='open')
    is_closed = models.BooleanField('Clôturé', default=False)
    closed_at = models.DateTimeField('Clôturé le', null=True, blank=True)
    closed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Exercice comptable'
        verbose_name_plural = 'Exercices comptables'
        ordering = ['-start_date']

    def __str__(self):
        return f'{self.name} ({self.start_date.year})'

    @property
    def is_open(self):
        return self.status == 'open'


class AccountingPeriod(models.Model):
    STATUS_CHOICES = [
        ('open', 'Ouverte'), ('locked', 'Verrouillée'), ('closed', 'Clôturée'),
    ]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='accounting_periods')
    fiscal_year = models.ForeignKey(FiscalYear, on_delete=models.CASCADE, related_name='periods')
    name = models.CharField('Nom', max_length=50)
    start_date = models.DateField('Début')
    end_date = models.DateField('Fin')
    status = models.CharField('Statut', max_length=10, choices=STATUS_CHOICES, default='open')

    class Meta:
        verbose_name = 'Période comptable'
        verbose_name_plural = 'Périodes comptables'
        ordering = ['start_date']

    def __str__(self):
        return f'{self.name} ({self.fiscal_year.name})'

    @property
    def is_open(self):
        return self.status == 'open'


# ─── PLAN COMPTABLE ───────────────────────────────────────────────────────────

class Account(models.Model):
    TYPE_CHOICES = [
        ('asset', 'Actif'), ('liability', 'Passif'), ('expense', 'Charge'), ('revenue', 'Produit'),
        ('receivable', 'Client'), ('payable', 'Fournisseur'), ('bank', 'Banque/Trésorerie'),
        ('tax', 'TVA'), ('fixed_asset', 'Immobilisation'), ('equity', 'Capitaux propres'),
        ('depreciation', 'Amortissement'), ('other', 'Autre'),
    ]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='chart_accounts')
    number = models.CharField('Numéro', max_length=20)
    name = models.CharField('Intitulé', max_length=200)
    account_type = models.CharField('Type', max_length=20, choices=TYPE_CHOICES, default='other')
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children')
    is_active = models.BooleanField('Actif', default=True)
    allow_manual_entries = models.BooleanField('Saisie manuelle autorisée', default=True)
    notes = models.TextField('Notes', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Compte comptable'
        verbose_name_plural = 'Plan comptable'
        ordering = ['number']
        unique_together = ['company', 'number']

    def __str__(self):
        return f'{self.number} — {self.name}'

    @property
    def is_debit_normal(self):
        return self.account_type in ('asset', 'expense', 'receivable', 'fixed_asset', 'depreciation')


# ─── JOURNAUX ─────────────────────────────────────────────────────────────────

class Journal(models.Model):
    TYPE_CHOICES = [
        ('sale', 'Vente'), ('purchase', 'Achat'), ('bank', 'Banque'), ('cash', 'Caisse'),
        ('misc', 'Opérations diverses'), ('payroll', 'Paie'), ('fixed_asset', 'Immobilisations'),
    ]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='journals')
    code = models.CharField('Code', max_length=10)
    name = models.CharField('Nom', max_length=100)
    journal_type = models.CharField('Type', max_length=20, choices=TYPE_CHOICES)
    default_debit_account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True, related_name='debit_journals')
    default_credit_account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True, related_name='credit_journals')
    is_active = models.BooleanField('Actif', default=True)

    class Meta:
        verbose_name = 'Journal comptable'
        verbose_name_plural = 'Journaux comptables'
        unique_together = ['company', 'code']

    def __str__(self):
        return f'{self.code} — {self.name}'


# ─── ÉCRITURES COMPTABLES ─────────────────────────────────────────────────────

class JournalEntry(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Brouillon'), ('validated', 'Validée'), ('cancelled', 'Annulée'), ('reversed', 'Extournée'),
    ]
    SOURCE_CHOICES = [
        ('manual', 'Saisie manuelle'), ('invoice', 'Facture client'), ('supplier_invoice', 'Facture fournisseur'),
        ('payment', 'Paiement'), ('expense', 'Note de frais'), ('payroll', 'Paie'),
        ('fixed_asset', 'Immobilisation'), ('closing', 'Clôture'), ('other', 'Autre'),
    ]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='new_journal_entries')
    journal = models.ForeignKey(Journal, on_delete=models.PROTECT, related_name='entries')
    fiscal_year = models.ForeignKey(FiscalYear, on_delete=models.PROTECT, null=True, blank=True)
    period = models.ForeignKey(AccountingPeriod, on_delete=models.PROTECT, null=True, blank=True)
    entry_number = models.CharField('Numéro', max_length=30, blank=True)
    entry_date = models.DateField('Date')
    description = models.CharField('Libellé', max_length=300)
    reference = models.CharField('Référence', max_length=100, blank=True)
    source_type = models.CharField('Source', max_length=30, choices=SOURCE_CHOICES, default='manual')
    source_id = models.PositiveIntegerField('ID source', null=True, blank=True)
    status = models.CharField('Statut', max_length=15, choices=STATUS_CHOICES, default='draft')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_entries')
    validated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='validated_entries')
    validated_at = models.DateTimeField('Validé le', null=True, blank=True)
    reversed_entry = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='reverse_of')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Écriture comptable'
        verbose_name_plural = 'Écritures comptables'
        ordering = ['-entry_date', '-created_at']

    def __str__(self):
        return f'{self.entry_number or "BROUILLON"} — {self.description[:50]}'

    @property
    def total_debit(self):
        return sum(l.debit for l in self.lines.all())

    @property
    def total_credit(self):
        return sum(l.credit for l in self.lines.all())

    @property
    def is_balanced(self):
        return abs(self.total_debit - self.total_credit) < 0.01

    def clean(self):
        if self.pk:
            try:
                original = JournalEntry.objects.get(pk=self.pk)
                if original.status in ('validated', 'cancelled', 'reversed'):
                    raise ValidationError(
                        f"Impossible de modifier une écriture {original.get_status_display().lower()}. "
                        "Utilisez l'extourne pour corriger."
                    )
            except JournalEntry.DoesNotExist:
                pass

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def validate(self, user):
        if not self.is_balanced:
            raise ValidationError("L'écriture est déséquilibrée. Le total débit doit être égal au total crédit.")
        if self.period and not self.period.is_open:
            raise ValidationError("Impossible d'écrire sur une période clôturée.")
        if self.status != 'draft':
            raise ValidationError("Impossible de valider une écriture déjà validée ou annulée.")
        from django.db import transaction
        with transaction.atomic():
            self.status = 'validated'
            self.validated_by = user
            self.validated_at = timezone.now()
            JournalEntry.objects.filter(pk=self.pk).update(
                status='validated', validated_by=user, validated_at=timezone.now()
            )
        self.refresh_from_db()

    def reverse(self, user, reverse_date=None):
        """Crée une écriture d'extourne."""
        if self.status != 'validated':
            raise ValidationError("Seules les écritures validées peuvent être extournées.")
        rev = JournalEntry.objects.create(
            company=self.company, journal=self.journal, fiscal_year=self.fiscal_year,
            period=self.period, entry_date=reverse_date or timezone.now().date(),
            description=f'Extourne : {self.description}', reference=self.reference,
            source_type='other', created_by=user, status='draft',
        )
        for line in self.lines.all():
            JournalEntryLine.objects.create(
                entry=rev, account=line.account, label=line.label,
                debit=line.credit, credit=line.debit,
            )
        self.status = 'reversed'
        self.reversed_entry = rev
        self.save()
        return rev


class JournalEntryLine(models.Model):
    entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name='lines')
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='entry_lines')
    partner_name = models.CharField('Tiers', max_length=200, blank=True)
    label = models.CharField('Libellé', max_length=300, blank=True)
    debit = models.DecimalField('Débit', max_digits=14, decimal_places=2, default=0)
    credit = models.DecimalField('Crédit', max_digits=14, decimal_places=2, default=0)
    due_date = models.DateField('Échéance', null=True, blank=True)
    reconciliation_code = models.CharField('Code lettrage', max_length=20, blank=True)
    analytic_axis = models.CharField('Axe analytique', max_length=100, blank=True)
    project = models.CharField('Chantier/Projet', max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Ligne d\'écriture'
        verbose_name_plural = 'Lignes d\'écriture'

    def __str__(self):
        return f'{self.account.number} | D:{self.debit} C:{self.credit} | {self.label[:40]}'

    @property
    def balance(self):
        return self.debit - self.credit


# ─── TVA ──────────────────────────────────────────────────────────────────────

class TaxRate(models.Model):
    TYPE_CHOICES = [
        ('collected', 'TVA collectée'), ('deductible', 'TVA déductible'),
        ('exempt', 'Exonéré'), ('reverse_charge', 'Autoliquidation'),
    ]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='tax_rates')
    name = models.CharField('Nom', max_length=100)
    rate = models.DecimalField('Taux %', max_digits=5, decimal_places=2)
    tax_type = models.CharField('Type', max_length=20, choices=TYPE_CHOICES)
    collected_tax_account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True, related_name='collected_tax')
    deductible_tax_account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True, related_name='deductible_tax')
    is_active = models.BooleanField('Actif', default=True)
    is_default = models.BooleanField('Par défaut', default=False)

    class Meta:
        verbose_name = 'Taux de TVA'
        verbose_name_plural = 'Taux de TVA'

    def __str__(self):
        return f'{self.name} ({self.rate}%)'


# ─── PAIEMENTS ────────────────────────────────────────────────────────────────

class BankAccount(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='bank_accounts')
    bank_name = models.CharField('Banque', max_length=100)
    account_name = models.CharField('Nom du compte', max_length=100)
    iban = models.CharField('IBAN', max_length=34, blank=True)
    bic = models.CharField('BIC', max_length=11, blank=True)
    accounting_account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True, related_name='bank_account_links')
    opening_balance = models.DecimalField('Solde d\'ouverture', max_digits=14, decimal_places=2, default=0)
    current_balance = models.DecimalField('Solde courant', max_digits=14, decimal_places=2, default=0)
    is_active = models.BooleanField('Actif', default=True)

    class Meta:
        verbose_name = 'Compte bancaire'
        verbose_name_plural = 'Comptes bancaires'

    def __str__(self):
        return f'{self.bank_name} — {self.account_name}'


class Payment(models.Model):
    TYPE_CHOICES = [
        ('customer_payment', 'Encaissement client'), ('supplier_payment', 'Paiement fournisseur'),
        ('refund', 'Remboursement'), ('credit_note', 'Avoir'), ('other', 'Autre'),
    ]
    METHOD_CHOICES = [
        ('bank_transfer', 'Virement'), ('check', 'Chèque'), ('cash', 'Espèces'),
        ('card', 'Carte bancaire'), ('direct_debit', 'Prélèvement'), ('other', 'Autre'),
    ]
    STATUS_CHOICES = [
        ('draft', 'Brouillon'), ('validated', 'Validé'), ('reconciled', 'Rapproché'), ('cancelled', 'Annulé'),
    ]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='payments')
    payment_type = models.CharField('Type', max_length=25, choices=TYPE_CHOICES)
    partner_name = models.CharField('Tiers', max_length=200)
    amount = models.DecimalField('Montant', max_digits=14, decimal_places=2)
    payment_date = models.DateField('Date')
    payment_method = models.CharField('Méthode', max_length=20, choices=METHOD_CHOICES)
    bank_account = models.ForeignKey(BankAccount, on_delete=models.SET_NULL, null=True, blank=True)
    reference = models.CharField('Référence', max_length=100, blank=True)
    status = models.CharField('Statut', max_length=15, choices=STATUS_CHOICES, default='draft')
    linked_invoice_id = models.PositiveIntegerField('ID Facture liée', null=True, blank=True)
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.SET_NULL, null=True, blank=True, related_name='payments')
    notes = models.TextField('Notes', blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Paiement'
        verbose_name_plural = 'Paiements'
        ordering = ['-payment_date']

    def __str__(self):
        return f'{self.get_payment_type_display()} — {self.partner_name} — {self.amount} €'


# ─── RAPPROCHEMENT BANCAIRE ───────────────────────────────────────────────────

class BankStatement(models.Model):
    STATUS_CHOICES = [
        ('imported', 'Importé'), ('in_progress', 'En cours'), ('validated', 'Validé'),
    ]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='bank_statements')
    bank_account = models.ForeignKey(BankAccount, on_delete=models.CASCADE, related_name='statements')
    statement_date = models.DateField('Date relevé')
    start_balance = models.DecimalField('Solde initial', max_digits=14, decimal_places=2, default=0)
    end_balance = models.DecimalField('Solde final', max_digits=14, decimal_places=2, default=0)
    import_file = models.FileField('Fichier relevé', upload_to='bank_statements/', blank=True)
    status = models.CharField('Statut', max_length=15, choices=STATUS_CHOICES, default='imported')
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Relevé bancaire'
        verbose_name_plural = 'Relevés bancaires'
        ordering = ['-statement_date']

    def __str__(self):
        return f'{self.bank_account} — {self.statement_date}'


class BankStatementLine(models.Model):
    statement = models.ForeignKey(BankStatement, on_delete=models.CASCADE, related_name='lines')
    operation_date = models.DateField('Date opération')
    label = models.CharField('Libellé', max_length=300)
    amount = models.DecimalField('Montant', max_digits=14, decimal_places=2)
    reference = models.CharField('Référence', max_length=100, blank=True)
    is_reconciled = models.BooleanField('Rapproché', default=False)
    matched_payment = models.ForeignKey(Payment, on_delete=models.SET_NULL, null=True, blank=True)
    matched_entry = models.ForeignKey(JournalEntry, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = 'Ligne de relevé'
        verbose_name_plural = 'Lignes de relevé'
        ordering = ['-operation_date']

    def __str__(self):
        return f'{self.operation_date} | {self.label[:50]} | {self.amount} €'


class Reconciliation(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='reconciliations')
    bank_statement_line = models.OneToOneField(BankStatementLine, on_delete=models.CASCADE, related_name='reconciliation')
    payment = models.ForeignKey(Payment, on_delete=models.SET_NULL, null=True, blank=True)
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField('Montant', max_digits=14, decimal_places=2)
    reconciled_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    reconciled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Rapprochement'
        verbose_name_plural = 'Rapprochements'


# ─── NOTES DE FRAIS ───────────────────────────────────────────────────────────

class ExpenseReport(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Brouillon'), ('submitted', 'Soumise'), ('validated', 'Validée'),
        ('refused', 'Refusée'), ('paid', 'Payée'), ('booked', 'Comptabilisée'),
    ]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='accounting_expense_reports')
    employee = models.ForeignKey('hr.Employee', on_delete=models.PROTECT, null=True, blank=True, related_name='accounting_expense_reports')
    title = models.CharField('Titre', max_length=200)
    period_start = models.DateField('Début de période')
    period_end = models.DateField('Fin de période')
    total_amount = models.DecimalField('Total TTC', max_digits=12, decimal_places=2, default=0)
    status = models.CharField('Statut', max_length=15, choices=STATUS_CHOICES, default='draft')
    submitted_at = models.DateTimeField('Soumise le', null=True, blank=True)
    validated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='validated_expenses')
    validated_at = models.DateTimeField('Validée le', null=True, blank=True)
    refused_reason = models.TextField('Motif de refus', blank=True)
    paid_at = models.DateField('Payée le', null=True, blank=True)
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Note de frais'
        verbose_name_plural = 'Notes de frais'
        ordering = ['-period_start']

    def __str__(self):
        return f'{self.title} — {self.employee} ({self.get_status_display()})'

    def recalc_total(self):
        self.total_amount = sum(l.amount_ttc for l in self.lines.all())
        self.save(update_fields=['total_amount'])


class ExpenseReportLine(models.Model):
    CATEGORY_CHOICES = [
        ('transport', 'Transport'), ('fuel', 'Carburant'), ('hotel', 'Hébergement'),
        ('restaurant', 'Repas'), ('parking', 'Stationnement'), ('toll', 'Péage'),
        ('phone', 'Téléphone'), ('supplies', 'Fournitures'), ('other', 'Autre'),
    ]
    expense_report = models.ForeignKey(ExpenseReport, on_delete=models.CASCADE, related_name='lines')
    date = models.DateField('Date')
    category = models.CharField('Catégorie', max_length=20, choices=CATEGORY_CHOICES)
    description = models.CharField('Description', max_length=300)
    amount_ht = models.DecimalField('Montant HT', max_digits=10, decimal_places=2)
    tax_rate = models.ForeignKey(TaxRate, on_delete=models.SET_NULL, null=True, blank=True)
    amount_ttc = models.DecimalField('Montant TTC', max_digits=10, decimal_places=2)
    receipt = models.FileField('Justificatif', upload_to='expense_receipts/', blank=True)
    account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = 'Ligne note de frais'
        ordering = ['date']

    def __str__(self):
        return f'{self.date} — {self.description} — {self.amount_ttc} €'


# ─── IMMOBILISATIONS ──────────────────────────────────────────────────────────

class FixedAsset(models.Model):
    METHOD_CHOICES = [
        ('linear', 'Linéaire'), ('degressive', 'Dégressif'),
    ]
    STATUS_CHOICES = [
        ('active', 'Actif'), ('fully_depreciated', 'Totalement amorti'), ('disposed', 'Cédé'),
    ]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='fixed_assets')
    name = models.CharField('Nom', max_length=200)
    asset_number = models.CharField('N° immobilisation', max_length=30, blank=True)
    purchase_date = models.DateField('Date d\'acquisition')
    purchase_value = models.DecimalField('Valeur d\'acquisition HT', max_digits=14, decimal_places=2)
    asset_account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True, related_name='asset_accounts')
    depreciation_account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True, related_name='depreciation_accounts')
    expense_account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True, related_name='expense_accounts')
    depreciation_method = models.CharField('Méthode', max_length=15, choices=METHOD_CHOICES, default='linear')
    duration_months = models.PositiveIntegerField('Durée (mois)')
    residual_value = models.DecimalField('Valeur résiduelle', max_digits=14, decimal_places=2, default=0)
    accumulated_depreciation = models.DecimalField('Amortissements cumulés', max_digits=14, decimal_places=2, default=0)
    status = models.CharField('Statut', max_length=20, choices=STATUS_CHOICES, default='active')
    notes = models.TextField('Notes', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Immobilisation'
        verbose_name_plural = 'Immobilisations'
        ordering = ['-purchase_date']

    def __str__(self):
        return f'{self.asset_number or "IMM"} — {self.name}'

    @property
    def net_book_value(self):
        return self.purchase_value - self.accumulated_depreciation

    @property
    def annual_depreciation(self):
        if self.duration_months > 0:
            return (self.purchase_value - self.residual_value) / (self.duration_months / 12)
        return 0


class DepreciationLine(models.Model):
    asset = models.ForeignKey(FixedAsset, on_delete=models.CASCADE, related_name='depreciation_lines')
    period = models.ForeignKey(AccountingPeriod, on_delete=models.SET_NULL, null=True, blank=True)
    depreciation_date = models.DateField('Date')
    amount = models.DecimalField('Montant', max_digits=14, decimal_places=2)
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField('Statut', max_length=15, choices=[('planned', 'Planifié'), ('booked', 'Comptabilisé')], default='planned')

    class Meta:
        verbose_name = 'Ligne d\'amortissement'
        verbose_name_plural = 'Plan d\'amortissement'
        ordering = ['depreciation_date']

    def __str__(self):
        return f'{self.asset.name} — {self.depreciation_date} — {self.amount} €'


# ─── SERVICES AUTOMATIQUES ────────────────────────────────────────────────────

def _auto_entry_number(company, journal):
    from django.db.models import Max
    last = JournalEntry.objects.filter(company=company, journal=journal).aggregate(Max('entry_number'))['entry_number__max']
    try:
        num = int(last.split('-')[-1]) + 1 if last else 1
    except (ValueError, AttributeError):
        num = 1
    return f'{journal.code}-{num:06d}'
