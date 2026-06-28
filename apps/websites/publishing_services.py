"""
apps/websites/publishing_services.py — Services de publication de sites
"""
from django.utils import timezone


def check_website_ready_to_publish(website) -> dict:
    """
    Vérifie si un site est prêt à être publié.
    Retourne dict avec 'ready': bool et 'checklist': list of checks.
    """
    checklist = []
    is_ecommerce = website.site_type == 'ecommerce'

    def chk(key, label, condition, critical=True, fix_url='', advice=''):
        checklist.append({
            'key': key, 'label': label,
            'ok': bool(condition), 'critical': critical,
            'fix_url': fix_url, 'advice': advice,
        })

    chk('name', 'Nom du site renseigné', website.name)
    chk('logo', 'Logo ajouté', website.logo, critical=False,
        advice='Ajoutez un logo pour une image professionnelle.')
    chk('theme', 'Thème configuré', website.theme, critical=False,
        advice='Choisissez un thème pour personnaliser l\'apparence.')

    homepage = website.pages.filter(is_homepage=True, status='published').first()
    if not homepage:
        homepage = website.pages.filter(page_type='home', status='published').first()
    chk('homepage', 'Page d\'accueil créée et publiée', homepage,
        fix_url='', advice='Créez une page d\'accueil publiée.')

    published_pages = website.pages.filter(status='published').count()
    chk('published_pages', 'Au moins une page publiée', published_pages > 0)

    has_menu = website.menus.filter(is_active=True).exists()
    chk('menu', 'Menu principal configuré', has_menu, critical=False,
        advice='Ajoutez un menu de navigation.')

    has_domain = website.domains.filter(status__in=['active', 'dns_verified']).exists()
    chk('domain', 'Domaine configuré', has_domain, critical=False,
        advice='Connectez un domaine ou sous-domaine.')

    has_seo = bool(website.meta_title and website.meta_description)
    chk('seo', 'SEO global renseigné (titre + description)', has_seo, critical=False,
        advice='Renseignez le titre et la description SEO globale.')

    has_legal = website.pages.filter(page_type='legal', status='published').exists()
    chk('legal', 'Mentions légales créées', has_legal, critical=False,
        advice='Ajoutez une page de mentions légales.')

    has_privacy = website.pages.filter(page_type='privacy', status='published').exists()
    chk('privacy', 'Politique de confidentialité créée', has_privacy, critical=False,
        advice='Ajoutez une politique de confidentialité.')

    if is_ecommerce:
        has_cgv = website.pages.filter(
            status='published', title__icontains='conditions'
        ).exists()
        chk('cgv', 'CGV créées (boutique)', has_cgv, critical=True,
            advice='Les CGV sont obligatoires pour une boutique en ligne.')
        has_products = website.store_products.filter(status='published').exists()
        chk('products', 'Produits publiés (boutique)', has_products, critical=False,
            advice='Ajoutez au moins un produit publié à votre boutique.')

    critical_checks = [c for c in checklist if c['critical']]
    ready = all(c['ok'] for c in critical_checks)
    return {
        'ready': ready,
        'checklist': checklist,
        'ok_count': sum(1 for c in checklist if c['ok']),
        'total_count': len(checklist),
        'critical_blocking': [c for c in critical_checks if not c['ok']],
    }


def publish_website(website) -> dict:
    """Publie un site web. Retourne dict avec 'success' et 'errors'."""
    check = check_website_ready_to_publish(website)
    if not check['ready']:
        return {
            'success': False,
            'errors': [c['label'] for c in check['critical_blocking']],
        }
    website.status = 'published'
    website.is_published = True
    website.is_active = True
    website.published_at = timezone.now()
    website.maintenance_mode = False
    website.save(update_fields=['status', 'is_published', 'is_active', 'published_at', 'maintenance_mode'])
    return {'success': True, 'errors': []}


def unpublish_website(website) -> None:
    """Dépublie un site web."""
    website.status = 'unpublished'
    website.is_published = False
    website.is_active = False
    website.unpublished_at = timezone.now()
    website.save(update_fields=['status', 'is_published', 'is_active', 'unpublished_at'])


def publish_page(page) -> None:
    """Publie une page."""
    page.status = 'published'
    page.published_at = timezone.now()
    page.save(update_fields=['status', 'published_at'])


def unpublish_page(page) -> None:
    """Dépublie une page."""
    page.status = 'draft'
    page.save(update_fields=['status'])


def generate_public_urls(website) -> list:
    """Retourne la liste des URLs publiques d'un site."""
    urls = []
    primary = website.domains.filter(is_primary=True, dns_verified=True).first()
    base = f'https://{primary.domain}' if primary else ''
    for page in website.pages.filter(status='published'):
        slug = '' if page.is_homepage else f'{page.slug}/'
        urls.append(f'{base}/{slug}')
    return urls


def clear_website_cache(website) -> None:
    """Vide le cache du site (placeholder pour future implémentation)."""
    from django.core.cache import cache
    pattern = f'website_{website.pk}_*'
    # Simple cache clear — pour une vraie implémentation, utiliser cache.delete_pattern
    pass
