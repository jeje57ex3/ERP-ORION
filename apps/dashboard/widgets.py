"""
dashboard/widgets.py — Chargeurs de données pour chaque widget
Chaque fonction retourne un dict utilisable dans les templates.
"""
from datetime import date, timedelta


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default if default is not None else {}


# ─── Raccourcis ─────────────────────────────────────────────────────────────

def get_favorite_shortcuts_data(user, company):
    from .models import DashboardShortcut
    shortcuts = DashboardShortcut.objects.filter(
        user=user, company=company, is_active=True, is_favorite=True
    ).order_by('order')[:12]
    return {'shortcuts': list(shortcuts)}


# ─── Demandes ───────────────────────────────────────────────────────────────

def get_my_requests_data(user, company):
    from .models import DashboardRequestBox
    requests = DashboardRequestBox.objects.filter(
        user=user, company=company
    ).exclude(status__in=['done', 'archived']).order_by('-created_at')[:10]
    return {
        'requests': list(requests),
        'total': DashboardRequestBox.objects.filter(user=user, company=company).exclude(status__in=['done', 'archived']).count(),
        'urgent': DashboardRequestBox.objects.filter(user=user, company=company, priority='urgent').exclude(status__in=['done', 'archived']).count(),
    }


# ─── Tâches ─────────────────────────────────────────────────────────────────

def get_my_tasks_data(user, company):
    return {'tasks': [], 'total': 0}


# ─── Validations ────────────────────────────────────────────────────────────

def get_my_validations_data(user, company):
    validations = []
    today = date.today()

    def add_quotes():
        from apps.sales.models import Quote
        for q in Quote.objects.filter(company=company, status='sent').order_by('-created_at')[:5]:
            validations.append({
                'type': 'Devis', 'label': str(q), 'date': q.created_at,
                'badge': 'bg-info', 'url': f'/sales/quotes/{q.pk}/'
            })
    _safe(add_quotes)

    def add_leaves():
        from apps.hr.models import LeaveRequest
        for lr in LeaveRequest.objects.filter(company=company, status='pending').order_by('-created_at')[:5]:
            validations.append({
                'type': 'Congé', 'label': str(lr), 'date': lr.created_at,
                'badge': 'bg-warning text-dark', 'url': f'/hr/leaves/{lr.pk}/'
            })
    _safe(add_leaves)

    def add_expenses():
        from apps.hr.models import ExpenseReport
        for er in ExpenseReport.objects.filter(company=company, status='submitted').order_by('-created_at')[:5]:
            validations.append({
                'type': 'Note de frais', 'label': str(er), 'date': er.created_at,
                'badge': 'bg-warning text-dark', 'url': f'/hr/expenses/{er.pk}/'
            })
    _safe(add_expenses)

    validations.sort(key=lambda x: x['date'], reverse=True)
    return {'validations': validations[:10], 'total': len(validations)}


# ─── Notifications ──────────────────────────────────────────────────────────

def get_my_notifications_data(user, company):
    def load():
        from apps.core.models import Notification
        notifs = Notification.objects.filter(
            user=user, is_read=False
        ).select_related('company').order_by('-created_at')[:10]
        return {'notifications': list(notifs), 'unread_count': notifs.count()}
    return _safe(load, {'notifications': [], 'unread_count': 0})


# ─── Messages ───────────────────────────────────────────────────────────────

def get_my_messages_data(user, company):
    return {'messages': [], 'unread_count': 0}


# ─── Documents récents ──────────────────────────────────────────────────────

def get_recent_documents_data(user, company):
    def load():
        from apps.documents.models import Document
        docs = Document.objects.filter(company=company).order_by('-created_at')[:8]
        return {'documents': list(docs)}
    return _safe(load, {'documents': []})


# ─── Calendrier ─────────────────────────────────────────────────────────────

def get_calendar_events_data(user, company):
    today = date.today()
    end = today + timedelta(days=14)
    events = []

    def add_leaves():
        from apps.hr.models import LeaveRequest
        for lr in LeaveRequest.objects.filter(
            company=company, status='approved',
            start_date__gte=today, start_date__lte=end
        )[:5]:
            events.append({
                'label': f'Congé — {lr.employee}',
                'date': lr.start_date,
                'type': 'leave', 'badge': 'bg-info',
            })
    _safe(add_leaves)

    def add_btp():
        from apps.btp.models import BTPProject
        for p in BTPProject.objects.filter(
            company=company, status='in_progress',
            end_date__gte=today, end_date__lte=end
        )[:5]:
            events.append({
                'label': f'Fin chantier — {p.name}',
                'date': p.end_date,
                'type': 'project', 'badge': 'bg-warning text-dark',
            })
    _safe(add_btp)

    events.sort(key=lambda x: x['date'])
    return {'events': events[:10], 'today': today, 'end': end}


# ─── BTP ────────────────────────────────────────────────────────────────────

def get_btp_active_projects_data(user, company):
    def load():
        from apps.btp.models import BTPProject
        projects = BTPProject.objects.filter(
            company=company, status='in_progress', is_active=True
        ).select_related('customer', 'project_manager').order_by('-updated_at')[:8]
        return {'projects': list(projects)}
    return _safe(load, {'projects': []})


def get_btp_my_projects_data(user, company):
    def load():
        from apps.btp.models import BTPProject
        projects = BTPProject.objects.filter(
            company=company, project_manager=user,
            status__in=['in_progress', 'won'], is_active=True
        ).select_related('customer').order_by('-updated_at')[:8]
        return {'projects': list(projects)}
    return _safe(load, {'projects': []})


def get_btp_hours_to_validate_data(user, company):
    def load():
        from apps.btp.models import Timesheet
        ts = Timesheet.objects.filter(
            company=company, status='submitted'
        ).select_related('employee', 'project').order_by('-date')[:10]
        return {'timesheets': list(ts), 'total': ts.count()}
    return _safe(load, {'timesheets': [], 'total': 0})


def get_btp_open_reservations_data(user, company):
    def load():
        from apps.portals.models import ProjectReservation
        rsvs = ProjectReservation.objects.filter(
            project__company=company, status__in=['open', 'in_progress']
        ).select_related('project').order_by('-created_at')[:8]
        return {'reservations': list(rsvs), 'total': rsvs.count()}
    return _safe(load, {'reservations': [], 'total': 0})


def get_btp_pending_change_requests_data(user, company):
    def load():
        from apps.portals.models import ProjectChangeRequest
        changes = ProjectChangeRequest.objects.filter(
            project__company=company, status__in=['pending', 'review']
        ).select_related('project').order_by('-created_at')[:8]
        return {'changes': list(changes), 'total': changes.count()}
    return _safe(load, {'changes': [], 'total': 0})


def get_btp_guided_quote_requests_data(user, company):
    def load():
        from apps.btp.models import GuidedQuoteRequest
        reqs = GuidedQuoteRequest.objects.filter(
            company=company, status__in=['new', 'in_progress']
        ).order_by('-created_at')[:8]
        return {'quote_requests': list(reqs), 'total': reqs.count()}
    return _safe(load, {'quote_requests': [], 'total': 0})


# ─── CRM ────────────────────────────────────────────────────────────────────

