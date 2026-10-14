from django.utils import timezone

from apps.orion_ai.tool_registry import register_ai_tool


@register_ai_tool(
    name='get_erp_summary',
    description='Retourne un résumé général de l\'état de l\'ERP : commandes récentes, alertes, santé système.',
    is_write_action=False,
)
def get_erp_summary(*, company, user, **kwargs):
    summary = {
        'company': str(company) if company else None,
        'timestamp': timezone.now().isoformat(),
    }

    try:
        from apps.crm.models import Customer
        summary['clients_total'] = Customer.objects.filter(company=company).count()
    except Exception:
        summary['clients_total'] = None

    try:
        from apps.orders.models import WebOrder
        summary['commandes_recentes'] = WebOrder.objects.filter(company=company).count()
    except Exception:
        try:
            from apps.ecommerce.models import Order
            summary['commandes_recentes'] = Order.objects.filter(company=company).count()
        except Exception:
            summary['commandes_recentes'] = None

    return {'ok': True, 'summary': summary}


@register_ai_tool(
    name='get_shop_status',
    description='Récupère l\'état des boutiques SIÈCLE / LUNEA (activées, paiements, maintenance).',
    is_write_action=False,
)
def get_shop_status(*, company, user, brand_key=None, **kwargs):
    try:
        from apps.website_shop_settings.models import WebsiteShopSettings
        qs = WebsiteShopSettings.objects.filter(company=company)
        if brand_key:
            qs = qs.filter(brand_key=brand_key)

        results = []
        for shop in qs:
            results.append({
                'brand_key': shop.brand_key,
                'site_name': getattr(shop, 'site_name', ''),
                'is_site_enabled': getattr(shop, 'is_site_enabled', None),
                'is_shop_enabled': getattr(shop, 'is_shop_enabled', None),
            })

        return {'ok': True, 'shops': results}
    except Exception as exc:
        return {'ok': False, 'error': str(exc)}


@register_ai_tool(
    name='get_recent_orders',
    description='Liste les commandes récentes avec statut, montant et date.',
    is_write_action=False,
)
def get_recent_orders(*, company, user, brand_key=None, limit=10, **kwargs):
    results = []

    try:
        from apps.ecommerce.models import Order
        qs = Order.objects.filter(company=company).order_by('-created_at')
        if brand_key:
            qs = qs.filter(brand_key=brand_key)
        for order in qs[:int(limit)]:
            results.append({
                'id': order.id,
                'status': getattr(order, 'status', ''),
                'total': str(getattr(order, 'total', '')),
                'created_at': order.created_at.isoformat() if getattr(order, 'created_at', None) else '',
            })
    except Exception:
        pass

    return {'ok': True, 'orders': results, 'count': len(results)}


@register_ai_tool(
    name='get_system_health_summary',
    description='Récupère le dernier diagnostic santé système Orion.',
    is_write_action=False,
)
def get_system_health_summary(*, company, user, **kwargs):
    try:
        from apps.system_health.models import HealthScan, HealthIssue

        latest_scan = HealthScan.objects.first()
        open_issues = list(HealthIssue.objects.filter(status='open')[:20])

        return {
            'ok': True,
            'latest_scan': {
                'id': latest_scan.id if latest_scan else None,
                'status': latest_scan.status if latest_scan else 'none',
                'summary': getattr(latest_scan, 'summary', '') if latest_scan else '',
            },
            'open_issues_count': len(open_issues),
            'open_issues': [
                {
                    'id': issue.id,
                    'code': getattr(issue, 'code', ''),
                    'title': getattr(issue, 'title', ''),
                    'severity': getattr(issue, 'severity', ''),
                }
                for issue in open_issues
            ],
        }
    except Exception as exc:
        return {'ok': False, 'error': str(exc), 'message': 'Module system_health non disponible.'}


@register_ai_tool(
    name='get_crm_stats',
    description='Récupère les statistiques clients CRM : total, récents, top clients.',
    is_write_action=False,
)
def get_crm_stats(*, company, user, **kwargs):
    try:
        from apps.crm.models import Customer

        qs = Customer.objects.filter(company=company)
        total = qs.count()
        recent = list(qs.order_by('-created_at')[:5])

        return {
            'ok': True,
            'total_clients': total,
            'recent_clients': [
                {
                    'id': c.id,
                    'name': str(c),
                    'created_at': c.created_at.isoformat() if getattr(c, 'created_at', None) else '',
                }
                for c in recent
            ],
        }
    except Exception as exc:
        return {'ok': False, 'error': str(exc)}


