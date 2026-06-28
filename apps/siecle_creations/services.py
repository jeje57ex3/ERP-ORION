from django.utils import timezone
from .models import Creation, CreationOrder


def create_creation(company, reference, title, category, *, price_ht=0, price_ttc=0,
                    description='', materials='', stock_qty=0, tags=None,
                    is_limited_edition=False, limited_qty=None, created_by=None):
    return Creation.objects.create(
        company=company, brand_key='siecle',
        reference=reference, title=title, category=category,
        price_ht=price_ht, price_ttc=price_ttc,
        description=description, materials=materials,
        stock_qty=stock_qty, tags=tags or [],
        is_limited_edition=is_limited_edition, limited_qty=limited_qty,
        created_by=created_by,
    )


def publish_creation(creation):
    creation.status = 'published'
    creation.published_at = timezone.now()
    creation.save(update_fields=['status', 'published_at'])
    return creation


def archive_creation(creation):
    creation.status = 'archived'
    creation.save(update_fields=['status'])
    return creation


def update_stock(creation, qty_delta):
    creation.stock_qty = max(0, creation.stock_qty + qty_delta)
    if creation.stock_qty == 0:
        creation.status = 'sold_out'
    creation.save(update_fields=['stock_qty', 'status'])
    return creation


def create_order(company, creation, customer, quantity=1, *, personalization='',
                 shipping_address='', notes='', created_by=None):
    unit_price = creation.price_ttc
    order = CreationOrder.objects.create(
        company=company, brand_key='siecle',
        creation=creation, customer=customer,
        quantity=quantity, unit_price=unit_price,
        total_price=unit_price * quantity,
        personalization=personalization,
        shipping_address=shipping_address,
        notes=notes, created_by=created_by,
    )
    update_stock(creation, -quantity)
    return order


def get_catalog(company, *, category=None, status='published', brand_key='siecle'):
    qs = Creation.objects.filter(company=company, brand_key=brand_key)
    if status:
        qs = qs.filter(status=status)
    if category:
        qs = qs.filter(category=category)
    return qs.order_by('-published_at', '-created_at')


def get_creation_stats(company):
    qs = Creation.objects.filter(company=company, brand_key='siecle')
    orders = CreationOrder.objects.filter(company=company, brand_key='siecle')
    from django.db.models import Sum
    return {
        'total_creations': qs.count(),
        'published': qs.filter(status='published').count(),
        'sold_out': qs.filter(status='sold_out').count(),
        'total_orders': orders.count(),
        'pending_orders': orders.filter(status='pending').count(),
        'revenue': float(orders.exclude(status='cancelled').aggregate(
            t=Sum('total_price'))['t'] or 0),
    }