def get_crm_followups_data(user, company):
    def load():
        from apps.crm.models import Prospect
        today = date.today()
        prospects = Prospect.objects.filter(
            company=company,
            status__in=['new', 'contacted', 'qualified'],
            is_active=True,
            next_action_date__lte=today + timedelta(days=7),
        ).order_by('next_action_date')[:8]
        return {'prospects': list(prospects), 'total': prospects.count()}
    return _safe(load, {'prospects': [], 'total': 0})


def get_crm_opportunities_data(user, company):
    def load():
        from apps.crm.models import Opportunity
        opps = Opportunity.objects.filter(
            company=company,
            status__in=['new', 'qualified', 'proposal', 'negotiation']
        ).select_related('customer').order_by('-estimated_value')[:8]
        total = sum(o.estimated_value or 0 for o in opps)
        return {'opportunities': list(opps), 'total_value': total}
    return _safe(load, {'opportunities': [], 'total_value': 0})


# ─── Ventes ─────────────────────────────────────────────────────────────────

def get_sales_quotes_to_send_data(user, company):
    def load():
        from apps.sales.models import Quote
        quotes = Quote.objects.filter(
            company=company, status='draft'
        ).select_related('customer').order_by('-created_at')[:8]
        return {'quotes': list(quotes), 'total': quotes.count()}
    return _safe(load, {'quotes': [], 'total': 0})


def get_sales_quotes_waiting_data(user, company):
    def load():
        from apps.sales.models import Quote
        quotes = Quote.objects.filter(
            company=company, status='sent'
        ).select_related('customer').order_by('-issue_date')[:8]
        return {'quotes': list(quotes), 'total': quotes.count()}
    return _safe(load, {'quotes': [], 'total': 0})


def get_sales_unpaid_invoices_data(user, company):
    def load():
        from apps.sales.models import Invoice
        invoices = Invoice.objects.filter(
            company=company, status='sent'
        ).select_related('customer').order_by('due_date')[:8]
        total = sum(inv.total_ttc or 0 for inv in invoices)
        return {'invoices': list(invoices), 'total_amount': total, 'count': invoices.count()}
    return _safe(load, {'invoices': [], 'total_amount': 0, 'count': 0})


# ─── Comptabilité ────────────────────────────────────────────────────────────

def get_accounting_cash_balance_data(user, company):
    def load():
        from apps.accounting.models import BankAccount
        accounts = BankAccount.objects.filter(company=company, is_active=True)
        total = sum(a.current_balance or 0 for a in accounts)
        return {'accounts': list(accounts), 'total_balance': total}
    return _safe(load, {'accounts': [], 'total_balance': 0})


def get_accounting_overdue_invoices_data(user, company):
    def load():
        from apps.sales.models import Invoice
        today = date.today()
        invoices = Invoice.objects.filter(
            company=company, status='sent', due_date__lt=today
        ).select_related('customer').order_by('due_date')[:8]
        total = sum(inv.total_ttc or 0 for inv in invoices)
        return {'invoices': list(invoices), 'total_amount': total, 'count': invoices.count()}
    return _safe(load, {'invoices': [], 'total_amount': 0, 'count': 0})


def get_accounting_supplier_due_data(user, company):
    def load():
        from apps.purchases.models import SupplierInvoice
        today = date.today()
        invoices = SupplierInvoice.objects.filter(
            company=company, status='received', due_date__lte=today + timedelta(days=30)
        ).select_related('supplier').order_by('due_date')[:8]
        total = sum(inv.total_ttc or 0 for inv in invoices)
        return {'invoices': list(invoices), 'total_amount': total, 'count': invoices.count()}
    return _safe(load, {'invoices': [], 'total_amount': 0, 'count': 0})


def get_accounting_vat_data(user, company):
    return {'vat_collected': 0, 'vat_deductible': 0, 'vat_due': 0}


def get_accounting_draft_entries_data(user, company):
    def load():
        from apps.accounting.models import JournalEntry
        entries = JournalEntry.objects.filter(
            company=company, status='draft'
        ).select_related('journal').order_by('-entry_date')[:10]
        return {'entries': list(entries), 'count': entries.count()}
    return _safe(load, {'entries': [], 'count': 0})


# ─── RH ─────────────────────────────────────────────────────────────────────

def get_hr_leave_requests_data(user, company):
    def load():
        from apps.hr.models import LeaveRequest
        leaves = LeaveRequest.objects.filter(
            company=company, status='pending'
        ).select_related('employee').order_by('-created_at')[:8]
        return {'leaves': list(leaves), 'total': leaves.count()}
    return _safe(load, {'leaves': [], 'total': 0})


def get_hr_expenses_data(user, company):
    def load():
        from apps.hr.models import ExpenseReport
        expenses = ExpenseReport.objects.filter(
            company=company, status='submitted'
        ).select_related('employee').order_by('-created_at')[:8]
        return {'expenses': list(expenses), 'total': expenses.count()}
    return _safe(load, {'expenses': [], 'total': 0})


def get_hr_expiring_documents_data(user, company):
    def load():
        from apps.hr.models import EmployeePrivateDocument
        threshold = date.today() + timedelta(days=30)
        docs = EmployeePrivateDocument.objects.filter(
            company=company,
            expires_at__lte=threshold,
            expires_at__gte=date.today()
        ).select_related('employee').order_by('expires_at')[:10]
        return {'documents': list(docs), 'total': docs.count()}
    return _safe(load, {'documents': [], 'total': 0})


def get_hr_my_private_documents_data(user, company):
    def load():
        from apps.hr.models import Employee, EmployeePrivateDocument
        try:
            employee = Employee.objects.get(company=company, user=user)
        except Employee.DoesNotExist:
            return {'documents': []}
        docs = EmployeePrivateDocument.objects.filter(
            company=company, employee=employee, visible_to_employee=True
        ).order_by('-created_at')[:8]
        return {'documents': list(docs)}
    return _safe(load, {'documents': []})


# ─── E-commerce ─────────────────────────────────────────────────────────────

def get_ecommerce_orders_data(user, company):
    def load():
        from apps.ecommerce.models import Order
        orders = Order.objects.filter(
            company=company, status__in=['confirmed', 'processing']
        ).order_by('-created_at')[:8]
        return {'orders': list(orders), 'count': orders.count()}
    return _safe(load, {'orders': [], 'count': 0})


def get_inventory_low_stock_data(user, company):
    def load():
        from apps.inventory.models import Product
        products = Product.objects.filter(
            company=company, is_active=True
        ).order_by('stock_quantity')[:10]
        return {'products': list(products), 'count': products.count()}
    return _safe(load, {'products': [], 'count': 0})


def get_ecommerce_returns_data(user, company):
    def load():
        from apps.ecommerce.models import Return
        returns = Return.objects.filter(
            company=company, status='pending'
        ).order_by('-created_at')[:8]
        return {'returns': list(returns), 'count': returns.count()}
    return _safe(load, {'returns': [], 'count': 0})


def get_commerce_daily_sales_data(user, company):
    return {'today_revenue': 0, 'transactions': 0, 'average': 0}


def get_commerce_click_collect_data(user, company):
    return {'orders': [], 'count': 0}


