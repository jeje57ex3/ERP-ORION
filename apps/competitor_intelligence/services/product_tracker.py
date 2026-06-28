"""
competitor_intelligence/services/product_tracker.py
Suivi légal des produits concurrents.
Méthodes autorisées : saisie manuelle, import CSV, API publique.
"""
import csv
import io
from django.utils import timezone


def add_competitor_product_manually(company, competitor, data: dict):
    """Ajoute un produit concurrent via saisie manuelle."""
    from apps.competitor_intelligence.models import CompetitorProduct
    from apps.competitor_intelligence.services.price_tracker import update_price_history

    product = CompetitorProduct.objects.create(
        company=company,
        competitor=competitor,
        name=data.get('name', ''),
        brand=data.get('brand', ''),
        category=data.get('category', ''),
        product_url=data.get('product_url', ''),
        price=data.get('price'),
        currency=data.get('currency', 'EUR'),
        old_price=data.get('old_price'),
        availability=data.get('availability', 'unknown'),
        description=data.get('description', ''),
        last_checked_at=timezone.now(),
    )
    if product.price:
        update_price_history(product, product.price, old_price=product.old_price)
    return product


def import_competitor_products_from_csv(company, competitor, csv_content: str):
    """
    Importe des produits depuis un CSV.
    Colonnes attendues : name, brand, category, price, currency, old_price, availability, product_url
    """
    from apps.competitor_intelligence.models import CompetitorProduct
    from apps.competitor_intelligence.services.price_tracker import update_price_history

    reader = csv.DictReader(io.StringIO(csv_content))
    created, updated, errors = 0, 0, []

    for i, row in enumerate(reader, start=2):
        try:
            name = row.get('name', '').strip()
            if not name:
                continue
            price_str = row.get('price', '').strip()
            price = None
            if price_str:
                try:
                    price = float(price_str.replace(',', '.').replace('€', '').strip())
                except ValueError:
                    pass

            product, is_new = CompetitorProduct.objects.update_or_create(
                company=company,
                competitor=competitor,
                name=name,
                defaults={
                    'brand':        row.get('brand', '').strip(),
                    'category':     row.get('category', '').strip(),
                    'product_url':  row.get('product_url', '').strip(),
                    'price':        price,
                    'currency':     row.get('currency', 'EUR').strip() or 'EUR',
                    'availability': row.get('availability', 'unknown').strip() or 'unknown',
                    'last_checked_at': timezone.now(),
                },
            )
            if price:
                update_price_history(product, price)
            if is_new:
                created += 1
            else:
                updated += 1
        except Exception as e:
            errors.append(f'Ligne {i}: {e}')

    return {'created': created, 'updated': updated, 'errors': errors}


def detect_new_products(competitor):
    """
    Détecte les nouveaux produits en comparant à la liste précédente.
    Requiert que les produits aient été importés récemment.
    """
    from apps.competitor_intelligence.models import CompetitorProduct
    from django.utils import timezone
    from datetime import timedelta

    recent_cutoff = timezone.now() - timedelta(days=1)
    new_products = CompetitorProduct.objects.filter(
        competitor=competitor,
        detected_at__gte=recent_cutoff,
    )
    return list(new_products)


def calculate_product_gap(company, competitor):
    """
    Calcule l'écart de gamme entre nos produits et ceux du concurrent.
    Retourne les catégories absentes de notre catalogue.
    """
    from apps.competitor_intelligence.models import CompetitorProduct
    from apps.inventory.models import Product as OurProduct

    competitor_categories = set(
        CompetitorProduct.objects.filter(
            company=company, competitor=competitor, is_active=True,
        ).values_list('category', flat=True).distinct()
    )

    our_categories = set()
    try:
        our_categories = set(
            OurProduct.objects.filter(company=company, is_active=True)
            .values_list('category__name', flat=True).distinct()
        )
    except Exception:
        pass

    missing = competitor_categories - our_categories
    return {
        'competitor_categories':  sorted(competitor_categories),
        'our_categories':         sorted(our_categories),
        'missing_categories':     sorted(missing),
        'gap_count':              len(missing),
    }
