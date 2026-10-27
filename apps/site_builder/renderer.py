"""
apps/site_builder/renderer.py — Converts BuilderSection instances to HTML strings.
"""
import html as _html

from .models import BuilderSection
from .sanitize import (
    couleur,
    entier,
    longueur_css,
    url_dans_du_css,
    url_de_lien,
    url_de_media,
)


def _esc(value) -> str:
    return _html.escape(str(value or ''))


def _style(*parts) -> str:
    """Join non-empty CSS declarations."""
    return ';'.join(p for p in parts if p)


def render_section_html(section: BuilderSection, brand_key: str = '') -> str:
    s = section.settings or {}
    dispatch = {
        'hero':              _hero,
        'text_image':        _text_image,
        'full_image':        _full_image,
        'product_grid':      _product_grid,
        'collection_filter': _collection_filter,
        'gallery':           _gallery,
        'features':          _features,
        'cta':               _cta,
        'faq':               _faq,
        'spacer':            _spacer,
    }
    fn = dispatch.get(section.module_type, _unknown)
    return fn(s, brand_key)


# ──────────────────────────────────────────────────────────────────────────────

def _hero(s, brand_key):
    title    = s.get('title', 'Hero')
    subtitle = s.get('subtitle', '')
    cta_lbl  = s.get('cta_label', '')
    cta_url  = url_de_lien(s.get('cta_url'), '#')
    image    = url_dans_du_css(s.get('image'), '')
    opacity  = entier(s.get('overlay_opacity'), 50, 'overlay_opacity')
    bg       = couleur(s.get('bg_color'), '#0B0B0D')
    fg       = couleur(s.get('text_color'), '#F7F2E7')

    bg_img   = f"background-image:url('{_esc(image)}');background-size:cover;background-position:center;" if image else ''
    overlay  = f'<div style="position:absolute;inset:0;background:rgba(0,0,0,{opacity/100:.2f})"></div>' if image else ''

    return (
        f'<section class="pb-section pb-hero" style="{_style(f"background:{_esc(bg)}", bg_img, f"color:{_esc(fg)}", "position:relative;overflow:hidden;min-height:480px")}">'
        f'{overlay}'
        f'<div class="pb-container" style="position:relative;z-index:1;text-align:center;padding:6rem 1.5rem;">'
        f'<h1 style="font-size:2.8rem;font-weight:700;margin-bottom:1rem;line-height:1.15">{_esc(title)}</h1>'
        + (f'<p style="font-size:1.15rem;opacity:.85;margin-bottom:2rem;max-width:600px;margin-left:auto;margin-right:auto">{_esc(subtitle)}</p>' if subtitle else '')
        + (f'<a href="{_esc(cta_url)}" class="pb-btn pb-btn-primary">{_esc(cta_lbl)}</a>' if cta_lbl else '')
        + '</div></section>'
    )


def _text_image(s, brand_key):
    title      = s.get('title', 'Titre')
    body       = s.get('body', '')
    image      = url_de_media(s.get('image'), '')
    image_side = s.get('image_side', 'right')
    cta_lbl    = s.get('cta_label', '')
    cta_url    = url_de_lien(s.get('cta_url'), '#')
    bg         = couleur(s.get('bg_color'), '')
    fg         = couleur(s.get('text_color'), '')

    text_col = (
        f'<div class="pb-ti-text">'
        f'<h2 style="font-size:2rem;font-weight:700;margin-bottom:1rem">{_esc(title)}</h2>'
        f'<p style="opacity:.85;line-height:1.7">{_esc(body)}</p>'
        + (f'<a href="{_esc(cta_url)}" class="pb-btn pb-btn-primary" style="margin-top:1.5rem;display:inline-block">{_esc(cta_lbl)}</a>' if cta_lbl else '')
        + '</div>'
    )
    img_col = f'<div class="pb-ti-img"><img src="{_esc(image)}" alt="" style="width:100%;border-radius:12px;object-fit:cover;max-height:420px"></div>' if image else '<div class="pb-ti-img pb-ti-img-placeholder"><i class="bi bi-image" style="font-size:4rem;opacity:.2"></i></div>'

    cols = (img_col + text_col) if image_side == 'left' else (text_col + img_col)

    return (
        f'<section class="pb-section pb-text-image" style="{_style(f"background:{_esc(bg)}" if bg else "", f"color:{_esc(fg)}" if fg else "", "padding:4rem 1.5rem")}">'
        f'<div class="pb-container"><div class="pb-ti-grid">{cols}</div></div>'
        f'</section>'
    )