# ═══════════════════════════════════════════════════════════════════════════════
# NOUVEAUX WIDGETS — Phase 2
# ═══════════════════════════════════════════════════════════════════════════════

# ─── Productivité personnelle ────────────────────────────────────────────────

def get_quick_actions_data(user, company):
    actions = [
        {'label': 'Nouveau client', 'icon': 'bi-person-plus', 'url': '/crm/clients/nouveau/', 'color': '#10B981'},
        {'label': 'Nouveau devis', 'icon': 'bi-file-earmark-plus', 'url': '/sales/quotes/create/', 'color': '#2563EB'},
        {'label': 'Nouvelle facture', 'icon': 'bi-receipt', 'url': '/sales/invoices/create/', 'color': '#7C3AED'},
        {'label': 'Saisir heures', 'icon': 'bi-clock', 'url': '/btp/timesheets/nouveau/', 'color': '#D97706'},
        {'label': 'Créer ticket', 'icon': 'bi-headset', 'url': '/support/tickets/nouveau/', 'color': '#DC2626'},
        {'label': 'Ajouter document', 'icon': 'bi-folder-plus', 'url': '/documents/', 'color': '#0891B2'},
        {'label': 'Nouveau chantier', 'icon': 'bi-building-gear', 'url': '/btp/projects/create/', 'color': '#C6A15B'},
        {'label': 'Voir planning', 'icon': 'bi-calendar3', 'url': '/btp/planning/', 'color': '#6B7280'},
    ]
    return {'actions': actions}


def get_user_favorites_data(user, company):
    from .models import DashboardShortcut
    favorites = DashboardShortcut.objects.filter(
        user=user, company=company, is_active=True, is_favorite=True
    ).order_by('order')[:12]
    return {'favorites': list(favorites), 'count': favorites.count()}


def get_today_todo_data(user, company):
    items = []
    today = date.today()

    def add_validations():
        from apps.hr.models import LeaveRequest
        for lr in LeaveRequest.objects.filter(company=company, status='pending').order_by('-created_at')[:3]:
            items.append({'type': 'Congé à valider', 'label': str(lr), 'priority': 'high', 'url': f'/hr/leaves/{lr.pk}/', 'icon': 'bi-calendar-check', 'color': 'warning'})
    _safe(add_validations)

    def add_quotes():
        from apps.sales.models import Quote
        for q in Quote.objects.filter(company=company, status='draft').order_by('-created_at')[:3]:
            items.append({'type': 'Devis à envoyer', 'label': str(q), 'priority': 'normal', 'url': f'/sales/quotes/{q.pk}/', 'icon': 'bi-file-earmark-arrow-up', 'color': 'info'})
    _safe(add_quotes)

    def add_invoices():
        from apps.sales.models import Invoice
        for inv in Invoice.objects.filter(company=company, status='sent', due_date__lte=today).order_by('due_date')[:3]:
            items.append({'type': 'Facture en retard', 'label': str(inv), 'priority': 'urgent', 'url': f'/sales/invoices/{inv.pk}/', 'icon': 'bi-exclamation-octagon', 'color': 'danger'})
    _safe(add_invoices)

    return {'items': items[:10], 'count': len(items), 'has_data': bool(items)}


def get_weekly_agenda_data(user, company):
    events = []
    today = date.today()
    end = today + timedelta(days=7)

    def add_projects():
        from apps.btp.models import BTPProject
        for p in BTPProject.objects.filter(company=company, status='in_progress', end_date__range=(today, end)).order_by('end_date')[:5]:
            events.append({'label': f'Fin — {p.name}', 'date': p.end_date, 'icon': 'bi-building-gear', 'color': '#D97706', 'type': 'project'})
    _safe(add_projects)

    def add_invoices():
        from apps.sales.models import Invoice
        for inv in Invoice.objects.filter(company=company, status='sent', due_date__range=(today, end)).order_by('due_date')[:5]:
            events.append({'label': f'Échéance — {inv}', 'date': inv.due_date, 'icon': 'bi-receipt', 'color': '#DC2626', 'type': 'invoice'})
    _safe(add_invoices)

    def add_leaves():
        from apps.hr.models import LeaveRequest
        for lr in LeaveRequest.objects.filter(company=company, status='approved', start_date__range=(today, end)).order_by('start_date')[:5]:
            events.append({'label': f'Congé — {lr.employee}', 'date': lr.start_date, 'icon': 'bi-person-check', 'color': '#10B981', 'type': 'leave'})
    _safe(add_leaves)

    events.sort(key=lambda x: x['date'])
    return {'events': events[:12], 'today': today, 'end': end, 'has_data': bool(events)}


def get_personal_notes_data(user, company):
    def load():
        from .models import DashboardPersonalNote
        notes = DashboardPersonalNote.objects.filter(user=user, company=company).order_by('-is_pinned', '-updated_at')[:6]
        return {'notes': list(notes), 'count': notes.count(), 'has_data': notes.exists()}
    return _safe(load, {'notes': [], 'count': 0, 'has_data': False})


# ─── Alertes et priorités ────────────────────────────────────────────────────

def get_important_alerts_data(user, company):
    alerts = []
    today = date.today()

    def check_overdue_invoices():
        from apps.sales.models import Invoice
        count = Invoice.objects.filter(company=company, status='sent', due_date__lt=today).count()
        if count:
            alerts.append({'level': 'danger', 'icon': 'bi-exclamation-octagon', 'label': f'{count} facture(s) client en retard', 'url': '/sales/invoices/?status=overdue', 'action': 'Voir'})
    _safe(check_overdue_invoices)

    def check_low_stock():
        from apps.inventory.models import Product
        count = Product.objects.filter(company=company, is_active=True, stock_quantity__lte=5).count()
        if count:
            alerts.append({'level': 'warning', 'icon': 'bi-box-seam', 'label': f'{count} produit(s) en stock critique', 'url': '/inventory/products/', 'action': 'Voir'})
    _safe(check_low_stock)

    def check_expiring_docs():
        from apps.hr.models import EmployeePrivateDocument
        threshold = today + timedelta(days=30)
        count = EmployeePrivateDocument.objects.filter(company=company, expires_at__lte=threshold, expires_at__gte=today).count()
        if count:
            alerts.append({'level': 'warning', 'icon': 'bi-file-earmark-exclamation', 'label': f'{count} document(s) expirant dans 30 jours', 'url': '/hr/employees/', 'action': 'Voir'})
    _safe(check_expiring_docs)

    def check_supplier_due():
        from apps.purchases.models import SupplierInvoice
        count = SupplierInvoice.objects.filter(company=company, status__in=['pending', 'approved'], due_date__lt=today).count()
        if count:
            alerts.append({'level': 'danger', 'icon': 'bi-shop', 'label': f'{count} facture(s) fournisseur en retard', 'url': '/purchases/factures/', 'action': 'Payer'})
    _safe(check_supplier_due)

    return {'alerts': alerts, 'count': len(alerts), 'has_data': bool(alerts)}