@register_ai_tool(
    name='get_inventory_alerts',
    description='Liste les produits en rupture de stock ou en alerte de stock bas.',
    is_write_action=False,
)
def get_inventory_alerts(*, company, user, **kwargs):
    try:
        from apps.inventory.models import Product

        qs = Product.objects.filter(company=company)
        low_stock = []

        for product in qs:
            stock = getattr(product, 'stock_quantity', None)
            threshold = getattr(product, 'stock_alert_threshold', 5)
            if stock is not None and stock <= threshold:
                low_stock.append({
                    'id': product.id,
                    'name': str(product),
                    'stock': stock,
                    'threshold': threshold,
                })

        return {'ok': True, 'low_stock_products': low_stock, 'count': len(low_stock)}
    except Exception as exc:
        return {'ok': False, 'error': str(exc)}


@register_ai_tool(
    name='get_stripe_config_status',
    description='Vérifie si Stripe est configuré (sans révéler les clés).',
    is_write_action=False,
)
def get_stripe_config_status(*, company, user, brand_key=None, **kwargs):
    from django.conf import settings as dj_settings

    has_secret = bool(getattr(dj_settings, 'STRIPE_SECRET_KEY', ''))
    has_public = bool(getattr(dj_settings, 'STRIPE_PUBLIC_KEY', ''))
    has_webhook = bool(getattr(dj_settings, 'STRIPE_WEBHOOK_SECRET', ''))

    return {
        'ok': True,
        'stripe_secret_configured': has_secret,
        'stripe_public_configured': has_public,
        'stripe_webhook_configured': has_webhook,
        'all_configured': has_secret and has_public and has_webhook,
        'note': 'Les clés ne sont jamais exposées. Seul leur statut est indiqué.',
    }


@register_ai_tool(
    name='create_order_note',
    description='Ajoute une note interne sur une commande existante.',
    is_write_action=True,
    is_dangerous_action=False,
)
def create_order_note(*, company, user, order_id, note, **kwargs):
    try:
        from apps.ecommerce.models import Order

        order = Order.objects.get(company=company, id=order_id)
        existing = getattr(order, 'internal_notes', '') or ''
        order.internal_notes = existing + f'\n[{timezone.now().strftime("%d/%m/%Y %H:%M")}] {note}'
        order.save(update_fields=['internal_notes'])

        return {'ok': True, 'message': 'Note ajoutée à la commande.', 'order_id': order.id}
    except Exception as exc:
        return {'ok': False, 'error': str(exc)}


@register_ai_tool(
    name='update_shop_maintenance',
    description='Active ou désactive le mode maintenance d\'une boutique.',
    is_write_action=True,
    is_dangerous_action=True,
)
def update_shop_maintenance(*, company, user, brand_key, enabled, message='', **kwargs):
    try:
        from apps.website_shop_settings.models import WebsiteShopSettings

        shop = WebsiteShopSettings.objects.get(company=company, brand_key=brand_key)
        maintenance = shop.maintenance_settings
        maintenance.maintenance_enabled = bool(enabled)
        if message:
            maintenance.maintenance_message = message
        maintenance.save()

        return {
            'ok': True,
            'brand_key': brand_key,
            'maintenance_enabled': maintenance.maintenance_enabled,
        }
    except Exception as exc:
        return {'ok': False, 'error': str(exc)}


# ─── Guidage dans l'interface ────────────────────────────────────────────────
# Ces outils lisent la navigation et la documentation, jamais les donnees
# metier : ils n'ont donc aucun besoin du contexte d'entreprise, et sont sans
# risque. Ils sont enregistres comme les autres pour apparaitre dans
# l'inventaire des capacites et rester appelables explicitement, mais le fil
# de conversation s'appuie surtout sur la recherche deterministe faite avant
# l'appel au modele (voir knowledge.contexte_pour_question).

@register_ai_tool(
    name='trouver_page',
    description="Trouve les pages du menu correspondant a une question, avec leur adresse reelle.",
    is_write_action=False,
)
def trouver_page(*, company, user, question='', **kwargs):
    from apps.orion_ai.knowledge import chercher_pages

    pages = chercher_pages(question)
    return {
        'question': question,
        'nombre': len(pages),
        'pages': [
            {'libelle': p['libelle'], 'module': p['module'], 'adresse': p['url']}
            for p in pages
        ],
    }


@register_ai_tool(
    name='lister_modules_interface',
    description="Liste les modules du menu et leurs pages, tels que l'interface les affiche.",
    is_write_action=False,
)
def lister_modules_interface(*, company, user, **kwargs):
    from apps.orion_ai.knowledge import lister_modules

    modules = lister_modules()
    return {
        'nombre_modules': len(modules),
        'nombre_pages': sum(m['nombre'] for m in modules),
        'modules': modules,
    }


@register_ai_tool(
    name='chercher_documentation',
    description='Cherche une reponse dans la documentation versionnee avec cette version du code.',
    is_write_action=False,
)
def chercher_documentation_outil(*, company, user, question='', **kwargs):
    from apps.orion_ai.knowledge import chercher_documentation

    sections = chercher_documentation(question)
    return {
        'question': question,
        'nombre': len(sections),
        'sections': sections,
    }
