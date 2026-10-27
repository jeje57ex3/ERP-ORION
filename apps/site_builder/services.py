import json
from django.utils import timezone
from django.utils.text import slugify

from .models import BuilderPage, BuilderSection, BuilderPublishLog
from .registry import BUILDER_MODULES
from .sanitize import assainir_reglages

# ── Default sections par marque ───────────────────────────────────────────────

_SIECLE_DEFAULTS = [
    ('hero', {
        'title': 'Objets intemporels, sélectionnés pour durer.',
        'subtitle': 'Une sélection de matières et lignes pensées pour traverser le temps.',
        'cta_label': 'Découvrir les objets',
        'cta_url': '/collections',
        'image': '',
        'overlay_opacity': 40,
        'bg_color': '#0B0B0D',
        'text_color': '#F7F2E7',
    }),
    ('collection_filter', {
        'title': 'Parcourir la collection',
        'bg_color': '#0B0B0D',
    }),
    ('product_grid', {
        'title': 'Archive des Objets Intemporels',
        'count': 8,
        'category_slug': '',
        'bg_color': '#0B0B0D',
    }),
    ('text_image', {
        'title': 'La sélection SIÈCLE',
        'body': 'Chaque objet est choisi pour sa justesse, sa matière et sa capacité à rester pertinent avec le temps.',
        'image': '',
        'image_side': 'right',
        'cta_label': '',
        'cta_url': '',
        'bg_color': '#101014',
        'text_color': '#F7F2E7',
    }),
    ('features', {
        'title': 'Pourquoi SIÈCLE',
        'bg_color': '#17171B',
        'text_color': '#F7F2E7',
    }),
]

_LUNEA_DEFAULTS = [
    ('hero', {
        'title': 'Beauté, soin et expérience personnalisée.',
        'subtitle': "Construisez une vitrine élégante pour l'univers LUNEA.",
        'cta_label': 'Découvrir',
        'cta_url': '/collections',
        'image': '',
        'overlay_opacity': 40,
        'bg_color': '#0B0B0D',
        'text_color': '#F7F2E7',
    }),
    ('product_grid', {
        'title': 'Sélection LUNEA',
        'count': 8,
        'category_slug': '',
        'bg_color': '#0B0B0D',
    }),
    ('features', {
        'title': "L'expérience LUNEA",
        'bg_color': '#17171B',
        'text_color': '#F7F2E7',
    }),
]


def create_default_builder_page_for_website(
    company,
    website,
    title: str = '',
    is_homepage: bool = True,
) -> BuilderPage:
    """
    Crée une BuilderPage rattachée au Website existant avec sections par défaut.
    Ne crée jamais de nouveau Website. Retourne la homepage existante si présente.
    """
    if website.company_id != company.pk:
        raise ValueError("Le Website n'appartient pas à l'entreprise active.")

    if is_homepage:
        existing = BuilderPage.objects.filter(
            company=company, website=website, is_homepage=True,
        ).first()
        if existing:
            return existing

    page_title = title or f'Accueil {website.name}'
    base_slug = slugify(page_title) or 'accueil'

    # Éviter conflit de slug
    slug = base_slug
    counter = 1
    while BuilderPage.objects.filter(website=website, slug=slug).exists():
        slug = f'{base_slug}-{counter}'
        counter += 1

    page = BuilderPage.objects.create(
        company=company,
        website=website,
        brand_key=website.slug,
        title=page_title,
        slug=slug,
        is_homepage=is_homepage,
        status=BuilderPage.STATUS_DRAFT,
    )

    defaults = _SIECLE_DEFAULTS if website.slug == 'siecle' else (
        _LUNEA_DEFAULTS if website.slug == 'lunea' else _SIECLE_DEFAULTS
    )

    for pos, (module_type, overrides) in enumerate(defaults):
        if module_type not in BUILDER_MODULES:
            continue
        settings = dict(BUILDER_MODULES[module_type].get('defaults', {}))
        settings.update(overrides)
        BuilderSection.objects.create(
            page=page,
            module_type=module_type,
            position=pos,
            settings=settings,
            is_visible=True,
        )

    return page


def add_section_to_page(page: BuilderPage, module_type: str) -> BuilderSection:
    if module_type not in BUILDER_MODULES:
        raise ValueError(f"Module inconnu : {module_type}")

    last_pos = page.sections.order_by('-position').values_list('position', flat=True).first()
    position = (last_pos + 1) if last_pos is not None else 0

    defaults = dict(BUILDER_MODULES[module_type].get('defaults', {}))

    return BuilderSection.objects.create(
        page=page,
        module_type=module_type,
        position=position,
        settings=defaults,
    )


def update_section_settings(section: BuilderSection, settings: dict) -> BuilderSection:
    """Enregistre les reglages d'une section, assainis.

    L'assainissement est ICI et pas seulement dans le moteur de rendu,
    parce que `public_api._serialize_section` renvoie ce dictionnaire
    **brut** au frontend Next.js : une protection posee uniquement dans
    `renderer.py` laisserait le site public recevoir un
    « cta_url: javascript:... » et l'executer chez chaque visiteur.

    Les valeurs refusees retombent sur le defaut du module au lieu de
    faire echouer l'enregistrement : un editeur de pages doit pardonner
    une faute de frappe, et le resultat se voit a l'ecran.
    """
    section.settings = assainir_reglages(section.module_type, settings)
    section.save(update_fields=['settings', 'updated_at'])
    return section


def delete_section(section: BuilderSection) -> None:
    section.delete()


def reorder_sections_from_ids(page: BuilderPage, section_ids: list) -> None:
    sections = {s.pk: s for s in page.sections.all()}
    to_update = []
    for pos, sid in enumerate(section_ids):
        # `int()` levait ValueError sur une entree non numerique -- donc un
        # 500 sur un simple glisser-deposer dont le JSON est malforme. Une
        # entree illisible est ignoree : les autres gardent leur ordre.
        try:
            sid = int(sid)
        except (TypeError, ValueError):
            continue
        if sid in sections:
            sections[sid].position = pos
            to_update.append(sections[sid])
    BuilderSection.objects.bulk_update(to_update, ['position'])


def publish_builder_page(page: BuilderPage, user=None) -> BuilderPage:
    snapshot = list(
        page.sections.order_by('position').values('pk', 'module_type', 'position', 'settings')
    )

    page.status = BuilderPage.STATUS_PUBLISHED
    page.published_at = timezone.now()
    page.save(update_fields=['status', 'published_at', 'updated_at'])

    BuilderPublishLog.objects.create(
        page=page,
        published_by=user,
        sections_snapshot=snapshot,
    )
    return page