def get_upcoming_deadlines_data(user, company):
    items = []
    today = date.today()
    soon = today + timedelta(days=14)

    def check_quotes():
        from apps.sales.models import Quote
        for q in Quote.objects.filter(company=company, status='sent', expiry_date__lte=soon, expiry_date__gte=today).order_by('expiry_date')[:5]:
            items.append({'type': 'Devis expirant', 'label': str(q), 'date': q.expiry_date, 'url': f'/sales/quotes/{q.pk}/', 'color': 'warning', 'icon': 'bi-file-earmark-text'})
    _safe(check_quotes)

    def check_invoices():
        from apps.sales.models import Invoice
        for inv in Invoice.objects.filter(company=company, status='sent', due_date__lte=soon, due_date__gte=today).order_by('due_date')[:5]:
            items.append({'type': 'Facture à encaisser', 'label': str(inv), 'date': inv.due_date, 'url': f'/sales/invoices/{inv.pk}/', 'color': 'danger', 'icon': 'bi-receipt'})
    _safe(check_invoices)

    items.sort(key=lambda x: x['date'])
    return {'items': items[:10], 'count': len(items), 'has_data': bool(items)}


def get_late_items_data(user, company):
    items = []
    today = date.today()

    def check_projects():
        from apps.btp.models import BTPProject
        for p in BTPProject.objects.filter(company=company, status='in_progress', end_date__lt=today).order_by('end_date')[:5]:
            items.append({'type': 'Chantier en retard', 'label': p.name, 'date': p.end_date, 'url': f'/btp/projects/{p.pk}/', 'color': 'danger', 'icon': 'bi-building-exclamation'})
    _safe(check_projects)

    def check_invoices():
        from apps.sales.models import Invoice
        for inv in Invoice.objects.filter(company=company, status='sent', due_date__lt=today).order_by('due_date')[:5]:
            items.append({'type': 'Facture impayée', 'label': str(inv), 'date': inv.due_date, 'url': f'/sales/invoices/{inv.pk}/', 'color': 'danger', 'icon': 'bi-exclamation-octagon'})
    _safe(check_invoices)

    def check_tickets():
        from apps.support.models import SupportTicket
        for t in SupportTicket.objects.filter(company=company, status__in=['open', 'pending'], created_at__date__lt=today - timedelta(days=7)).order_by('created_at')[:5]:
            items.append({'type': 'Ticket non traité', 'label': t.subject, 'date': t.created_at.date(), 'url': f'/support/tickets/{t.pk}/', 'color': 'warning', 'icon': 'bi-headset'})
    _safe(check_tickets)

    items.sort(key=lambda x: x.get('date') or today)
    return {'items': items[:12], 'count': len(items), 'has_data': bool(items)}


# ─── BTP avancés ─────────────────────────────────────────────────────────────

def get_btp_project_profitability_data(user, company):
    def load():
        from apps.btp.models import BTPProject
        projects = BTPProject.objects.filter(
            company=company, status__in=['in_progress', 'completed'], is_active=True
        ).order_by('-updated_at')[:8]
        result = []
        for p in projects:
            budget = getattr(p, 'budget', 0) or 0
            spent = getattr(p, 'total_spent', 0) or 0
            margin_pct = round((budget - spent) / budget * 100, 1) if budget else 0
            result.append({'project': p, 'budget': budget, 'spent': spent, 'margin_pct': margin_pct, 'over_budget': spent > budget})
        return {'projects': result, 'count': len(result), 'has_data': bool(result)}
    return _safe(load, {'projects': [], 'count': 0, 'has_data': False})


def get_btp_risky_projects_data(user, company):
    def load():
        from apps.btp.models import BTPProject
        today = date.today()
        projects = BTPProject.objects.filter(
            company=company, status='in_progress', is_active=True
        ).select_related('customer', 'project_manager').order_by('-updated_at')
        risky = []
        for p in projects:
            risks = []
            if getattr(p, 'end_date', None) and p.end_date < today:
                risks.append('Retard planning')
            if risks:
                risky.append({'project': p, 'risks': risks, 'risk_count': len(risks)})
        return {'projects': risky[:8], 'count': len(risky), 'has_data': bool(risky)}
    return _safe(load, {'projects': [], 'count': 0, 'has_data': False})


def get_btp_projects_progress_data(user, company):
    def load():
        from apps.btp.models import BTPProject
        projects = BTPProject.objects.filter(
            company=company, status='in_progress', is_active=True
        ).select_related('customer', 'project_manager').order_by('-updated_at')[:10]
        result = []
        for p in projects:
            pct = getattr(p, 'progress_percent', None) or 0
            result.append({'project': p, 'progress': pct})
        return {'projects': result, 'count': len(result), 'has_data': bool(result)}
    return _safe(load, {'projects': [], 'count': 0, 'has_data': False})


def get_btp_client_requests_data(user, company):
    def load():
        from apps.portals.models import GuidedQuoteRequest
        reqs = GuidedQuoteRequest.objects.filter(
            company=company, status__in=['new', 'in_progress']
        ).order_by('-created_at')[:10]
        return {'requests': list(reqs), 'count': reqs.count(), 'has_data': reqs.exists()}
    return _safe(load, {'requests': [], 'count': 0, 'has_data': False})


def get_btp_recent_site_photos_data(user, company):
    def load():
        from apps.btp.models import BTPProject
        projects = BTPProject.objects.filter(company=company, status='in_progress', is_active=True).order_by('-updated_at')[:5]
        return {'projects': list(projects), 'count': projects.count(), 'has_data': projects.exists(), 'note': 'Photos via module documents'}
    return _safe(load, {'projects': [], 'count': 0, 'has_data': False})


def get_btp_equipment_status_data(user, company):
    return {'equipment': [], 'count': 0, 'has_data': False, 'note': 'Nécessite module matériel'}


# ─── CRM / Ventes avancés ────────────────────────────────────────────────────

def get_crm_sales_pipeline_data(user, company):
    def load():
        from apps.crm.models import Opportunity
        stages = ['new', 'qualified', 'proposal', 'negotiation', 'won', 'lost']
        pipeline = []
        for stage in stages:
            opps = Opportunity.objects.filter(company=company, status=stage)
            count = opps.count()
            total = sum(o.estimated_value or 0 for o in opps)
            pipeline.append({'stage': stage, 'count': count, 'total': total})
        return {'pipeline': pipeline, 'has_data': True}
    return _safe(load, {'pipeline': [], 'has_data': False})


def get_crm_priority_followups_data(user, company):
    def load():
        from apps.crm.models import Prospect
        today = date.today()
        prospects = Prospect.objects.filter(
            company=company,
            status__in=['new', 'contacted', 'qualified'],
            is_active=True,
            next_action_date__lte=today,
        ).order_by('next_action_date')[:10]
        return {'prospects': list(prospects), 'count': prospects.count(), 'has_data': prospects.exists()}
    return _safe(load, {'prospects': [], 'count': 0, 'has_data': False})


def get_sales_quotes_expiring_soon_data(user, company):
    def load():
        from apps.sales.models import Quote
        today = date.today()
        soon = today + timedelta(days=7)
        quotes = Quote.objects.filter(
            company=company, status='sent', expiry_date__gte=today, expiry_date__lte=soon
        ).select_related('customer').order_by('expiry_date')[:10]
        return {'quotes': list(quotes), 'count': quotes.count(), 'has_data': quotes.exists()}
    return _safe(load, {'quotes': [], 'count': 0, 'has_data': False})


