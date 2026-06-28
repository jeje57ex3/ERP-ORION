"""
competitor_intelligence/services/price_tracker.py
Suivi légal des prix concurrents — saisie manuelle, CSV, APIs autorisées.
"""
from decimal import Decimal


def update_price_history(product, new_price, old_price=None, availability='unknown'):
    """Enregistre un nouveau prix dans l'historique."""
    from apps.competitor_intelligence.models import CompetitorPriceHistory
    record = CompetitorPriceHistory.objects.create(
        company=product.company,
        competitor_product=product,
        price=new_price,
        old_price=old_price or product.old_price,
        currency=product.currency,
        availability=availability,
    )
    discount = None
    if old_price and old_price > 0 and new_price < old_price:
        discount = round((1 - float(new_price) / float(old_price)) * 100, 2)
    record.discount_percent = discount
    record.save(update_fields=['discount_percent'])
    return record


def detect_price_change(product, new_price):
    """Détecte si le prix a changé et crée une alerte si nécessaire."""
    from apps.competitor_intelligence.services.alert_service import (
        create_price_drop_alert, create_price_increase_alert,
    )
    if not product.price:
        return None

    old_price = product.price
    new_price = Decimal(str(new_price))

    if new_price < old_price:
        return create_price_drop_alert(product, old_price, new_price)
    elif new_price > old_price:
        return create_price_increase_alert(product, old_price, new_price)
    return None


def calculate_price_index(company, category=None):
    """
    Calcule l'indice prix : rapport entre nos prix et ceux des concurrents.
    Retourne un dict avec les métriques.
    """
    from apps.competitor_intelligence.models import CompetitorProduct
    from apps.inventory.models import Product as OurProduct
    from django.db.models import Avg

    qs = CompetitorProduct.objects.filter(
        company=company, is_active=True, price__isnull=False,
    )
    if category:
        qs = qs.filter(category__icontains=category)

    competitor_avg = qs.aggregate(avg=Avg('price'))['avg']

    our_avg = None
    try:
        our_qs = OurProduct.objects.filter(company=company, is_active=True)
        if category:
            our_qs = our_qs.filter(category__name__icontains=category)
        our_avg = our_qs.aggregate(avg=Avg('price'))['avg']
    except Exception:
        pass

    gap_percent = None
    if our_avg and competitor_avg and competitor_avg > 0:
        gap_percent = round((float(our_avg) - float(competitor_avg)) / float(competitor_avg) * 100, 1)

    position = None
    if gap_percent is not None:
        if gap_percent < -5:
            position = 'plus_competitif'
        elif gap_percent > 5:
            position = 'plus_cher'
        else:
            position = 'equivalent'

    return {
        'our_avg':          our_avg,
        'competitor_avg':   competitor_avg,
        'gap_percent':      gap_percent,
        'position':         position,
        'products_tracked': qs.count(),
    }


def compare_our_prices_with_competitors(company, category=None):
    """Retourne une liste comparative produit par produit."""
    from apps.competitor_intelligence.models import CompetitorProduct
    qs = CompetitorProduct.objects.filter(
        company=company, is_active=True, price__isnull=False,
    ).select_related('competitor')
    if category:
        qs = qs.filter(category__icontains=category)
    return list(qs.values(
        'name', 'category', 'price', 'currency',
        'competitor__name', 'discount_percent',
    ))
