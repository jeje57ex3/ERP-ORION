"""
apps/websites/seo_services.py — Services SEO pour les sites web
"""
import re
from django.utils.html import strip_tags


def calculate_seo_score(page) -> dict:
    """Calcule un score SEO simple pour une page. Retourne dict avec score et détails."""
    checks = []
    score = 0
    max_score = 100

    def check(name, condition, points, advice=''):
        nonlocal score
        ok = bool(condition)
        if ok:
            score += points
        checks.append({'name': name, 'ok': ok, 'points': points, 'advice': advice})

    check('Meta title présent', page.meta_title, 15,
          'Ajoutez un meta title entre 30 et 70 caractères.')
    check('Meta title longueur optimale',
          page.meta_title and 30 <= len(page.meta_title) <= 70, 10,
          'Le meta title doit faire entre 30 et 70 caractères.')
    check('Meta description présente', page.meta_description, 15,
          'Ajoutez une meta description entre 100 et 160 caractères.')
    check('Meta description longueur optimale',
          page.meta_description and 100 <= len(page.meta_description) <= 160, 10,
          'La meta description doit faire entre 100 et 160 caractères.')
    check('Slug propre (sans espaces ni accents)',
          page.slug and re.match(r'^[a-z0-9-]+$', page.slug), 10,
          'Utilisez uniquement des lettres minuscules, chiffres et tirets.')
    text = strip_tags(page.content or '')
    check('Contenu suffisant (>200 caractères)', len(text) >= 200, 20,
          'La page devrait contenir au moins 200 caractères de contenu.')
    check('Page indexable', page.is_indexable, 10,
          'Activez l\'indexation pour que cette page apparaisse dans Google.')
    check('Titre de page présent', bool(page.title), 10,
          'Ajoutez un titre à la page.')

    return {
        'score': min(score, max_score),
        'max_score': max_score,
        'percentage': min(int(score / max_score * 100), 100),
        'checks': checks,
        'grade': _grade(score, max_score),
    }


def _grade(score, max_score):
    pct = score / max_score * 100
    if pct >= 80:
        return 'A'
    if pct >= 60:
        return 'B'
    if pct >= 40:
        return 'C'
    return 'D'


def generate_meta_preview(page) -> dict:
    """Génère un aperçu Google pour une page."""
    title = page.meta_title or page.title or 'Sans titre'
    description = page.meta_description or ''
    url = page.canonical_url or f'/{page.slug}/'
    return {
        'title': title[:60],
        'description': description[:160],
        'url': url,
        'title_warning': len(title) > 60,
        'description_warning': len(description) > 160,
    }


def check_missing_meta(page) -> list:
    """Retourne la liste des métadonnées manquantes pour une page."""
    missing = []
    if not page.meta_title:
        missing.append('meta_title')
    if not page.meta_description:
        missing.append('meta_description')
    if not page.slug:
        missing.append('slug')
    return missing


def generate_sitemap_xml(website) -> str:
    """Génère le contenu XML du sitemap pour un site."""
    from django.utils import timezone
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']

    base_url = ''
    primary = website.domains.filter(is_primary=True, dns_verified=True).first()
    if primary:
        base_url = f'https://{primary.domain}'

    pages = website.pages.filter(status='published', is_indexable=True)
    for page in pages:
        lines.append(f'  <url>')
        lines.append(f'    <loc>{base_url}/{page.slug}/</loc>')
        if page.updated_at:
            lines.append(f'    <lastmod>{page.updated_at.strftime("%Y-%m-%d")}</lastmod>')
        lines.append(f'    <changefreq>weekly</changefreq>')
        prio = '1.0' if page.is_homepage else '0.8'
        lines.append(f'    <priority>{prio}</priority>')
        lines.append(f'  </url>')

    posts = website.blog_posts.filter(status='published', is_indexable=True)
    for post in posts:
        lines.append(f'  <url>')
        lines.append(f'    <loc>{base_url}/blog/{post.slug}/</loc>')
        if post.published_at:
            lines.append(f'    <lastmod>{post.published_at.strftime("%Y-%m-%d")}</lastmod>')
        lines.append(f'    <changefreq>monthly</changefreq>')
        lines.append(f'    <priority>0.6</priority>')
        lines.append(f'  </url>')

    lines.append('</urlset>')
    return '\n'.join(lines)


def generate_robots_txt(website) -> str:
    """Génère le contenu du fichier robots.txt pour un site."""
    lines = ['User-agent: *']
    if website.is_published and website.status == 'published':
        lines.append('Allow: /')
        lines.append('')
        base = ''
        primary = website.domains.filter(is_primary=True, dns_verified=True).first()
        if primary:
            base = f'https://{primary.domain}'
        if base:
            lines.append(f'Sitemap: {base}/sitemap.xml')
    else:
        lines.append('Disallow: /')
    return '\n'.join(lines)


def get_canonical_url(page) -> str:
    """Retourne l'URL canonique d'une page."""
    if page.canonical_url:
        return page.canonical_url
    primary = page.website.domains.filter(is_primary=True, dns_verified=True).first()
    if primary:
        slug = '' if page.is_homepage else f'{page.slug}/'
        return f'https://{primary.domain}/{slug}'
    return f'/{page.slug}/'