def get_crm_top_customers_data(user, company):
    def load():
        from apps.crm.models import Customer
        customers = Customer.objects.filter(company=company, is_active=True).order_by('-ca_ytd')[:8]
        return {'customers': list(customers), 'count': customers.count(), 'has_data': customers.exists()}
    return _safe(load, {'customers': [], 'count': 0, 'has_data': False})


# ─── Comptabilité / Trésorerie avancés ───────────────────────────────────────

def get_accounting_bank_balances_data(user, company):
    def load():
        from apps.accounting.models import BankAccount
        accounts = BankAccount.objects.filter(company=company, is_active=True)
        total = sum(a.current_balance or 0 for a in accounts)
        return {'accounts': list(accounts), 'total': total, 'count': accounts.count(), 'has_data': accounts.exists()}
    return _safe(load, {'accounts': [], 'total': 0, 'count': 0, 'has_data': False})


def get_accounting_cashflow_forecast_data(user, company):
    def load():
        from apps.sales.models import Invoice
        from apps.purchases.models import SupplierInvoice
        today = date.today()
        horizon = today + timedelta(days=30)
        to_receive = Invoice.objects.filter(company=company, status='sent', due_date__lte=horizon)
        to_pay = SupplierInvoice.objects.filter(company=company, status__in=['pending', 'approved'], due_date__lte=horizon)
        encaissements = sum(inv.total_ttc or 0 for inv in to_receive)
        decaissements = sum(inv.total_ttc or 0 for inv in to_pay)
        return {
            'encaissements': encaissements, 'decaissements': decaissements,
            'solde_previsionnel': encaissements - decaissements,
            'horizon_days': 30, 'has_data': True,
        }
    return _safe(load, {'encaissements': 0, 'decaissements': 0, 'solde_previsionnel': 0, 'horizon_days': 30, 'has_data': False})


def get_accounting_invoice_reminders_data(user, company):
    def load():
        from apps.sales.models import Invoice
        today = date.today()
        invoices = Invoice.objects.filter(
            company=company, status='sent', due_date__lt=today
        ).select_related('customer').order_by('due_date')[:10]
        return {'invoices': list(invoices), 'count': invoices.count(), 'has_data': invoices.exists()}
    return _safe(load, {'invoices': [], 'count': 0, 'has_data': False})


def get_accounting_expenses_to_reimburse_data(user, company):
    def load():
        from apps.hr.models import ExpenseReport
        expenses = ExpenseReport.objects.filter(
            company=company, status='approved'
        ).select_related('employee').order_by('-created_at')[:10]
        total = sum(getattr(e, 'total_amount', 0) or 0 for e in expenses)
        return {'expenses': list(expenses), 'count': expenses.count(), 'total': total, 'has_data': expenses.exists()}
    return _safe(load, {'expenses': [], 'count': 0, 'total': 0, 'has_data': False})


def get_accounting_vat_to_declare_data(user, company):
    return {'vat_collected': 0, 'vat_deductible': 0, 'vat_due': 0, 'has_data': False, 'note': 'Calcul TVA basé sur les factures du mois'}


# ─── Documents avancés ───────────────────────────────────────────────────────

def get_documents_to_sign_data(user, company):
    def load():
        from apps.documents.models import Document
        docs = Document.objects.filter(company=company, status='pending_signature').order_by('-created_at')[:8]
        return {'documents': list(docs), 'count': docs.count(), 'has_data': docs.exists()}
    return _safe(load, {'documents': [], 'count': 0, 'has_data': False})


def get_documents_expiring_soon_data(user, company):
    def load():
        from apps.hr.models import EmployeePrivateDocument
        threshold = date.today() + timedelta(days=60)
        docs = EmployeePrivateDocument.objects.filter(
            company=company, expires_at__lte=threshold, expires_at__gte=date.today()
        ).select_related('employee').order_by('expires_at')[:10]
        return {'documents': list(docs), 'count': docs.count(), 'has_data': docs.exists()}
    return _safe(load, {'documents': [], 'count': 0, 'has_data': False})


def get_documents_recently_shared_data(user, company):
    def load():
        from apps.documents.models import Document
        docs = Document.objects.filter(company=company).order_by('-created_at')[:8]
        return {'documents': list(docs), 'count': docs.count(), 'has_data': docs.exists()}
    return _safe(load, {'documents': [], 'count': 0, 'has_data': False})


# ─── RH avancés ──────────────────────────────────────────────────────────────

def get_hr_today_absences_data(user, company):
    def load():
        from apps.hr.models import LeaveRequest
        today = date.today()
        absences = LeaveRequest.objects.filter(
            company=company, status='approved',
            start_date__lte=today, end_date__gte=today
        ).select_related('employee').order_by('start_date')[:10]
        return {'absences': list(absences), 'count': absences.count(), 'has_data': absences.exists(), 'today': today}
    return _safe(load, {'absences': [], 'count': 0, 'has_data': False, 'today': date.today()})


def get_hr_important_dates_data(user, company):
    def load():
        from apps.hr.models import Employee
        today = date.today()
        employees = Employee.objects.filter(company=company, is_active=True).order_by('last_name')
        upcoming = []
        for emp in employees:
            if getattr(emp, 'trial_end_date', None):
                days_left = (emp.trial_end_date - today).days
                if 0 <= days_left <= 14:
                    upcoming.append({'employee': emp, 'type': "Fin période d'essai", 'date': emp.trial_end_date, 'days': days_left, 'icon': 'bi-person-check', 'color': 'warning'})
        upcoming.sort(key=lambda x: x['date'])
        return {'events': upcoming[:10], 'count': len(upcoming), 'has_data': bool(upcoming)}
    return _safe(load, {'events': [], 'count': 0, 'has_data': False})


def get_hr_my_hours_data(user, company):
    def load():
        from apps.hr.models import Employee, Timesheet
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        try:
            employee = Employee.objects.get(company=company, user=user)
        except Employee.DoesNotExist:
            return {'hours_week': 0, 'hours_pending': 0, 'hours_validated': 0, 'has_data': False}
        week_ts = Timesheet.objects.filter(company=company, employee=employee, date__gte=week_start)
        hours_week = sum(getattr(ts, 'hours', 0) or 0 for ts in week_ts)
        pending = Timesheet.objects.filter(company=company, employee=employee, status='submitted').count()
        validated = Timesheet.objects.filter(company=company, employee=employee, status='validated', date__gte=week_start).count()
        return {'hours_week': hours_week, 'hours_pending': pending, 'hours_validated': validated, 'has_data': True, 'employee': employee}
    return _safe(load, {'hours_week': 0, 'hours_pending': 0, 'hours_validated': 0, 'has_data': False})


# ─── Support et portail ───────────────────────────────────────────────────────

def get_support_urgent_tickets_data(user, company):
    def load():
        from apps.support.models import SupportTicket
        tickets = SupportTicket.objects.filter(
            company=company, priority__in=['high', 'urgent'], status__in=['open', 'pending']
        ).order_by('-created_at')[:10]
        return {'tickets': list(tickets), 'count': tickets.count(), 'has_data': tickets.exists()}
    return _safe(load, {'tickets': [], 'count': 0, 'has_data': False})


