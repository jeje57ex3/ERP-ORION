"""
apps/competitor_intelligence/tasks.py — Tâches Celery analyse concurrentielle
Requiert Celery + Redis. Méthodes légales uniquement.
"""
try:
    from celery import shared_task
except ImportError:
    def shared_task(fn=None, **kwargs):
        if fn:
            return fn
        def decorator(f):
            return f
        return decorator


@shared_task
def scan_competitor_site(site_id):
    """Scan légal d'un site concurrent (respecte robots.txt)."""
    from apps.competitor_intelligence.models import CompetitorSite
    from apps.competitor_intelligence.services.competitor_service import scan_public_product_page
    from django.utils import timezone

    try:
        site = CompetitorSite.objects.get(pk=site_id)
        if not site.tracking_enabled:
            return 'Tracking désactivé'
        result = scan_public_product_page(site.site_url)
        site.last_scan_at = timezone.now()
        site.status = 'active' if result.get('accessible') else 'error'
        site.save(update_fields=['last_scan_at', 'status'])
        return f'Site {site.site_url}: {site.status}'
    except Exception as e:
        return f'Erreur: {e}'


@shared_task
def scan_all_active_competitors(company_id):
    """Scanne tous les sites des concurrents actifs d'une entreprise."""
    from apps.core.models import Company
    from apps.competitor_intelligence.models import CompetitorSite

    try:
        company = Company.objects.get(pk=company_id)
        sites   = CompetitorSite.objects.filter(
            competitor__company=company,
            tracking_enabled=True,
        ).exclude(scan_frequency='manual')

        results = []
        for site in sites:
            scan_competitor_site.delay(site.pk)
            results.append(f'{site.competitor.name}: {site.site_url}')
        return results
    except Exception as e:
        return f'Erreur: {e}'


@shared_task
def update_competitor_price_history(product_id):
    """Met à jour l'historique des prix d'un produit concurrent."""
    from apps.competitor_intelligence.models import CompetitorProduct
    from apps.competitor_intelligence.services.price_tracker import update_price_history

    try:
        product = CompetitorProduct.objects.get(pk=product_id)
        if product.price:
            update_price_history(product, product.price)
        return f'OK: {product.name}'
    except Exception as e:
        return f'Erreur: {e}'


@shared_task
def generate_weekly_competitor_report(company_id):
    """Génère et envoie le rapport hebdomadaire concurrentiel."""
    from apps.core.models import Company
    from apps.competitor_intelligence.models import Competitor
    from apps.competitor_intelligence.services.report_service import generate_competitor_excel_report

    try:
        company = Company.objects.get(pk=company_id)
        competitor_ids = list(Competitor.objects.filter(company=company, is_active=True).values_list('pk', flat=True))
        if not competitor_ids:
            return 'Aucun concurrent'
        buf = generate_competitor_excel_report(company, competitor_ids)
        return f'Rapport généré: {len(buf.getvalue())} octets'
    except Exception as e:
        return f'Erreur: {e}'
