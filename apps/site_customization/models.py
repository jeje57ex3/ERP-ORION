"""
apps/site_customization/models.py — Personnalisation des sites web SIÈCLE / LUNEA
"""
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class SiteThemeSettings(models.Model):
    """Paramètres visuels globaux d'un site (logo, couleurs, typographie, scripts)."""

    company = models.ForeignKey(
        'core.Company',
        on_delete=models.CASCADE,
        related_name='site_theme_settings',
    )
    website = models.OneToOneField(
        'websites.Website',
        on_delete=models.CASCADE,
        related_name='theme_settings',
    )

    logo      = models.ImageField(upload_to='sites/theme/logos/',      blank=True, null=True, verbose_name='Logo (clair)')
    logo_dark = models.ImageField(upload_to='sites/theme/logos_dark/', blank=True, null=True, verbose_name='Logo (sombre)')
    favicon   = models.ImageField(upload_to='sites/theme/favicons/',   blank=True, null=True)

    primary_color    = models.CharField(max_length=20, default='#D6B36A', verbose_name='Couleur primaire')
    secondary_color  = models.CharField(max_length=20, default='#F1DFA8', verbose_name='Couleur secondaire')
    background_color = models.CharField(max_length=20, default='#0B0B0D', verbose_name='Fond')
    surface_color    = models.CharField(max_length=20, default='#17171B', verbose_name='Surface')
    text_color       = models.CharField(max_length=20, default='#F7F2E7', verbose_name='Texte')
    muted_text_color = models.CharField(max_length=20, default='#B9B2A3', verbose_name='Texte atténué')

    font_family    = models.CharField(max_length=120, default='Inter, system-ui, sans-serif', verbose_name='Police')
    border_radius  = models.PositiveIntegerField(default=24,  verbose_name='Rayon bordures (px)')
    button_radius  = models.PositiveIntegerField(default=999, verbose_name='Rayon boutons (px)')

    custom_css    = models.TextField(blank=True, verbose_name='CSS personnalisé')
    head_scripts  = models.TextField(blank=True, verbose_name='Scripts <head>')
    body_scripts  = models.TextField(blank=True, verbose_name='Scripts <body>')

    is_published = models.BooleanField(default=False, verbose_name='Publié')
    published_at = models.DateTimeField(null=True, blank=True)
    updated_by   = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='updated_site_themes',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Thème site'
        verbose_name_plural = 'Thèmes sites'

    def publish(self, user=None):
        self.is_published = True
        self.published_at = timezone.now()
        if user:
            self.updated_by = user
        self.save(update_fields=['is_published', 'published_at', 'updated_by', 'updated_at'])

    def __str__(self):
        return f'Thème — {self.website}'


class SitePageCustomization(models.Model):
    """Page personnalisable : hero, textes, CTA, SEO, sections."""

    PAGE_TYPE_CHOICES = [
        ('home',           'Accueil'),
        ('about',          'À propos'),
        ('contact',        'Contact'),
        ('collection',     'Collection'),
        ('product_landing','Landing produit'),
        ('legal',          'Page légale'),
        ('custom',         'Page personnalisée'),
    ]
    STATUS_CHOICES = [
        ('draft',     'Brouillon'),
        ('published', 'Publié'),
        ('archived',  'Archivé'),
    ]

    company   = models.ForeignKey('core.Company',       on_delete=models.CASCADE,  related_name='custom_site_pages')
    website   = models.ForeignKey('websites.Website',   on_delete=models.CASCADE,  related_name='custom_pages')
    page_type = models.CharField(max_length=50, choices=PAGE_TYPE_CHOICES, default='custom')
    title     = models.CharField(max_length=220)
    slug      = models.SlugField(max_length=240, blank=True)

    seo_title       = models.CharField(max_length=220, blank=True, verbose_name='SEO title')
    seo_description = models.TextField(blank=True, verbose_name='SEO description')

    hero_title    = models.CharField(max_length=240, blank=True, verbose_name='Titre hero')
    hero_subtitle = models.TextField(blank=True,     verbose_name='Sous-titre hero')
    hero_image    = models.ImageField(upload_to='sites/pages/hero/', blank=True, null=True, verbose_name='Image hero')

    cta_label = models.CharField(max_length=120, blank=True, verbose_name='Texte CTA')
    cta_url   = models.CharField(max_length=300, blank=True, verbose_name='URL CTA')

    status      = models.CharField(max_length=40, choices=STATUS_CHOICES, default='draft')
    is_homepage = models.BooleanField(default=False, verbose_name='Page d\'accueil')
    published_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_custom_site_pages')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_custom_site_pages')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('website', 'slug')]
        ordering = ['website__name', 'title']
        verbose_name = 'Page personnalisée'
        verbose_name_plural = 'Pages personnalisées'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        if self.is_homepage:
            SitePageCustomization.objects.filter(website=self.website, is_homepage=True).exclude(pk=self.pk).update(is_homepage=False)
        super().save(*args, **kwargs)

    def publish(self, user=None):
        self.status = 'published'
        self.published_at = timezone.now()
        if user:
            self.updated_by = user
        self.save(update_fields=['status', 'published_at', 'updated_by', 'updated_at'])

    def __str__(self):
        return f'{self.website} — {self.title}'