def get_client_unread_messages_data(user, company):
    def load():
        from apps.portals.models import ClientMessage
        msgs = ClientMessage.objects.filter(
            project__company=company, is_read=False, sender_type='client'
        ).select_related('project').order_by('-created_at')[:10]
        return {'messages': list(msgs), 'count': msgs.count(), 'has_data': msgs.exists()}
    return _safe(load, {'messages': [], 'count': 0, 'has_data': False})


def get_client_portal_activity_data(user, company):
    def load():
        from apps.portals.models import ClientMessage
        activities = ClientMessage.objects.filter(
            project__company=company
        ).select_related('project').order_by('-created_at')[:10]
        return {'activities': list(activities), 'count': activities.count(), 'has_data': activities.exists()}
    return _safe(load, {'activities': [], 'count': 0, 'has_data': False})


# ─── Sites web ───────────────────────────────────────────────────────────────

def get_website_leads_data(user, company):
    def load():
        from apps.websites.models import ContactForm
        leads = ContactForm.objects.filter(company=company, is_processed=False).order_by('-created_at')[:10]
        return {'leads': list(leads), 'count': leads.count(), 'has_data': leads.exists()}
    return _safe(load, {'leads': [], 'count': 0, 'has_data': False})


def get_website_pages_to_publish_data(user, company):
    def load():
        from apps.websites.models import Page
        pages = Page.objects.filter(company=company, status='draft').order_by('-updated_at')[:10]
        return {'pages': list(pages), 'count': pages.count(), 'has_data': pages.exists()}
    return _safe(load, {'pages': [], 'count': 0, 'has_data': False})


def get_website_basic_stats_data(user, company):
    def load():
        from apps.websites.models import Website, ContactForm
        site = Website.objects.filter(company=company).first()
        leads = ContactForm.objects.filter(company=company).count() if site else 0
        return {'site': site, 'leads_count': leads, 'has_data': bool(site)}
    return _safe(load, {'site': None, 'leads_count': 0, 'has_data': False})


# ─── E-commerce et commerce ───────────────────────────────────────────────────

def get_ecommerce_urgent_orders_data(user, company):
    def load():
        from apps.ecommerce.models import Order
        from django.utils import timezone
        orders = Order.objects.filter(
            company=company, status__in=['confirmed', 'processing']
        ).order_by('created_at')[:10]
        return {'orders': list(orders), 'count': orders.count(), 'has_data': orders.exists()}
    return _safe(load, {'orders': [], 'count': 0, 'has_data': False})


def get_ecommerce_abandoned_carts_data(user, company):
    return {'carts': [], 'count': 0, 'has_data': False, 'note': 'Module panier à implémenter'}


def get_inventory_products_to_reorder_data(user, company):
    def load():
        from apps.inventory.models import Product
        products = Product.objects.filter(
            company=company, is_active=True, stock_quantity__lte=5
        ).order_by('stock_quantity')[:12]
        return {'products': list(products), 'count': products.count(), 'has_data': products.exists()}
    return _safe(load, {'products': [], 'count': 0, 'has_data': False})


def get_commerce_omnichannel_sales_data(user, company):
    def load():
        from apps.commerce.models import POSSession
        sessions = POSSession.objects.filter(company=company, status='closed')
        pos_total = sum(getattr(s, 'total_sales', 0) or 0 for s in sessions[:30])
        channels = [
            {'label': 'Caisse (POS)', 'amount': pos_total, 'icon': 'bi-cash-register', 'color': '#10B981'},
            {'label': 'Boutique en ligne', 'amount': 0, 'icon': 'bi-bag', 'color': '#2563EB'},
            {'label': 'B2B', 'amount': 0, 'icon': 'bi-buildings', 'color': '#7C3AED'},
        ]
        return {'channels': channels, 'has_data': bool(pos_total)}
    return _safe(load, {'channels': [], 'has_data': False})


# ─── Intelligence Orion ──────────────────────────────────────────────────────

def get_orion_suggestions_data(user, company):
    suggestions = []
    today = date.today()

    def check_quotes():
        from apps.sales.models import Quote
        count = Quote.objects.filter(company=company, status='draft').count()
        if count:
            suggestions.append({'label': f'{count} devis en brouillon à envoyer', 'icon': 'bi-file-earmark-arrow-up', 'url': '/sales/quotes/?status=draft', 'priority': 'normal', 'action': 'Envoyer'})
    _safe(check_quotes)

    def check_overdue():
        from apps.sales.models import Invoice
        count = Invoice.objects.filter(company=company, status='sent', due_date__lt=today).count()
        if count:
            suggestions.append({'label': f'{count} facture(s) en retard à relancer', 'icon': 'bi-exclamation-octagon', 'url': '/sales/invoices/', 'priority': 'high', 'action': 'Relancer'})
    _safe(check_overdue)

    def check_stock():
        from apps.inventory.models import Product
        count = Product.objects.filter(company=company, is_active=True, stock_quantity__lte=5).count()
        if count:
            suggestions.append({'label': f'{count} produit(s) en stock critique', 'icon': 'bi-box-seam', 'url': '/inventory/products/', 'priority': 'high', 'action': 'Commander'})
    _safe(check_stock)

    def check_tickets():
        from apps.support.models import SupportTicket
        count = SupportTicket.objects.filter(company=company, status='open', priority='urgent').count()
        if count:
            suggestions.append({'label': f'{count} ticket(s) urgent(s) sans réponse', 'icon': 'bi-headset', 'url': '/support/tickets/', 'priority': 'urgent', 'action': 'Traiter'})
    _safe(check_tickets)

    return {'suggestions': suggestions[:8], 'count': len(suggestions), 'has_data': bool(suggestions)}


def get_daily_summary_data(user, company):
    today = date.today()
    data = {'today': today, 'has_data': True}

    def count_tasks():
        from apps.hr.models import LeaveRequest
        data['validations_pending'] = LeaveRequest.objects.filter(company=company, status='pending').count()
    _safe(count_tasks)

    def count_invoices():
        from apps.sales.models import Invoice
        data['invoices_overdue'] = Invoice.objects.filter(company=company, status='sent', due_date__lt=today).count()
    _safe(count_invoices)

    def count_tickets():
        from apps.support.models import SupportTicket
        data['tickets_open'] = SupportTicket.objects.filter(company=company, status__in=['open', 'pending']).count()
    _safe(count_tickets)

    data.setdefault('validations_pending', 0)
    data.setdefault('invoices_overdue', 0)
    data.setdefault('tickets_open', 0)
    return data


def get_personal_goals_data(user, company):
    def load():
        from .models import DashboardGoal
        goals = DashboardGoal.objects.filter(user=user, company=company, status='active').order_by('-created_at')[:6]
        return {'goals': list(goals), 'count': goals.count(), 'has_data': goals.exists()}


# ── LUNEA ─────────────────────────────────────────────────────────────────────

