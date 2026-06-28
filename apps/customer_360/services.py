"""
customer_360/services.py
Service de données enrichies pour la vue Customer 360.
"""
from decimal import Decimal
from django.db.models import Sum, Count, Q
from django.utils import timezone
from .models import CustomerScore, CustomerTimelineEvent


def add_timeline_event(company, customer, event_type, title, *, description='', brand_key='',
                       related_object_type='', related_object_id=''):
    return CustomerTimelineEvent.objects.create(
        company=company,
        customer=customer,
        brand_key=brand_key,
        event_type=event_type,
        title=title,
        description=description,
        related_object_type=related_object_type,
        related_object_id=str(related_object_id) if related_object_id else '',
    )


def upsert_score(company, customer, score_type, score, label='', explanation='', brand_key=''):
    obj, _ = CustomerScore.objects.update_or_create(
        company=company,
        customer=customer,
        score_type=score_type,
        brand_key=brand_key,
        defaults={'score': score, 'label': label, 'explanation': explanation},
    )
    return obj


def compute_customer_scores(company, customer):
    """Calcule les scores d'un client à partir des données existantes."""
    scores = {}

    # Score fidélité : basé sur nombre de commandes
    try:
        from apps.sales.models import SalesOrder
        order_count = SalesOrder.objects.filter(company=company, customer=customer).count()
    except Exception:
        order_count = 0
    loyalty = min(Decimal('100'), Decimal(order_count) * Decimal('10'))
    upsert_score(company, customer, 'loyalty', loyalty,
                 label='Fidèle' if loyalty >= 50 else 'Nouveau',
                 explanation=f'{order_count} commande(s)')
    scores['loyalty'] = float(loyalty)

    # Score risque : clients sans commandes récentes (90j)
    try:
        from apps.sales.models import SalesOrder
        from datetime import timedelta
        recent = SalesOrder.objects.filter(
            company=company, customer=customer,
            created_at__gte=timezone.now() - timedelta(days=90)
        ).exists()
    except Exception:
        recent = True
    risk = Decimal('0') if recent else Decimal('70')
    upsert_score(company, customer, 'risk', risk,
                 label='À risque' if risk > 50 else 'Actif',
                 explanation='Aucune commande dans les 90 derniers jours' if risk > 50 else 'Actif récemment')
    scores['risk'] = float(risk)

    # Score paiement : factures impayées
    try:
        from apps.sales.models import Invoice
        unpaid = Invoice.objects.filter(
            company=company, customer=customer, status='overdue'
        ).count()
        payment = max(Decimal('0'), Decimal('100') - Decimal(unpaid) * Decimal('25'))
        upsert_score(company, customer, 'payment', payment,
                     label='Retards' if unpaid else 'Bon payeur',
                     explanation=f'{unpaid} facture(s) en retard')
        scores['payment'] = float(payment)
    except Exception:
        pass

    return scores


def get_customer_360_data(company, customer):
    """Agrège toutes les données pour la vue 360."""
    data = {
        'customer': customer,
        'scores': list(CustomerScore.objects.filter(company=company, customer=customer).order_by('score_type')),
        'timeline': list(CustomerTimelineEvent.objects.filter(company=company, customer=customer).order_by('-created_at')[:30]),
    }

    try:
        from apps.sales.models import SalesOrder
        orders = SalesOrder.objects.filter(company=company, customer=customer).order_by('-created_at')
        data['orders_count'] = orders.count()
        data['orders_total'] = orders.aggregate(t=Sum('total_ttc'))['t'] or Decimal('0')
        data['recent_orders'] = list(orders[:5])
    except Exception:
        data['orders_count'] = 0
        data['orders_total'] = Decimal('0')
        data['recent_orders'] = []

    try:
        from apps.sales.models import Invoice
        invoices = Invoice.objects.filter(company=company, customer=customer).order_by('-created_at')
        data['invoices_count'] = invoices.count()
        data['invoices_unpaid'] = invoices.filter(status__in=['sent', 'overdue']).count()
        data['recent_invoices'] = list(invoices[:5])
    except Exception:
        data['invoices_count'] = 0
        data['invoices_unpaid'] = 0
        data['recent_invoices'] = []

    try:
        from apps.support.models import SupportTicket
        tickets = SupportTicket.objects.filter(company=company, customer=customer).order_by('-created_at')
        data['tickets_open'] = tickets.filter(status='open').count()
        data['recent_tickets'] = list(tickets[:5])
    except Exception:
        data['tickets_open'] = 0
        data['recent_tickets'] = []

    return data