class SitePageSection(models.Model):
    """Section d'une page personnalisée."""

    SECTION_TYPE_CHOICES = [
        ('hero',         'Hero'),
        ('text',         'Texte'),
        ('image_text',   'Image + texte'),
        ('products',     'Produits'),
        ('collection',   'Collection'),
        ('features',     'Avantages'),
        ('gallery',      'Galerie'),
        ('testimonials', 'Avis clients'),
        ('faq',          'FAQ'),
        ('cta',          'Appel à l\'action'),
        ('custom_html',  'HTML personnalisé'),
    ]

    page         = models.ForeignKey(SitePageCustomization, on_delete=models.CASCADE, related_name='sections')
    title        = models.CharField(max_length=220)
    subtitle     = models.TextField(blank=True)
    section_type = models.CharField(max_length=50, choices=SECTION_TYPE_CHOICES, default='text')
    image        = models.ImageField(upload_to='sites/sections/', blank=True, null=True)
    content      = models.TextField(blank=True)
    custom_html  = models.TextField(blank=True, verbose_name='HTML personnalisé')
    cta_label    = models.CharField(max_length=120, blank=True, verbose_name='Texte CTA')
    cta_url      = models.CharField(max_length=300, blank=True, verbose_name='URL CTA')
    position     = models.PositiveIntegerField(default=0)
    is_visible   = models.BooleanField(default=True)
    background_color = models.CharField(max_length=20, blank=True)
    text_color       = models.CharField(max_length=20, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['position', 'id']
        verbose_name = 'Section page'
        verbose_name_plural = 'Sections page'

    def __str__(self):
        return f'{self.page.title} — {self.title}'


class SiteContentBlock(models.Model):
    """Bloc à l'intérieur d'une section (avantage, FAQ, témoignage, galerie...)."""

    BLOCK_TYPE_CHOICES = [
        ('text',        'Texte'),
        ('image',       'Image'),
        ('link',        'Lien'),
        ('feature',     'Avantage'),
        ('faq_item',    'Question FAQ'),
        ('testimonial', 'Témoignage'),
        ('stat',        'Statistique'),
        ('html',        'HTML'),
    ]

    section    = models.ForeignKey(SitePageSection, on_delete=models.CASCADE, related_name='blocks')
    block_type = models.CharField(max_length=40, choices=BLOCK_TYPE_CHOICES, default='text')
    title      = models.CharField(max_length=220, blank=True)
    content    = models.TextField(blank=True)
    image      = models.ImageField(upload_to='sites/blocks/', blank=True, null=True)
    link_label = models.CharField(max_length=120, blank=True)
    link_url   = models.CharField(max_length=300, blank=True)
    position   = models.PositiveIntegerField(default=0)
    is_visible = models.BooleanField(default=True)
    extra_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['position', 'id']
        verbose_name = 'Bloc contenu'
        verbose_name_plural = 'Blocs contenu'

    def __str__(self):
        return self.title or f'Bloc {self.pk}'