def get_lunea_new_orders_data(user, company):
    def load():
        from apps.lunea.models import WebOrder
        from django.utils import timezone
        today = timezone.now().date()
        orders = WebOrder.objects.filter(company=company, created_at__date=today).order_by('-created_at')[:10]
        return {'orders': list(orders), 'count': orders.count(), 'has_data': orders.exists()}
    return _safe(load, {'orders': [], 'count': 0, 'has_data': False})


def get_lunea_orders_to_prepare_data(user, company):
    def load():
        from apps.lunea.models import WebOrder
        orders = WebOrder.objects.filter(company=company, status='paid').order_by('created_at')[:10]
        return {'orders': list(orders), 'count': orders.count(), 'has_data': orders.exists()}
    return _safe(load, {'orders': [], 'count': 0, 'has_data': False})


def get_lunea_low_shade_stock_data(user, company):
    def load():
        from apps.lunea.models import ProductShade
        shades = ProductShade.objects.filter(
            product__company=company, stock__lte=5
        ).select_related('product').order_by('stock')[:10]
        return {'shades': list(shades), 'count': shades.count(), 'has_data': shades.exists()}
    return _safe(load, {'shades': [], 'count': 0, 'has_data': False})


def get_lunea_best_sellers_data(user, company):
    def load():
        from apps.lunea.models import LuneaProduct
        products = LuneaProduct.objects.filter(
            company=company, is_active=True, is_best_seller=True
        ).order_by('-created_at')[:8]
        return {'products': list(products), 'count': products.count(), 'has_data': products.exists()}
    return _safe(load, {'products': [], 'count': 0, 'has_data': False})


def get_lunea_pending_reviews_data(user, company):
    def load():
        from apps.lunea.models import ProductReview
        reviews = ProductReview.objects.filter(
            product__company=company, is_approved=False
        ).select_related('product').order_by('-created_at')[:10]
        return {'reviews': list(reviews), 'count': reviews.count(), 'has_data': reviews.exists()}
    return _safe(load, {'reviews': [], 'count': 0, 'has_data': False})


def get_lunea_revenue_today_data(user, company):
    def load():
        from apps.lunea.models import WebOrder
        from django.utils import timezone
        from django.db.models import Sum
        today = timezone.now().date()
        agg = WebOrder.objects.filter(
            company=company, status__in=['paid', 'shipped', 'delivered'], created_at__date=today
        ).aggregate(total=Sum('total_amount'))
        txn = WebOrder.objects.filter(
            company=company, status__in=['paid', 'shipped', 'delivered'], created_at__date=today
        ).count()
        return {'revenue': agg['total'] or 0, 'transactions': txn, 'has_data': True}
    return _safe(load, {'revenue': 0, 'transactions': 0, 'has_data': False})


def get_lunea_shade_alerts_data(user, company):
    def load():
        from apps.lunea.models import ShadeStockAlert
        alerts = ShadeStockAlert.objects.filter(
            shade__product__company=company, is_notified=False
        ).select_related('shade__product').order_by('-created_at')[:10]
        return {'alerts': list(alerts), 'count': alerts.count(), 'has_data': alerts.exists()}
    return _safe(load, {'alerts': [], 'count': 0, 'has_data': False})


def get_lunea_gift_cards_active_data(user, company):
    def load():
        from apps.lunea.models import GiftCard
        from django.db.models import Sum
        cards = GiftCard.objects.filter(company=company, is_active=True, balance__gt=0)
        total = cards.aggregate(bal=Sum('balance'))['bal'] or 0
        return {'count': cards.count(), 'total_balance': total, 'has_data': cards.exists()}
    return _safe(load, {'count': 0, 'total_balance': 0, 'has_data': False})


def get_lunea_loyalty_points_issued_data(user, company):
    def load():
        from apps.lunea.models import LoyaltyTransaction
        from django.utils import timezone
        from django.db.models import Sum
        today = timezone.now().date()
        agg = LoyaltyTransaction.objects.filter(
            account__company=company, type='earn', created_at__date=today
        ).aggregate(pts=Sum('points'))
        return {'points_today': agg['pts'] or 0, 'has_data': True}
    return _safe(load, {'points_today': 0, 'has_data': False})


def get_lunea_newsletter_subscribers_data(user, company):
    def load():
        from apps.lunea.models import NewsletterSubscriber
        count = NewsletterSubscriber.objects.filter(company=company, is_active=True).count()
        return {'count': count, 'has_data': count > 0}
    return _safe(load, {'count': 0, 'has_data': False})


def get_lunea_subscription_renewals_data(user, company):
    def load():
        from apps.lunea.models import BeautySubscription
        from django.utils import timezone
        import datetime
        soon = timezone.now().date() + datetime.timedelta(days=7)
        subs = BeautySubscription.objects.filter(
            company=company, status='active', next_billing_date__lte=soon
        ).order_by('next_billing_date')[:10]
        return {'subscriptions': list(subs), 'count': subs.count(), 'has_data': subs.exists()}
    return _safe(load, {'subscriptions': [], 'count': 0, 'has_data': False})


def get_lunea_abandoned_carts_data(user, company):
    return {'count': 0, 'has_data': False}


def get_lunea_conversion_rate_data(user, company):
    return {'rate': 0.0, 'has_data': False}


def get_lunea_beauty_quiz_completions_data(user, company):
    def load():
        from apps.lunea.models import BeautyQuizResult
        from django.utils import timezone
        from django.utils.timezone import timedelta
        week_ago = timezone.now() - timedelta(days=7)
        count = BeautyQuizResult.objects.filter(company=company, created_at__gte=week_ago).count()
        return {'count': count, 'has_data': count > 0}
    return _safe(load, {'count': 0, 'has_data': False})


def get_lunea_samples_sent_data(user, company):
    def load():
        from apps.lunea.models import OrderSample
        from django.utils import timezone
        from django.utils.timezone import timedelta
        week_ago = timezone.now() - timedelta(days=7)
        count = OrderSample.objects.filter(
            order__company=company, created_at__gte=week_ago
        ).count()
        return {'count': count, 'has_data': count > 0}
    return _safe(load, {'count': 0, 'has_data': False})


# ── BACKUPS ───────────────────────────────────────────────────────────────────

def get_backups_last_status_data(user, company):
    return {'status': 'unknown', 'last_run': None, 'has_data': False}


def get_backups_pending_data(user, company):
    return {'count': 0, 'has_data': False}


def get_backups_failed_data(user, company):
    return {'count': 0, 'items': [], 'has_data': False}


def get_backups_size_used_data(user, company):
    return {'size_gb': 0, 'limit_gb': 0, 'has_data': False}


def get_backups_scheduled_data(user, company):
    return {'next_run': None, 'has_data': False}


def get_backups_recent_restores_data(user, company):
    return {'restores': [], 'count': 0, 'has_data': False}


# ── COMPETITOR INTELLIGENCE ───────────────────────────────────────────────────

def get_competitor_price_alerts_data(user, company):
    return {'alerts': [], 'count': 0, 'has_data': False}


def get_competitor_new_products_data(user, company):
    return {'products': [], 'count': 0, 'has_data': False}


def get_competitor_social_mentions_data(user, company):
    return {'mentions': [], 'count': 0, 'has_data': False}


def get_competitor_ranking_changes_data(user, company):
    return {'changes': [], 'count': 0, 'has_data': False}