def _product_grid(s, brand_key):
    title    = s.get('title', 'Nos produits')
    count    = entier(s.get('count'), 8, 'count')
    cat_slug = s.get('category_slug', '')
    bg       = couleur(s.get('bg_color'), '')

    products = []
    if brand_key:
        try:
            from apps.ecommerce.public_selectors import get_public_products_for_site
            qs, _ = get_public_products_for_site(site_slug=brand_key, category_slug=cat_slug or None)
            products = list(qs[:count])
        except Exception:
            pass

    cards = ''
    for p in products:
        img_url = ''
        try:
            img_url = p.main_image.url if p.main_image else ''
        except Exception:
            pass
        price = getattr(p, 'price', '')
        cards += (
            f'<div class="pb-product-card">'
            + (f'<img src="{_esc(img_url)}" alt="{_esc(p.name)}" class="pb-product-img">' if img_url else '<div class="pb-product-img-ph"><i class="bi bi-image"></i></div>')
            + f'<div class="pb-product-info"><div class="pb-product-name">{_esc(p.name)}</div>'
            + (f'<div class="pb-product-price">{_esc(str(price))} €</div>' if price else '')
            + '</div></div>'
        )

    if not cards:
        cards = (
            ''.join(
                '<div class="pb-product-card pb-product-placeholder">'
                '<div class="pb-product-img-ph"><i class="bi bi-image"></i></div>'
                f'<div class="pb-product-info"><div class="pb-product-name">Produit {i+1}</div></div>'
                '</div>'
                for i in range(min(count, 4))
            )
        )

    return (
        f'<section class="pb-section pb-product-grid" style="{_style(f"background:{_esc(bg)}" if bg else "", "padding:4rem 1.5rem")}">'
        f'<div class="pb-container">'
        f'<h2 style="text-align:center;font-size:2rem;font-weight:700;margin-bottom:2.5rem">{_esc(title)}</h2>'
        f'<div class="pb-product-grid-inner">{cards}</div>'
        f'</div></section>'
    )


def _collection_filter(s, brand_key):
    title = s.get('title', 'Parcourir la collection')
    bg    = couleur(s.get('bg_color'), '')

    return (
        f'<section class="pb-section pb-collection-filter" style="{_style(f"background:{_esc(bg)}" if bg else "", "padding:2rem 1.5rem")}">'
        f'<div class="pb-container" style="text-align:center">'
        f'<h2 style="font-size:1.6rem;font-weight:700;margin-bottom:1.5rem">{_esc(title)}</h2>'
        f'<div class="pb-filter-chips">'
        f'<span class="pb-filter-chip active">Tous</span>'
        f'<span class="pb-filter-chip">Nouveautés</span>'
        f'<span class="pb-filter-chip">Meilleures ventes</span>'
        f'<span class="pb-filter-chip">Promotions</span>'
        f'</div></div></section>'
    )


def _gallery(s, brand_key):
    title   = s.get('title', 'Galerie')
    columns = entier(s.get('columns'), 3, 'columns')
    bg      = couleur(s.get('bg_color'), '')

    placeholders = ''.join(
        '<div class="pb-gallery-cell"><div class="pb-gallery-ph"><i class="bi bi-image"></i></div></div>'
        for _ in range(columns * 2)
    )

    return (
        f'<section class="pb-section pb-gallery" style="{_style(f"background:{_esc(bg)}" if bg else "", "padding:4rem 1.5rem")}">'
        f'<div class="pb-container">'
        f'<h2 style="text-align:center;font-size:2rem;font-weight:700;margin-bottom:2rem">{_esc(title)}</h2>'
        f'<div class="pb-gallery-grid" style="grid-template-columns:repeat({columns},1fr)">{placeholders}</div>'
        f'</div></section>'
    )


def _features(s, brand_key):
    title = s.get('title', 'Nos avantages')
    bg    = couleur(s.get('bg_color'), '')
    fg    = couleur(s.get('text_color'), '')

    default_items = [
        ('bi-gem',         'Qualité supérieure',  'Matériaux soigneusement sélectionnés.'),
        ('bi-truck',       'Livraison rapide',     'Expédié sous 24h ouvrées.'),
        ('bi-shield-check','Garantie 2 ans',       'Service après-vente réactif.'),
    ]
    items_html = ''.join(
        f'<div class="pb-feature-item">'
        f'<div class="pb-feature-icon"><i class="bi {icon}"></i></div>'
        f'<h3 class="pb-feature-title">{_esc(t)}</h3>'
        f'<p class="pb-feature-text">{_esc(d)}</p>'
        f'</div>'
        for icon, t, d in default_items
    )

    return (
        f'<section class="pb-section pb-features" style="{_style(f"background:{_esc(bg)}" if bg else "", f"color:{_esc(fg)}" if fg else "", "padding:4rem 1.5rem")}">'
        f'<div class="pb-container">'
        f'<h2 style="text-align:center;font-size:2rem;font-weight:700;margin-bottom:2.5rem">{_esc(title)}</h2>'
        f'<div class="pb-features-grid">{items_html}</div>'
        f'</div></section>'
    )


