"""
competitor_intelligence/services/competitor_service.py
Service principal de gestion des concurrents.
"""


def create_competitor(company, name, website_url='', industry='', country='France', description='', created_by=None):
    from apps.competitor_intelligence.models import Competitor
    return Competitor.objects.create(
        company=company,
        name=name,
        website_url=website_url,
        industry=industry,
        country=country,
        description=description,
        created_by=created_by,
    )


def get_competitor_summary(competitor):
    """Retourne un résumé complet d'un concurrent."""
    from apps.competitor_intelligence.services.analysis_service import generate_competitor_score

    traffic = competitor.traffic_estimates.order_by('-measured_at').first()
    latest_alert = competitor.alerts.filter(is_read=False).order_by('-created_at').first()

    return {
        'competitor':        competitor,
        'score':             generate_competitor_score(competitor),
        'products_count':    competitor.products.filter(is_active=True).count(),
        'advantages_count':  competitor.advantages.count(),
        'alerts_count':      competitor.alerts.filter(is_read=False).count(),
        'latest_traffic':    traffic,
        'latest_alert':      latest_alert,
        'sites_count':       competitor.sites.count(),
    }


def scan_public_product_page(product_url: str) -> dict:
    """
    Tente de récupérer les informations publiques d'une page produit.
    Respecte robots.txt. Ne contourne aucune protection.
    Retourne un dict partiel ou vide si inaccessible.
    """
    import urllib.request
    import urllib.robotparser
    from urllib.parse import urlparse

    result = {'url': product_url, 'accessible': False, 'data': {}}

    try:
        parsed = urlparse(product_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(robots_url)
        rp.read()

        user_agent = 'OrionERP/1.0 (competitive-analysis; contact: admin@orion-erp.com)'
        if not rp.can_fetch(user_agent, product_url):
            result['accessible'] = False
            result['reason'] = 'robots.txt interdit l\'accès'
            return result

        req = urllib.request.Request(
            product_url,
            headers={'User-Agent': user_agent},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result['accessible'] = True
            result['status_code'] = resp.status

    except Exception as e:
        result['accessible'] = False
        result['reason'] = str(e)

    return result
