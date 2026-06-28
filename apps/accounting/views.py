"""
apps/accounting/views.py — Module Comptabilité avancé
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Q
from django.utils import timezone
from decimal import Decimal
from .models import (
    FiscalYear, AccountingPeriod, Account, Journal, JournalEntry, JournalEntryLine,
    TaxRate, Payment, BankAccount, BankStatement, BankStatementLine, Reconciliation,
    ExpenseReport, ExpenseReportLine, FixedAsset, DepreciationLine, _auto_entry_number,
)


def _company(request):
    return request.current_company


# ─── DASHBOARD ────────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    company = _company(request)
    today = timezone.now().date()
    bank_total = BankAccount.objects.filter(company=company, is_active=True).aggregate(
        s=Sum('current_balance'))['s'] or 0
    draft_entries = JournalEntry.objects.filter(company=company, status='draft').count()
    pending_expenses = ExpenseReport.objects.filter(company=company, status='submitted').count()
    recent_entries = JournalEntry.objects.filter(company=company).select_related('journal').order_by('-created_at')[:10]
    return render(request, 'accounting/dashboard.html', {
        'bank_total': bank_total,
        'draft_entries': draft_entries,
        'pending_expenses': pending_expenses,
        'recent_entries': recent_entries,
        'today': today,
    })


# ─── PLAN COMPTABLE ───────────────────────────────────────────────────────────

@login_required
def account_list(request):
    company = _company(request)
    type_filter = request.GET.get('type', '')
    q = request.GET.get('q', '')
    accounts = Account.objects.filter(company=company)
    if type_filter:
        accounts = accounts.filter(account_type=type_filter)
    if q:
        accounts = accounts.filter(Q(number__icontains=q) | Q(name__icontains=q))
    return render(request, 'accounting/account_list.html', {
        'accounts': accounts, 'type_choices': Account.TYPE_CHOICES,
        'type_filter': type_filter, 'q': q,
    })


@login_required
def account_create(request):
    company = _company(request)
    if request.method == 'POST':
        acc = Account.objects.create(
            company=company,
            number=request.POST.get('number', ''),
            name=request.POST.get('name', ''),
            account_type=request.POST.get('account_type', 'other'),
            allow_manual_entries=bool(request.POST.get('allow_manual_entries')),
        )
        messages.success(request, f'Compte {acc.number} — {acc.name} créé.')
        return redirect('accounting:account_list')
    return render(request, 'accounting/account_form.html', {'type_choices': Account.TYPE_CHOICES})


@login_required
def account_edit(request, pk):
    account = get_object_or_404(Account, pk=pk, company=_company(request))
    if request.method == 'POST':
        account.number = request.POST.get('number', account.number)
        account.name = request.POST.get('name', account.name)
        account.account_type = request.POST.get('account_type', account.account_type)
        account.is_active = bool(request.POST.get('is_active'))
        account.allow_manual_entries = bool(request.POST.get('allow_manual_entries'))
        account.save()
        messages.success(request, 'Compte mis à jour.')
        return redirect('accounting:account_list')
    return render(request, 'accounting/account_form.html', {
        'account': account, 'type_choices': Account.TYPE_CHOICES,
    })


# ─── JOURNAUX ─────────────────────────────────────────────────────────────────

@login_required
def journal_list(request):
    company = _company(request)
    journals = Journal.objects.filter(company=company)
    return render(request, 'accounting/journal_list.html', {'journals': journals})


@login_required
def journal_create(request):
    company = _company(request)
    if request.method == 'POST':
        j = Journal.objects.create(
            company=company,
            code=request.POST.get('code', '').upper(),
            name=request.POST.get('name', ''),
            journal_type=request.POST.get('journal_type', 'misc'),
        )
        messages.success(request, f'Journal {j.code} créé.')
        return redirect('accounting:journal_list')
    return render(request, 'accounting/journal_form.html', {'type_choices': Journal.TYPE_CHOICES})


# ─── ÉCRITURES ────────────────────────────────────────────────────────────────

@login_required
def entry_list(request):
    company = _company(request)
    status_filter = request.GET.get('status', '')
    journal_filter = request.GET.get('journal', '')
    entries = JournalEntry.objects.filter(company=company).select_related('journal')
    if status_filter:
        entries = entries.filter(status=status_filter)
    if journal_filter:
        entries = entries.filter(journal_id=journal_filter)
    journals = Journal.objects.filter(company=company, is_active=True)
    return render(request, 'accounting/entry_list.html', {
        'entries': entries, 'journals': journals,
        'status_filter': status_filter, 'journal_filter': journal_filter,
        'page_title': 'Écritures comptables', 'active_module': 'accounting',
    })


@login_required
def entry_create(request):
    company = _company(request)
    journals = Journal.objects.filter(company=company, is_active=True)
    accounts = Account.objects.filter(company=company, is_active=True, allow_manual_entries=True)
    if request.method == 'POST':
        journal_id = request.POST.get('journal')
        journal = get_object_or_404(Journal, pk=journal_id, company=company)
        entry = JournalEntry.objects.create(
            company=company, journal=journal,
            entry_date=request.POST.get('entry_date'),
            description=request.POST.get('description', ''),
            reference=request.POST.get('reference', ''),
            source_type='manual', created_by=request.user,
            entry_number=_auto_entry_number(company, journal),
        )
        account_ids = request.POST.getlist('account_id[]')
        debits = request.POST.getlist('debit[]')
        credits = request.POST.getlist('credit[]')
        labels = request.POST.getlist('label[]')
        for i, acc_id in enumerate(account_ids):
            if not acc_id:
                continue
            try:
                acc = Account.objects.get(pk=acc_id, company=company)
                JournalEntryLine.objects.create(
                    entry=entry, account=acc,
                    label=labels[i] if i < len(labels) else '',
                    debit=Decimal(debits[i]) if i < len(debits) and debits[i] else 0,
                    credit=Decimal(credits[i]) if i < len(credits) and credits[i] else 0,
                )
            except Exception:
                pass
        messages.success(request, f'Écriture {entry.entry_number} créée.')
        return redirect('accounting:entry_detail', pk=entry.pk)
    return render(request, 'accounting/entry_form.html', {'journals': journals, 'accounts': accounts})


@login_required
def entry_detail(request, pk):
    company = _company(request)
    entry = get_object_or_404(JournalEntry, pk=pk, company=company)
    lines = entry.lines.select_related('account')
    return render(request, 'accounting/entry_detail.html', {
        'entry': entry, 'lines': lines,
        'total_debit': entry.total_debit,
        'total_credit': entry.total_credit,
        'is_balanced': entry.is_balanced,
    })


@login_required
def entry_validate(request, pk):
    company = _company(request)
    entry = get_object_or_404(JournalEntry, pk=pk, company=company)
    if request.method == 'POST':
        try:
            entry.validate(request.user)
            messages.success(request, 'L\'écriture a été validée.')
        except Exception as e:
            messages.error(request, str(e))
    return redirect('accounting:entry_detail', pk=pk)


@login_required
def entry_reverse(request, pk):
    company = _company(request)
    entry = get_object_or_404(JournalEntry, pk=pk, company=company)
    if request.method == 'POST':
        try:
            rev = entry.reverse(request.user)
            messages.success(request, f'Extourne créée : {rev.entry_number}')
            return redirect('accounting:entry_detail', pk=rev.pk)
        except Exception as e:
            messages.error(request, str(e))
    return redirect('accounting:entry_detail', pk=pk)


@login_required
def entry_cancel(request, pk):
    company = _company(request)
    entry = get_object_or_404(JournalEntry, pk=pk, company=company)
    if request.method == 'POST':
        if entry.status == 'draft':
            entry.status = 'cancelled'
            entry.save()
            messages.success(request, 'Écriture annulée.')
        else:
            messages.error(request, 'Impossible d\'annuler une écriture validée. Utilisez l\'extourne.')
    return redirect('accounting:entry_detail', pk=pk)


# ─── TVA ──────────────────────────────────────────────────────────────────────

@login_required
def tva_dashboard(request):
    company = _company(request)
    period_start = request.GET.get('start', '')
    period_end = request.GET.get('end', '')
    collected = Decimal('0')
    deductible = Decimal('0')
    if period_start and period_end:
        lines = JournalEntryLine.objects.filter(
            entry__company=company, entry__status='validated',
            account__account_type='tax',
            entry__entry_date__gte=period_start, entry__entry_date__lte=period_end,
        )
        for line in lines:
            collected += line.credit
            deductible += line.debit
    solde = collected - deductible
    return render(request, 'accounting/tva.html', {
        'collected': collected, 'deductible': deductible, 'solde': solde,
        'period_start': period_start, 'period_end': period_end,
        'tax_rates': TaxRate.objects.filter(company=company, is_active=True),
    })


# ─── PAIEMENTS ────────────────────────────────────────────────────────────────

@login_required
def payment_list(request):
    company = _company(request)
    payments = Payment.objects.filter(company=company).order_by('-payment_date')
    type_filter = request.GET.get('type', '')
    if type_filter:
        payments = payments.filter(payment_type=type_filter)
    return render(request, 'accounting/payment_list.html', {
        'payments': payments, 'type_choices': Payment.TYPE_CHOICES, 'type_filter': type_filter,
    })


@login_required
def payment_create(request):
    company = _company(request)
    if request.method == 'POST':
        p = Payment.objects.create(
            company=company,
            payment_type=request.POST.get('payment_type'),
            partner_name=request.POST.get('partner_name', ''),
            amount=request.POST.get('amount', 0),
            payment_date=request.POST.get('payment_date'),
            payment_method=request.POST.get('payment_method', 'bank_transfer'),
            reference=request.POST.get('reference', ''),
            created_by=request.user,
        )
        messages.success(request, f'Paiement créé.')
        return redirect('accounting:payment_list')
    bank_accounts = BankAccount.objects.filter(company=company, is_active=True)
    return render(request, 'accounting/payment_form.html', {
        'type_choices': Payment.TYPE_CHOICES,
        'method_choices': Payment.METHOD_CHOICES,
        'bank_accounts': bank_accounts,
    })


# ─── RAPPROCHEMENT BANCAIRE ───────────────────────────────────────────────────

@login_required
def bank_account_list(request):
    company = _company(request)
    accounts = BankAccount.objects.filter(company=company)
    if request.method == 'POST':
        BankAccount.objects.create(
            company=company,
            bank_name=request.POST.get('bank_name', ''),
            account_name=request.POST.get('account_name', ''),
            iban=request.POST.get('iban', ''),
            bic=request.POST.get('bic', ''),
            opening_balance=request.POST.get('opening_balance', 0) or 0,
        )
        messages.success(request, 'Compte bancaire ajouté.')
        return redirect('accounting:bank_account_list')
    return render(request, 'accounting/bank_account_list.html', {'accounts': accounts})


@login_required
def bank_statement_list(request):
    company = _company(request)
    statements = BankStatement.objects.filter(company=company).order_by('-statement_date')
    bank_accounts = BankAccount.objects.filter(company=company, is_active=True)
    if request.method == 'POST':
        bank_acct = get_object_or_404(BankAccount, pk=request.POST.get('bank_account'), company=company)
        stmt = BankStatement.objects.create(
            company=company, bank_account=bank_acct,
            statement_date=request.POST.get('statement_date'),
            start_balance=request.POST.get('start_balance', 0) or 0,
            end_balance=request.POST.get('end_balance', 0) or 0,
        )
        if 'import_file' in request.FILES:
            stmt.import_file = request.FILES['import_file']
            stmt.save()
        messages.success(request, f'Relevé importé.')
        return redirect('accounting:bank_statement_list')
    return render(request, 'accounting/bank_statement_list.html', {
        'statements': statements, 'bank_accounts': bank_accounts,
    })


@login_required
def bank_reconciliation(request, statement_pk):
    company = _company(request)
    statement = get_object_or_404(BankStatement, pk=statement_pk, company=company)
    lines = statement.lines.all().order_by('operation_date')
    unreconciled_payments = Payment.objects.filter(company=company, status='validated')
    if request.method == 'POST':
        line_pk = request.POST.get('line_pk')
        payment_pk = request.POST.get('payment_pk')
        action = request.POST.get('action', 'reconcile')
        if action == 'reconcile' and line_pk and payment_pk:
            try:
                line = BankStatementLine.objects.get(pk=line_pk, statement=statement)
                payment = Payment.objects.get(pk=payment_pk, company=company)
                Reconciliation.objects.create(
                    company=company, bank_statement_line=line,
                    payment=payment, amount=payment.amount, reconciled_by=request.user,
                )
                line.is_reconciled = True
                line.matched_payment = payment
                line.save()
                payment.status = 'reconciled'
                payment.save()
                messages.success(request, 'Rapprochement effectué.')
            except Exception as e:
                messages.error(request, str(e))
        elif action == 'ignore' and line_pk:
            BankStatementLine.objects.filter(pk=line_pk).update(is_reconciled=True)
        return redirect('accounting:bank_reconciliation', statement_pk=statement_pk)
    return render(request, 'accounting/bank_reconciliation.html', {
        'statement': statement, 'lines': lines,
        'unreconciled_payments': unreconciled_payments,
        'reconciled_count': lines.filter(is_reconciled=True).count(),
        'total_count': lines.count(),
    })


# ─── NOTES DE FRAIS ───────────────────────────────────────────────────────────

@login_required
def expense_report_list(request):
    company = _company(request)
    status_filter = request.GET.get('status', '')
    reports = ExpenseReport.objects.filter(company=company).select_related('employee')
    if status_filter:
        reports = reports.filter(status=status_filter)
    return render(request, 'accounting/expense_report_list.html', {
        'reports': reports, 'status_choices': ExpenseReport.STATUS_CHOICES, 'status_filter': status_filter,
    })


@login_required
def expense_report_detail(request, pk):
    company = _company(request)
    report = get_object_or_404(ExpenseReport, pk=pk, company=company)
    lines = report.lines.all().select_related('tax_rate', 'account')
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'validate' and report.status == 'submitted':
            report.status = 'validated'
            report.validated_by = request.user
            report.validated_at = timezone.now()
            report.save()
            messages.success(request, 'Note de frais validée.')
        elif action == 'refuse':
            report.status = 'refused'
            report.refused_reason = request.POST.get('reason', '')
            report.save()
            messages.warning(request, 'Note de frais refusée.')
        elif action == 'mark_paid' and report.status == 'validated':
            report.status = 'paid'
            report.paid_at = timezone.now().date()
            report.save()
            messages.success(request, 'Note de frais marquée remboursée.')
        return redirect('accounting:expense_report_detail', pk=pk)
    return render(request, 'accounting/expense_report_detail.html', {'report': report, 'lines': lines})


# ─── IMMOBILISATIONS ──────────────────────────────────────────────────────────

@login_required
def fixed_asset_list(request):
    company = _company(request)
    assets = FixedAsset.objects.filter(company=company)
    return render(request, 'accounting/fixed_asset_list.html', {'assets': assets})


@login_required
def fixed_asset_detail(request, pk):
    company = _company(request)
    asset = get_object_or_404(FixedAsset, pk=pk, company=company)
    lines = asset.depreciation_lines.all().order_by('depreciation_date')
    return render(request, 'accounting/fixed_asset_detail.html', {'asset': asset, 'lines': lines})


# ─── EXERCICES COMPTABLES ─────────────────────────────────────────────────────

@login_required
def fiscal_year_list(request):
    company = _company(request)
    fiscal_years = FiscalYear.objects.filter(company=company)
    if request.method == 'POST':
        FiscalYear.objects.create(
            company=company,
            name=request.POST.get('name', ''),
            start_date=request.POST.get('start_date'),
            end_date=request.POST.get('end_date'),
        )
        messages.success(request, 'Exercice créé.')
        return redirect('accounting:fiscal_year_list')
    return render(request, 'accounting/fiscal_year_list.html', {'fiscal_years': fiscal_years})


@login_required
def period_list(request, year_pk):
    company = _company(request)
    fiscal_year = get_object_or_404(FiscalYear, pk=year_pk, company=company)
    periods = fiscal_year.periods.all()
    if request.method == 'POST':
        pk = request.POST.get('period_pk')
        new_status = request.POST.get('status')
        if pk and new_status:
            period = get_object_or_404(AccountingPeriod, pk=pk, fiscal_year=fiscal_year)
            period.status = new_status
            period.save()
            messages.success(request, f'Période {period.name} mise à jour.')
        return redirect('accounting:period_list', year_pk=year_pk)
    return render(request, 'accounting/period_list.html', {'fiscal_year': fiscal_year, 'periods': periods})


# ─── RAPPORTS ────────────────────────────────────────────────────────────────

@login_required
def report_balance(request):
    company = _company(request)
    period_start = request.GET.get('start', '')
    period_end = request.GET.get('end', '')
    accounts_data = []
    if period_start and period_end:
        for acc in Account.objects.filter(company=company, is_active=True).order_by('number'):
            lines = JournalEntryLine.objects.filter(
                account=acc, entry__status='validated',
                entry__entry_date__gte=period_start, entry__entry_date__lte=period_end,
            )
            total_debit = lines.aggregate(s=Sum('debit'))['s'] or Decimal('0')
            total_credit = lines.aggregate(s=Sum('credit'))['s'] or Decimal('0')
            if total_debit or total_credit:
                balance = total_debit - total_credit
                accounts_data.append({
                    'account': acc,
                    'total_debit': total_debit,
                    'total_credit': total_credit,
                    'solde_debiteur': balance if balance > 0 else Decimal('0'),
                    'solde_crediteur': abs(balance) if balance < 0 else Decimal('0'),
                })
    return render(request, 'accounting/report_balance.html', {
        'accounts_data': accounts_data,
        'period_start': period_start, 'period_end': period_end,
    })


@login_required
def report_grand_livre(request):
    company = _company(request)
    account_filter = request.GET.get('account', '')
    period_start = request.GET.get('start', '')
    period_end = request.GET.get('end', '')
    lines = JournalEntryLine.objects.filter(
        entry__company=company, entry__status='validated'
    ).select_related('account', 'entry', 'entry__journal')
    if account_filter:
        lines = lines.filter(account_id=account_filter)
    if period_start:
        lines = lines.filter(entry__entry_date__gte=period_start)
    if period_end:
        lines = lines.filter(entry__entry_date__lte=period_end)
    lines = lines.order_by('account__number', 'entry__entry_date')
    accounts = Account.objects.filter(company=company, is_active=True).order_by('number')
    return render(request, 'accounting/report_grand_livre.html', {
        'lines': lines, 'accounts': accounts,
        'account_filter': account_filter,
        'period_start': period_start, 'period_end': period_end,
    })


@login_required
def report_income_statement(request):
    company = _company(request)
    period_start = request.GET.get('start', '')
    period_end = request.GET.get('end', '')
    revenues = Decimal('0')
    expenses = Decimal('0')
    if period_start and period_end:
        rev_lines = JournalEntryLine.objects.filter(
            entry__company=company, entry__status='validated',
            account__account_type='revenue',
            entry__entry_date__gte=period_start, entry__entry_date__lte=period_end,
        )
        revenues = sum((l.credit - l.debit for l in rev_lines), Decimal('0'))
        exp_lines = JournalEntryLine.objects.filter(
            entry__company=company, entry__status='validated',
            account__account_type='expense',
            entry__entry_date__gte=period_start, entry__entry_date__lte=period_end,
        )
        expenses = sum((l.debit - l.credit for l in exp_lines), Decimal('0'))
    return render(request, 'accounting/report_income_statement.html', {
        'revenues': revenues, 'expenses': expenses, 'result': revenues - expenses,
        'period_start': period_start, 'period_end': period_end,
    })


def index(request):
    return redirect('accounting:dashboard')