def _cta(s, brand_key):
    title    = s.get('title', 'Prêt à commencer ?')
    subtitle = s.get('subtitle', '')
    cta_lbl  = s.get('cta_label', 'Découvrir')
    cta_url  = url_de_lien(s.get('cta_url'), '#')
    bg       = couleur(s.get('bg_color'), '#D6B36A')
    fg       = couleur(s.get('text_color'), '#0B0B0D')

    return (
        f'<section class="pb-section pb-cta" style="{_style(f"background:{_esc(bg)}", f"color:{_esc(fg)}", "padding:5rem 1.5rem;text-align:center")}">'
        f'<div class="pb-container">'
        f'<h2 style="font-size:2.2rem;font-weight:700;margin-bottom:1rem">{_esc(title)}</h2>'
        + (f'<p style="font-size:1.1rem;opacity:.8;margin-bottom:2rem">{_esc(subtitle)}</p>' if subtitle else '')
        + f'<a href="{_esc(cta_url)}" class="pb-btn pb-btn-dark">{_esc(cta_lbl)}</a>'
        + '</div></section>'
    )


def _faq(s, brand_key):
    title = s.get('title', 'Foire aux questions')
    bg    = couleur(s.get('bg_color'), '')

    default_items = [
        ('Comment passer une commande ?', "Ajoutez vos articles au panier et suivez les étapes de commande."),
        ('Quels sont les délais de livraison ?', "Comptez 2 à 5 jours ouvrés selon votre localisation."),
        ('Comment retourner un article ?', "Contactez notre service client sous 14 jours."),
    ]
    items_html = ''.join(
        f'<details class="pb-faq-item"><summary class="pb-faq-q">{_esc(q)}</summary>'
        f'<div class="pb-faq-a">{_esc(a)}</div></details>'
        for q, a in default_items
    )

    return (
        f'<section class="pb-section pb-faq" style="{_style(f"background:{_esc(bg)}" if bg else "", "padding:4rem 1.5rem")}">'
        f'<div class="pb-container" style="max-width:760px">'
        f'<h2 style="text-align:center;font-size:2rem;font-weight:700;margin-bottom:2.5rem">{_esc(title)}</h2>'
        f'{items_html}'
        f'</div></section>'
    )


def _full_image(s, brand_key):
    eyebrow    = s.get('eyebrow', '')
    title      = s.get('title', 'Titre')
    subtitle   = s.get('subtitle', '')
    image      = url_dans_du_css(s.get('image'), '')
    min_height = longueur_css(s.get('min_height'), '70vh')
    opacity    = entier(s.get('overlay_opacity'), 55, 'overlay_opacity')
    cta_lbl    = s.get('cta_label', '')
    cta_url    = url_de_lien(s.get('cta_url'), '#')
    bg         = couleur(s.get('bg_color'), '#080808')
    fg         = couleur(s.get('text_color'), '#F7F2E7')

    bg_img      = f"background-image:url('{_esc(image)}');background-size:cover;background-position:center;" if image else ''
    overlay     = f'<div style="position:absolute;inset:0;background:rgba(0,0,0,{opacity/100:.2f})"></div>' if image else ''
    placeholder = (
        '<div style="position:absolute;inset:0;display:flex;align-items:center;'
        'justify-content:center;opacity:.12;flex-direction:column;gap:.5rem">'
        '<i class="bi bi-image" style="font-size:4rem"></i>'
        '<span style="font-size:.8rem;letter-spacing:.1em">UPLOADEZ UNE IMAGE</span>'
        '</div>'
    ) if not image else ''

    return (
        f'<section style="position:relative;overflow:hidden;min-height:{_esc(min_height)};'
        f'display:flex;align-items:center;{_style(f"background:{_esc(bg)}", bg_img, f"color:{_esc(fg)}")}">'
        f'{overlay}{placeholder}'
        f'<div style="position:relative;z-index:1;width:100%;max-width:1200px;margin:0 auto;padding:5rem 1.5rem;text-align:center">'
        + (f'<p style="font-size:.68rem;font-weight:900;letter-spacing:.15em;text-transform:uppercase;color:#D6B36A;margin-bottom:1.2rem">{_esc(eyebrow)}</p>' if eyebrow else '')
        + f'<h2 style="font-size:2.6rem;font-weight:300;margin-bottom:1rem;line-height:1.2;font-family:serif">{_esc(title)}</h2>'
        + (f'<p style="font-size:.95rem;opacity:.65;max-width:520px;margin:0 auto 2.5rem;line-height:1.75">{_esc(subtitle)}</p>' if subtitle else '')
        + (f'<a href="{_esc(cta_url)}" style="display:inline-block;padding:.9rem 2.2rem;background:#D6B36A;color:#0B0B0D;font-weight:800;border:none;text-decoration:none;font-size:.85rem;letter-spacing:.08em;text-transform:uppercase">{_esc(cta_lbl)}</a>' if cta_lbl else '')
        + '</div></section>'
    )


def _spacer(s, brand_key):
    height = entier(s.get('height'), 80, 'height')
    bg     = couleur(s.get('bg_color'), '')
    return (
        f'<div class="pb-spacer" style="{_style(f"height:{height}px", f"background:{_esc(bg)}" if bg else "")}"></div>'
    )


def _unknown(s, brand_key):
    return '<div style="padding:2rem;text-align:center;opacity:.4">Section inconnue</div>'
