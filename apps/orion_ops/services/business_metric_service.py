"""
apps/orion_ops/services/business_metric_service.py — Collecte des métriques métier.

Chaque fonction collecte une métrique fonctionnelle depuis les modèles existants
et enregistre une BusinessMetricReading. Les seuils sont configurables par
constante — ils ne modifient aucune donnée.
"""
from __future__ import annotations

from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone


def _save_metric(metric_type: str, value: float, status: str, metadata: dict = None):
    from apps.orion_ops.models import BusinessMetricReading
    BusinessMetricReading.objects.create(
        metric_type=metric_type,
        value=value,
        status=status,
        metadata=metadata or {},
    )
    return {'metric_type': metric_type, 'value': value, 'status': status}


def collect_payments_failed_1h() -> dict:
    """Paiements e-commerce échoués dans la dernière heure."""
    try:
        from apps.ecommerce.models import WebOrder
        cutoff = timezone.now() - timedelta(hours=1)
        count = WebOrder.objects.filter(
            payment_status='failed',
            created_at__gte=cutoff,
        ).count()
        status = 'ok' if count == 0 else ('warning' if count <= 3 else 'critical')
        return _save_metric('payments_failed_1h', count, status)
    except Exception as e:
        return {'metric_type': 'payments_failed_1h', 'error': str(e)}


def collect_orders_blocked() -> dict:
    """Commandes bloquées (statut 'blocked' ou 'on_hold')."""
    try:
        from apps.sales.models import SalesOrder
        count = SalesOrder.objects.filter(
            status__in=['blocked', 'on_hold']
        ).count()
        status = 'ok' if count == 0 else ('warning' if count <= 5 else 'critical')
        return _save_metric('orders_blocked', count, status)
    except Exception as e:
        return {'metric_type': 'orders_blocked', 'error': str(e)}


def collect_negative_stock_count() -> dict:
    """Nombre de produits avec un stock négatif."""
    try:
        from apps.inventory.models import Product
        count = Product.objects.filter(stock_quantity__lt=0).count()
        status = 'ok' if count == 0 else ('warning' if count <= 3 else 'critical')
        return _save_metric('negative_stock_count', count, status)
    except Exception as e:
        return {'metric_type': 'negative_stock_count', 'error': str(e)}


def collect_notifications_pending() -> dict:
    """Notifications en attente d'envoi."""
    try:
        from apps.notifications.models import Notification
        count = Notification.objects.filter(is_read=False).count()
        status = 'ok' if count < 10 else ('warning' if count < 50 else 'critical')
        return _save_metric('notifications_pending', count, status)
    except Exception as e:
        return {'metric_type': 'notifications_pending', 'error': str(e)}


def collect_invoices_24h() -> dict:
    """Factures générées dans les dernières 24h."""
    try:
        from apps.accounting.models import Invoice
        cutoff = timezone.now() - timedelta(hours=24)
        count = Invoice.objects.filter(created_at__gte=cutoff).count()
        return _save_metric('invoices_24h', count, 'ok')
    except Exception as e:
        return {'metric_type': 'invoices_24h', 'error': str(e)}


def collect_ecommerce_orders_24h() -> dict:
    """Commandes e-commerce reçues dans les 24h."""
    try:
        from apps.ecommerce.models import WebOrder
        cutoff = timezone.now() - timedelta(hours=24)
        count = WebOrder.objects.filter(
            created_at__gte=cutoff,
            payment_status__in=['paid', 'authorized'],
        ).count()
        return _save_metric('ecommerce_orders_24h', count, 'ok')
    except Exception as e:
        return {'metric_type': 'ecommerce_orders_24h', 'error': str(e)}


def collect_all_business_metrics() -> dict:
    """Collecte toutes les métriques métier. Appelé par la tâche Celery."""
    collectors = [
        collect_payments_failed_1h,
        collect_orders_blocked,
        collect_negative_stock_count,
        collect_notifications_pending,
        collect_invoices_24h,
        collect_ecommerce_orders_24h,
    ]
    results = []
    errors = []
    for fn in collectors:
        try:
            r = fn()
            if 'error' in r:
                errors.append(r)
            else:
                results.append(r)
        except Exception as e:
            errors.append({'collector': fn.__name__, 'error': str(e)})

    return {'collected': len(results), 'errors': len(errors), 'results': results}