def get_competitor_promo_alerts_data(user, company):
    return {'promos': [], 'count': 0, 'has_data': False}


def get_competitor_reviews_summary_data(user, company):
    return {'summary': {}, 'has_data': False}


def get_competitor_traffic_trends_data(user, company):
    return {'trends': [], 'has_data': False}


def get_competitor_ad_intelligence_data(user, company):
    return {'ads': [], 'count': 0, 'has_data': False}


def get_competitor_news_data(user, company):
    return {'news': [], 'count': 0, 'has_data': False}


# ── CLOUDFLARE ────────────────────────────────────────────────────────────────

def get_cloudflare_zones_status_data(user, company):
    return {'zones': [], 'count': 0, 'has_data': False}


def get_cloudflare_firewall_events_data(user, company):
    return {'events': [], 'count': 0, 'has_data': False}


def get_cloudflare_traffic_stats_data(user, company):
    return {'requests': 0, 'bandwidth_gb': 0, 'has_data': False}


def get_cloudflare_ssl_status_data(user, company):
    return {'zones': [], 'expiring_count': 0, 'has_data': False}


def get_cloudflare_page_rules_data(user, company):
    return {'rules': [], 'count': 0, 'has_data': False}


def get_cloudflare_analytics_data(user, company):
    return {'visitors': 0, 'pageviews': 0, 'has_data': False}


# ── DOMAINS ───────────────────────────────────────────────────────────────────

def get_domains_expiring_data(user, company):
    return {'domains': [], 'count': 0, 'has_data': False}


def get_domains_dns_health_data(user, company):
    return {'domains': [], 'issues_count': 0, 'has_data': False}


def get_domains_whois_summary_data(user, company):
    return {'domains': [], 'count': 0, 'has_data': False}


def get_domains_ssl_expiry_data(user, company):
    return {'domains': [], 'expiring_soon': 0, 'has_data': False}


def get_domains_redirect_status_data(user, company):
    return {'redirects': [], 'broken_count': 0, 'has_data': False}


# ── PRIVATE SAAS ──────────────────────────────────────────────────────────────

def get_private_saas_services_status_data(user, company):
    return {'services': [], 'down_count': 0, 'has_data': False}


def get_private_saas_users_count_data(user, company):
    return {'count': 0, 'active': 0, 'has_data': False}


def get_private_saas_storage_usage_data(user, company):
    return {'used_gb': 0, 'limit_gb': 0, 'has_data': False}


def get_private_saas_pending_updates_data(user, company):
    return {'updates': [], 'count': 0, 'has_data': False}


def get_private_saas_incidents_data(user, company):
    return {'incidents': [], 'count': 0, 'has_data': False}


def get_private_saas_backups_data(user, company):
    return {'services': [], 'failed_count': 0, 'has_data': False}


# ── LOYALTY ───────────────────────────────────────────────────────────────────

def get_loyalty_points_issued_data(user, company):
    def load():
        from apps.lunea.models import LoyaltyTransaction
        from django.utils import timezone
        from django.utils.timezone import timedelta
        from django.db.models import Sum
        week_ago = timezone.now() - timedelta(days=7)
        agg = LoyaltyTransaction.objects.filter(
            account__company=company, type='earn', created_at__gte=week_ago
        ).aggregate(pts=Sum('points'))
        return {'points': agg['pts'] or 0, 'has_data': True}
    return _safe(load, {'points': 0, 'has_data': False})


def get_loyalty_members_active_data(user, company):
    def load():
        from apps.lunea.models import LoyaltyAccount
        count = LoyaltyAccount.objects.filter(company=company).count()
        return {'count': count, 'has_data': count > 0}
    return _safe(load, {'count': 0, 'has_data': False})


def get_loyalty_redemptions_data(user, company):
    def load():
        from apps.lunea.models import LoyaltyTransaction
        from django.utils import timezone
        from django.utils.timezone import timedelta
        week_ago = timezone.now() - timedelta(days=7)
        redemptions = LoyaltyTransaction.objects.filter(
            account__company=company, type='redeem', created_at__gte=week_ago
        ).select_related('account').order_by('-created_at')[:10]
        return {'redemptions': list(redemptions), 'count': redemptions.count(), 'has_data': redemptions.exists()}
    return _safe(load, {'redemptions': [], 'count': 0, 'has_data': False})


def get_loyalty_tier_distribution_data(user, company):
    def load():
        from apps.lunea.models import LoyaltyAccount, LoyaltyTier
        tiers = LoyaltyTier.objects.filter(company=company).order_by('min_points')
        result = []
        for tier in tiers:
            count = LoyaltyAccount.objects.filter(company=company, tier=tier).count()
            result.append({'tier': tier, 'count': count})
        return {'tiers': result, 'has_data': bool(result)}
    return _safe(load, {'tiers': [], 'has_data': False})


def get_loyalty_expiring_points_data(user, company):
    return {'transactions': [], 'count': 0, 'has_data': False}


# ── GIFT CARDS ────────────────────────────────────────────────────────────────

def get_gift_cards_issued_data(user, company):
    def load():
        from apps.lunea.models import GiftCard
        from django.utils import timezone
        from django.utils.timezone import timedelta
        month_ago = timezone.now() - timedelta(days=30)
        count = GiftCard.objects.filter(company=company, created_at__gte=month_ago).count()
        return {'count': count, 'has_data': count > 0}
    return _safe(load, {'count': 0, 'has_data': False})


def get_gift_cards_active_data(user, company):
    def load():
        from apps.lunea.models import GiftCard
        from django.db.models import Sum
        cards = GiftCard.objects.filter(company=company, is_active=True, balance__gt=0)
        total = cards.aggregate(bal=Sum('balance'))['bal'] or 0
        return {'count': cards.count(), 'total_balance': total, 'has_data': cards.exists()}
    return _safe(load, {'count': 0, 'total_balance': 0, 'has_data': False})


def get_gift_cards_redeemed_data(user, company):
    def load():
        from apps.lunea.models import GiftCardRedemption
        from django.utils import timezone
        from django.utils.timezone import timedelta
        from django.db.models import Sum
        month_ago = timezone.now() - timedelta(days=30)
        redemptions = GiftCardRedemption.objects.filter(
            gift_card__company=company, created_at__gte=month_ago
        )
        total = redemptions.aggregate(amt=Sum('amount_used'))['amt'] or 0
        return {'count': redemptions.count(), 'total_amount': total, 'has_data': redemptions.exists()}
    return _safe(load, {'count': 0, 'total_amount': 0, 'has_data': False})


def get_gift_cards_expiring_data(user, company):
    def load():
        from apps.lunea.models import GiftCard
        from django.utils import timezone
        import datetime
        soon = timezone.now().date() + datetime.timedelta(days=30)
        cards = GiftCard.objects.filter(
            company=company, is_active=True, balance__gt=0, expires_at__lte=soon, expires_at__isnull=False
        ).order_by('expires_at')[:10]
        return {'cards': list(cards), 'count': cards.count(), 'has_data': cards.exists()}
    return _safe(load, {'cards': [], 'count': 0, 'has_data': False})
    return _safe(load, {'goals': [], 'count': 0, 'has_data': False})
