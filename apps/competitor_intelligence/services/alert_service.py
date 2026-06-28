"""
competitor_intelligence/services/alert_service.py
Génération et notification des alertes concurrentielles.
"""


def _create_alert(company, competitor, alert_type, title, message, severity='medium'):
    from apps.competitor_intelligence.models import CompetitorAlert
    return CompetitorAlert.objects.create(
        company=company,
        competitor=competitor,
        alert_type=alert_type,
        title=title,
        message=message,
        severity=severity,
    )


def create_price_drop_alert(product, old_price, new_price):
    pct = round((float(old_price) - float(new_price)) / float(old_price) * 100, 1)
    severity = 'high' if pct >= 20 else 'medium'
    return _create_alert(
        company=product.company,
        competitor=product.competitor,
        alert_type='price_drop',
        title=f'Baisse de prix : {product.name}',
        message=f'{product.competitor.name} a baissé le prix de "{product.name}" de {old_price} € à {new_price} € (-{pct}%).',
        severity=severity,
    )


def create_price_increase_alert(product, old_price, new_price):
    pct = round((float(new_price) - float(old_price)) / float(old_price) * 100, 1)
    return _create_alert(
        company=product.company,
        competitor=product.competitor,
        alert_type='price_increase',
        title=f'Hausse de prix : {product.name}',
        message=f'{product.competitor.name} a augmenté le prix de "{product.name}" de {old_price} € à {new_price} € (+{pct}%).',
        severity='low',
    )


def create_new_product_alert(competitor, product):
    return _create_alert(
        company=product.company,
        competitor=competitor,
        alert_type='new_product',
        title=f'Nouveau produit : {product.name}',
        message=f'{competitor.name} propose un nouveau produit : "{product.name}" ({product.category}).',
        severity='medium',
    )


def create_promotion_alert(product):
    return _create_alert(
        company=product.company,
        competitor=product.competitor,
        alert_type='new_promotion',
        title=f'Promotion : {product.name}',
        message=f'{product.competitor.name} a une promotion sur "{product.name}" : {product.discount_percent}% de remise.',
        severity='high',
    )


def create_traffic_change_alert(competitor, company, old_value, new_value):
    if old_value and old_value > 0:
        pct = round((new_value - old_value) / old_value * 100, 1)
        direction = 'hausse' if pct > 0 else 'baisse'
        severity  = 'high' if abs(pct) > 20 else 'medium'
        return _create_alert(
            company=company,
            competitor=competitor,
            alert_type='traffic_change',
            title=f'Changement trafic estimé : {competitor.name}',
            message=f'Le trafic estimé de {competitor.name} a varié de {abs(pct)}% ({direction}). '
                    f'Ancien: ~{old_value:,} / Nouveau: ~{new_value:,} visiteurs/mois (estimés).',
            severity=severity,
        )
    return None


def notify_competitor_alert(alert):
    """Envoie une notification ERP pour une alerte concurrentielle."""
    try:
        from apps.notifications.models import Notification
        from django.contrib.auth.models import User

        admins = User.objects.filter(is_staff=True, is_active=True)
        for user in admins:
            Notification.objects.create(
                user=user,
                company=alert.company,
                title=alert.title,
                message=alert.message,
                notification_type='competitor_alert',
            )
    except Exception:
        pass
