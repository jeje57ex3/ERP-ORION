"""
apps/inventory/services.py — Opérations de stock atomiques et sécurisées

Règles :
  - Impossible de sortir plus que le stock disponible (sauf allow_negative=True)
  - Chaque mouvement est tracé dans StockMovement
  - Un transfert crée deux mouvements (sortie + entrée) dans la même transaction
  - Un ajustement d'inventaire est audité
"""
import logging
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError

logger = logging.getLogger('orion')


def create_stock_movement(
    *,
    company,
    product,
    movement_type: str,
    quantity: Decimal,
    from_location=None,
    to_location=None,
    reference: str = '',
    notes: str = '',
    lot_number: str = '',
    unit_cost: Decimal = None,
    user=None,
    allow_negative: bool = False,
):
    """
    Crée un mouvement de stock de façon atomique et sécurisée.

    Args:
        company:        entreprise
        product:        instance Product
        movement_type:  'in'|'out'|'transfer'|'adjustment'|'return'|'loss'
        quantity:       quantité (toujours positive)
        from_location:  emplacement source (pour out/transfer)
        to_location:    emplacement destination (pour in/transfer)
        reference:      numéro de document source
        notes:          commentaire
        lot_number:     numéro de lot
        unit_cost:      coût unitaire
        user:           utilisateur créateur
        allow_negative: autoriser le stock négatif (False par défaut)

    Returns:
        StockMovement ou tuple (StockMovement, StockMovement) pour un transfert
    """
    from apps.inventory.models import StockMovement, Product

    quantity = Decimal(str(quantity))
    if quantity <= 0:
        raise ValidationError("La quantité doit être strictement positive.")

    with transaction.atomic():
        # Verrouiller le produit pour lecture exclusive
        product_locked = Product.objects.select_for_update().get(pk=product.pk)

        if movement_type == 'transfer':
            return _do_transfer(
                company, product_locked, quantity, from_location, to_location,
                reference, notes, lot_number, unit_cost, user, allow_negative
            )

        if movement_type in ('out', 'loss'):
            _check_stock(product_locked, quantity, allow_negative)

        movement = StockMovement.objects.create(
            company=company,
            product=product_locked,
            movement_type=movement_type,
            quantity=quantity,
            from_location=from_location,
            to_location=to_location,
            reference=reference,
            notes=notes,
            lot_number=lot_number,
            unit_cost=unit_cost,
            created_by=user,
        )

        # Mise à jour quantité
        if movement_type in ('in', 'return'):
            Product.objects.filter(pk=product.pk).update(
                stock_quantity=models_F('stock_quantity') + quantity
            )
        elif movement_type in ('out', 'loss'):
            Product.objects.filter(pk=product.pk).update(
                stock_quantity=models_F('stock_quantity') - quantity
            )
        elif movement_type == 'adjustment':
            Product.objects.filter(pk=product.pk).update(stock_quantity=quantity)

        logger.info(
            "Mouvement stock: %s x%s %s [%s] ref=%s",
            movement_type, quantity, product_locked.name, company.name, reference
        )
        return movement


def _do_transfer(company, product, quantity, from_loc, to_loc, reference, notes, lot, cost, user, allow_negative):
    """Crée une sortie + une entrée dans la même transaction."""
    from apps.inventory.models import StockMovement

    _check_stock(product, quantity, allow_negative)

    out = StockMovement.objects.create(
        company=company, product=product, movement_type='out',
        quantity=quantity, from_location=from_loc,
        reference=reference, notes=f'Transfert vers {to_loc}. {notes}',
        lot_number=lot, unit_cost=cost, created_by=user,
    )
    inp = StockMovement.objects.create(
        company=company, product=product, movement_type='in',
        quantity=quantity, to_location=to_loc,
        reference=reference, notes=f'Transfert depuis {from_loc}. {notes}',
        lot_number=lot, unit_cost=cost, created_by=user,
    )
    # Stock net reste identique pour un transfert
    return out, inp


def _check_stock(product, quantity: Decimal, allow_negative: bool):
    """Lève ValidationError si le stock est insuffisant."""
    if not product.track_inventory:
        return
    if not allow_negative and product.stock_quantity < quantity:
        raise ValidationError(
            f"Stock insuffisant pour '{product.name}'. "
            f"Disponible: {product.stock_quantity} {product.unit}, "
            f"demandé: {quantity} {product.unit}."
        )


def models_F(field):
    """Raccourci pour django.db.models.F."""
    from django.db.models import F
    return F(field)


def get_stock_summary(company, product):
    """Retourne un résumé des mouvements de stock d'un produit."""
    from apps.inventory.models import StockMovement
    from django.db.models import Sum

    movements = StockMovement.objects.filter(company=company, product=product)
    return {
        'total_in': movements.filter(movement_type__in=('in', 'return')).aggregate(
            s=Sum('quantity'))['s'] or Decimal(0),
        'total_out': movements.filter(movement_type__in=('out', 'loss')).aggregate(
            s=Sum('quantity'))['s'] or Decimal(0),
        'total_adjustments': movements.filter(movement_type='adjustment').count(),
        'current_qty': product.stock_quantity,
    }
