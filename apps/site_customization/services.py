from django.utils import timezone
from .models import SitePageCustomization, SiteThemeSettings


def publish_theme(theme, user=None):
    theme.is_published = True
    theme.published_at = timezone.now()
    if user:
        theme.updated_by = user
    theme.save(update_fields=['is_published', 'published_at', 'updated_by', 'updated_at'])
    return theme


def unpublish_theme(theme, user=None):
    theme.is_published = False
    if user:
        theme.updated_by = user
    theme.save(update_fields=['is_published', 'updated_by', 'updated_at'])
    return theme


def publish_page(page, user=None):
    page.status = 'published'
    page.published_at = timezone.now()
    if user:
        page.updated_by = user
    page.save(update_fields=['status', 'published_at', 'updated_by', 'updated_at'])
    return page


def build_theme_css(theme):
    """Génère les variables CSS à injecter côté public."""
    if not theme:
        return ''
    css = f""":root {{
  --site-primary: {theme.primary_color};
  --site-secondary: {theme.secondary_color};
  --site-background: {theme.background_color};
  --site-surface: {theme.surface_color};
  --site-text: {theme.text_color};
  --site-muted: {theme.muted_text_color};
  --site-font: {theme.font_family};
  --site-radius: {theme.border_radius}px;
  --site-button-radius: {theme.button_radius}px;
}}
"""
    if theme.custom_css:
        css += '\n' + theme.custom_css
    return css


def clone_page_as_draft(page, user=None):
    """Duplique une page publiée en brouillon avec ses sections et blocs."""
    old_sections = list(page.sections.prefetch_related('blocks').all())
    page.pk = None
    page.status = 'draft'
    page.is_homepage = False
    page.slug = f'{page.slug}-copie'
    page.created_by = user
    page.updated_by = user
    page.published_at = None
    page.save()
    for section in old_sections:
        old_blocks = list(section.blocks.all())
        section.pk = None
        section.page = page
        section.save()
        for block in old_blocks:
            block.pk = None
            block.section = section
            block.save()
    return page
