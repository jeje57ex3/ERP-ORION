"""
apps/orion_ops/services/data_quality_service.py — Audit automatique de la qualité des données.

Exécuté quotidiennement via une tâche Celery.
Aucune donnée n'est modifiée par ce service — uniquement lecture et signalement.
Les anomalies sont dédoublonnées : une anomalie du même type ouverte depuis
moins de 7 jours n'est pas recréée (le count est mis à jour).
"""
from __future__ import annotations

from datetime import timedelta

from django.db import connection
from django.utils import timezone


def _upsert_anomaly(anomaly_type: str, severity: str, count: int, module: str,
                    examples: list, cause: str = '', fix_hint: str = '') -> bool:
    """
    Crée ou met à jour une anomalie.
    Retourne True si créée, False si mise à jour.
    """
    from apps.orion_ops.models import DataQualityAnomaly

    cutoff_7d = timezone.now() - timedelta(days=7)
    existing = DataQualityAnomaly.objects.filter(
        anomaly_type=anomaly_type,
        status__in=['open', 'acknowledged', 'fixing'],
        detected_at__gte=cutoff_7d,
    ).order_by('-detected_at').first()

    if existing:
        existing.count = count
        existing.examples = examples[:5]
        existing.save(update_fields=['count', 'examples'])
        return False

    DataQualityAnomaly.objects.create(
        anomaly_type=anomaly_type,
        severity=severity,
        count=count,
        module=module,
        examples=examples[:5],
        cause=cause,
        fix_hint=fix_hint,
    )
    return True


def check_duplicate_customers() -> dict:
    """Clients avec le même email (doublons)."""
    try:
        from apps.crm.models import Customer
        from django.db.models import Count as DCount

        dupes = (Customer.objects
                 .values('email')
                 .annotate(n=DCount('id'))
                 .filter(n__gt=1, email__isnull=False)
                 .exclude(email=''))

        count = sum(d['n'] - 1 for d in dupes)
        if count == 0:
            return {'check': 'duplicate_customer', 'count': 0, 'status': 'ok'}

        examples = [{'email': d['email'], 'count': d['n']} for d in list(dupes)[:5]]
        _upsert_anomaly(
            anomaly_type='duplicate_customer',
            severity='high',
            count=count,
            module='crm',
            examples=examples,
            cause='Plusieurs enregistrements clients partagent le même email',
            fix_hint='Fusionner les doublons via l\'interface CRM > Clients > Fusion',
        )
        return {'check': 'duplicate_customer', 'count': count, 'status': 'anomaly'}
    except Exception as e:
        return {'check': 'duplicate_customer', 'status': 'error', 'error': str(e)}


def check_negative_stock() -> dict:
    """Produits avec un stock quantité négatif."""
    try:
        from apps.inventory.models import Product
        from django.db.models import Q

        neg = Product.objects.filter(stock_quantity__lt=0)
        count = neg.count()
        if count == 0:
            return {'check': 'negative_stock', 'count': 0, 'status': 'ok'}

        examples = list(neg.values('id', 'name', 'stock_quantity')[:5])
        _upsert_anomaly(
            anomaly_type='negative_stock',
            severity='high',
            count=count,
            module='inventory',
            examples=[{'id': e['id'], 'detail': f"{e['name']}: {e['stock_quantity']}"} for e in examples],
            cause='Stock négatif suite à des ventes sans réapprovisionnement ou erreur import',
            fix_hint='Régulariser via Inventaire > Mouvements > Entrée de stock',
        )
        return {'check': 'negative_stock', 'count': count, 'status': 'anomaly'}
    except Exception as e:
        return {'check': 'negative_stock', 'status': 'error', 'error': str(e)}


def check_unpaid_invoices_60d() -> dict:
    """Factures impayées depuis plus de 60 jours."""
    try:
        from apps.accounting.models import Invoice
        from django.db.models import Q
        cutoff = timezone.now().date() - timedelta(days=60)
        overdue = Invoice.objects.filter(
            Q(status__in=['sent', 'overdue', 'draft']) &
            Q(due_date__lt=cutoff)
        )
        count = overdue.count()
        if count == 0:
            return {'check': 'unpaid_invoice_60d', 'count': 0, 'status': 'ok'}

        examples = list(overdue.values('id', 'invoice_number', 'due_date', 'total_ttc')[:5])
        _upsert_anomaly(
            anomaly_type='unpaid_invoice_60d',
            severity='medium',
            count=count,
            module='accounting',
            examples=[{'id': e['id'], 'detail': f"#{e['invoice_number']} — échéance {e['due_date']}"} for e in examples],
            fix_hint='Relancer les clients via Comptabilité > Créances > Relances',
        )
        return {'check': 'unpaid_invoice_60d', 'count': count, 'status': 'anomaly'}
    except Exception as e:
        return {'check': 'unpaid_invoice_60d', 'status': 'error', 'error': str(e)}


def check_stale_data_quality_anomalies() -> dict:
    """Anomalies résolues automatiquement si plus aucun problème détecté."""
    from apps.orion_ops.models import DataQualityAnomaly

    count = DataQualityAnomaly.objects.filter(
        status__in=['open', 'acknowledged'],
        detected_at__lt=timezone.now() - timedelta(days=90),
    ).count()
    return {'check': 'stale_anomalies', 'count': count, 'status': 'ok'}


def run_all_data_quality_checks() -> dict:
    """
    Lance tous les contrôles de qualité et retourne un résumé.
    Appelé par la tâche Celery quotidienne.
    """
    checks = [
        check_duplicate_customers,
        check_negative_stock,
        check_unpaid_invoices_60d,
        check_stale_data_quality_anomalies,
    ]
    results = {}
    anomalies_found = 0
    for fn in checks:
        try:
            r = fn()
            results[r['check']] = r
            if r.get('status') == 'anomaly':
                anomalies_found += 1
        except Exception as e:
            results[fn.__name__] = {'status': 'error', 'error': str(e)}

    return {
        'checks_run': len(checks),
        'anomalies_found': anomalies_found,
        'results': results,
    }
