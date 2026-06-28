"""Auto-populate PDCA KPI baselines from other ERP modules."""
from decimal import Decimal

from .models import PDCACycle, PDCAKPI


def auto_populate_kpis(cycle: PDCACycle):
    category = cycle.category
    company = cycle.company

    if category == 'quality':
        _kpi_quality(cycle, company)
    elif category in ('sales', 'shop'):
        _kpi_sales(cycle, company)
    elif category == 'customer_service':
        _kpi_customer_service(cycle, company)
    elif category == 'stock':
        _kpi_stock(cycle, company)
    elif category == 'system_health':
        _kpi_system_health(cycle, company)
    elif category == 'bug':
        _kpi_bug(cycle, company)


def _kpi_quality(cycle, company):
    _ensure_kpi(cycle, 'Taux de satisfaction client', unit='%')
    _ensure_kpi(cycle, 'Nombre de réclamations', unit='')


def _kpi_sales(cycle, company):
    try:
        from apps.ecommerce.models import Order
        order_count = Order.objects.filter(company=company).count()
        kpi = _ensure_kpi(cycle, 'Nombre de commandes', unit='')
        if kpi and kpi.before_value is None:
            kpi.before_value = Decimal(order_count)
            kpi.save(update_fields=['before_value'])
    except Exception:
        pass
    _ensure_kpi(cycle, 'Chiffre d\'affaires', unit='EUR')
    _ensure_kpi(cycle, 'Taux de conversion', unit='%')


def _kpi_customer_service(cycle, company):
    _ensure_kpi(cycle, 'Délai moyen de réponse', unit='h')
    _ensure_kpi(cycle, 'Taux de résolution au premier contact', unit='%')


def _kpi_stock(cycle, company):
    try:
        from apps.ecommerce.models import Product
        low_stock = Product.objects.filter(
            company=company,
            stock__lte=5,
        ).count()
        kpi = _ensure_kpi(cycle, 'Produits en stock bas', unit='')
        if kpi and kpi.before_value is None:
            kpi.before_value = Decimal(low_stock)
            kpi.save(update_fields=['before_value'])
    except Exception:
        pass
    _ensure_kpi(cycle, 'Rotation de stock', unit='')


def _kpi_system_health(cycle, company):
    try:
        from apps.system_health.models import HealthIssue
        open_issues = HealthIssue.objects.filter(company=company, is_resolved=False).count()
        kpi = _ensure_kpi(cycle, 'Problèmes système ouverts', unit='')
        if kpi and kpi.before_value is None:
            kpi.before_value = Decimal(open_issues)
            kpi.save(update_fields=['before_value'])
    except Exception:
        pass


def _kpi_bug(cycle, company):
    _ensure_kpi(cycle, 'Bugs ouverts', unit='')
    _ensure_kpi(cycle, 'Délai moyen de correction', unit='h')


def _ensure_kpi(cycle, name, unit=''):
    existing = PDCAKPI.objects.filter(cycle=cycle, name=name).first()
    if existing:
        return existing
    return PDCAKPI.objects.create(cycle=cycle, name=name, unit=unit)


def compute_cycle_success_rate(cycle: PDCACycle) -> float:
    kpis = list(cycle.kpis.all())
    if not kpis:
        return 0.0
    reached = sum(1 for k in kpis if k.target_reached)
    return round(reached / len(kpis) * 100, 1)


def compute_action_completion_rate(cycle: PDCACycle) -> float:
    actions = list(cycle.actions.all())
    if not actions:
        return 0.0
    done = sum(1 for a in actions if a.status == 'done')
    return round(done / len(actions) * 100, 1)
