"""
apps/websites/models.py — Gestion de sites web publics multi-entreprises
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from apps.core.models import Company


# ─── Thème ────────────────────────────────────────────────────────────────────

class WebsiteTheme(models.Model):
    """Thème de couleurs pour un site web."""
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='website_themes', null=True, blank=True)

    FONT_CHOICES = [
        ('Inter', 'Inter'),
        ('Roboto', 'Roboto'),
        ('Open Sans', 'Open Sans'),
        ('Poppins', 'Poppins'),
        ('Montserrat', 'Montserrat'),
        ('Raleway', 'Raleway'),
        ('Lato', 'Lato'),
        ('Nunito', 'Nunito'),
    ]
    BUTTON_STYLE_CHOICES = [
        ('rounded', 'Arrondi'),
        ('pill', 'Pilule'),
        ('square', 'Carré'),
        ('outlined', 'Contour'),
    ]
    MODE_CHOICES = [('light', 'Clair'), ('dark', 'Sombre')]

    name = models.CharField('Nom du thème', max_length=100)
    primary_color = models.CharField('Couleur primaire', max_length=7, default='#2563EB')
    secondary_color = models.CharField('Couleur secondaire', max_length=7, default='#0F172A')
    accent_color = models.CharField('Couleur accent', max_length=7, default='#38BDF8')
    background_color = models.CharField('Couleur fond', max_length=7, default='#FFFFFF')
    text_color = models.CharField('Couleur texte', max_length=7, default='#111827')
    button_color = models.CharField('Couleur boutons', max_length=7, default='#2563EB')
    header_bg_color = models.CharField('Fond header', max_length=7, default='#FFFFFF')
    footer_bg_color = models.CharField('Fond footer', max_length=7, default='#0F172A')
    footer_text_color = models.CharField('Texte footer', max_length=7, default='#CBD5E1')
    font_primary = models.CharField('Police principale', max_length=50, choices=FONT_CHOICES, default='Inter')
    font_secondary = models.CharField('Police secondaire', max_length=50, choices=FONT_CHOICES, default='Poppins')
    button_style = models.CharField('Style boutons', max_length=20, choices=BUTTON_STYLE_CHOICES, default='rounded')
    border_radius = models.CharField('Rayon bordures', max_length=10, default='0.5rem')
    mode = models.CharField('Mode', max_length=10, choices=MODE_CHOICES, default='light')
    custom_css = models.TextField('CSS personnalisé', blank=True)
    is_default = models.BooleanField('Thème par défaut', default=False)

    class Meta:
        verbose_name = 'Thème site web'
        verbose_name_plural = 'Thèmes sites web'

    def __str__(self):
        return self.name


# ─── Site web ─────────────────────────────────────────────────────────────────

class Website(models.Model):
    """Site web d'une entreprise."""
    SITE_TYPES = [
        ('showcase', 'Site vitrine'),
        ('ecommerce', 'Boutique en ligne'),
        ('catalog', 'Catalogue sans paiement'),
        ('landing', 'Landing page'),
        ('blog', 'Blog'),
        ('portal', 'Portail client'),
        ('event', 'Site événementiel'),
        ('btp', 'Site BTP'),
        ('commerce', 'Site commerce'),
        ('audio', 'Site audio / audiovisuel'),
        ('production', 'Site production / industrie'),
    ]
    STATUS_CHOICES = [
        ('draft', 'Brouillon'),
        ('construction', 'En construction'),
        ('published', 'Publié'),
        ('unpublished', 'Dépublié'),
        ('archived', 'Archivé'),
    ]
    LANGUAGE_CHOICES = [
        ('fr', 'Français'),
        ('en', 'Anglais'),
        ('es', 'Espagnol'),
        ('de', 'Allemand'),
        ('it', 'Italien'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='websites')
    name = models.CharField('Nom du site', max_length=200)
    site_type = models.CharField('Type de site', max_length=20, choices=SITE_TYPES, default='showcase')
    status = models.CharField('Statut', max_length=20, choices=STATUS_CHOICES, default='draft')
    domain = models.CharField('Domaine / sous-domaine', max_length=200, blank=True)
    subdomain = models.CharField('Sous-domaine', max_length=100, blank=True)
    currency = models.CharField('Devise', max_length=3, default='EUR')
    country = models.CharField('Pays', max_length=100, default='France')
    logo = models.ImageField('Logo', upload_to='websites/logos/', blank=True, null=True)
    favicon = models.ImageField('Favicon', upload_to='websites/favicons/', blank=True, null=True)
    contact_email = models.EmailField('Email contact', blank=True)
    contact_phone = models.CharField('Téléphone', max_length=20, blank=True)
    address = models.TextField('Adresse', blank=True)
    theme = models.ForeignKey(WebsiteTheme, on_delete=models.SET_NULL, null=True, blank=True)
    language = models.CharField('Langue', max_length=5, choices=LANGUAGE_CHOICES, default='fr')
    is_active = models.BooleanField('Actif', default=True)
    show_powered_by_orion = models.BooleanField('Afficher "Propulsé par Orion ERP"', default=True)

    # Réseaux sociaux
    facebook_url = models.URLField('Facebook', blank=True)
    instagram_url = models.URLField('Instagram', blank=True)
    twitter_url = models.URLField('Twitter / X', blank=True)
    linkedin_url = models.URLField('LinkedIn', blank=True)
    youtube_url = models.URLField('YouTube', blank=True)
    tiktok_url = models.URLField('TikTok', blank=True)

    # SEO global
    meta_title = models.CharField('Meta title', max_length=70, blank=True)
    meta_description = models.CharField('Meta description', max_length=160, blank=True)
    google_analytics_id = models.CharField('GA ID', max_length=30, blank=True)
    meta_pixel_id = models.CharField('Meta Pixel ID', max_length=30, blank=True)

    # Mentions légales
    legal_company_name = models.CharField('Raison sociale', max_length=200, blank=True)
    legal_siret = models.CharField('SIRET', max_length=14, blank=True)
    legal_vat = models.CharField('N° TVA', max_length=20, blank=True)
    legal_director = models.CharField('Directeur de publication', max_length=100, blank=True)
    hosting_provider = models.CharField('Hébergeur', max_length=100, blank=True)

    slug = models.SlugField('Slug', max_length=100, blank=True)
    is_published = models.BooleanField('Publié', default=False)
    published_at = models.DateTimeField('Publié le', null=True, blank=True)
    unpublished_at = models.DateTimeField('Dépublié le', null=True, blank=True)
    maintenance_mode = models.BooleanField('Mode maintenance', default=False)
    home_page = models.ForeignKey('WebsitePage', on_delete=models.SET_NULL, null=True, blank=True, related_name='+', verbose_name='Page d\'accueil')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Site web'
        verbose_name_plural = 'Sites web'
        ordering = ['name']

    @property
    def public_slug(self):
        """Slug utilisé dans les URLs publiques du site."""
        return self.slug or self.company.slug

    def __str__(self):
        return f'{self.name} ({self.company.name})'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


# ─── Pages ────────────────────────────────────────────────────────────────────

class WebsitePage(models.Model):
    """Page dynamique d'un site web."""
    PAGE_TYPES = [
        ('home', 'Accueil'),
        ('about', 'À propos'),
        ('services', 'Services'),
        ('products', 'Produits'),
        ('projects', 'Réalisations'),
        ('blog_list', 'Blog'),
        ('blog_article', 'Article de blog'),
        ('contact', 'Contact'),
        ('quote_request', 'Demande de devis'),
        ('legal', 'Mentions légales'),
        ('privacy', 'Politique de confidentialité'),
        ('faq', 'FAQ'),
        ('team', 'Équipe'),
        ('custom', 'Page personnalisée'),
    ]
    STATUS_CHOICES = [('draft', 'Brouillon'), ('published', 'Publié'), ('archived', 'Archivé')]

    website = models.ForeignKey(Website, on_delete=models.CASCADE, related_name='pages')
    page_type = models.CharField('Type de page', max_length=20, choices=PAGE_TYPES, default='custom')
    title = models.CharField('Titre', max_length=200)
    slug = models.SlugField('Slug', max_length=200)
    content = models.TextField('Contenu (HTML/Markdown)', blank=True)
    hero_image = models.ImageField('Image hero', upload_to='websites/pages/', blank=True, null=True)
    status = models.CharField('Statut', max_length=20, choices=STATUS_CHOICES, default='draft')
    order = models.PositiveIntegerField('Ordre', default=0)
    is_homepage = models.BooleanField('Page d\'accueil', default=False)
    show_in_menu = models.BooleanField('Afficher dans le menu', default=True)
    # SEO
    meta_title = models.CharField('Meta title', max_length=70, blank=True)
    meta_description = models.CharField('Meta description', max_length=160, blank=True)
    is_indexable = models.BooleanField('Indexable SEO', default=True)
    canonical_url = models.URLField('URL canonique', blank=True)
    published_at = models.DateTimeField('Publié le', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Page web'
        verbose_name_plural = 'Pages web'
        ordering = ['order', 'title']
        unique_together = ['website', 'slug']

    def __str__(self):
        return f'{self.title} ({self.website.name})'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)


class WebsiteSection(models.Model):
    """Section dans une page web."""
    SECTION_TYPES = [
        ('hero', 'Hero banner'),
        ('text', 'Texte simple'),
        ('image_text', 'Image + texte'),
        ('services_grid', 'Grille de services'),
        ('products_grid', 'Grille de produits'),
        ('testimonials', 'Témoignages'),
        ('projects_grid', 'Réalisations'),
        ('faq', 'FAQ'),
        ('cta', 'Call to action'),
        ('contact_form', 'Formulaire de contact'),
        ('newsletter', 'Newsletter'),
        ('gallery', 'Galerie'),
        ('stats', 'Chiffres clés'),
        ('team', 'Équipe'),
        ('map', 'Carte / localisation'),
        ('pricing', 'Tarifs'),
        ('video', 'Vidéo'),
        ('custom', 'Contenu libre'),
    ]

    page = models.ForeignKey(WebsitePage, on_delete=models.CASCADE, related_name='sections')
    section_type = models.CharField('Type', max_length=30, choices=SECTION_TYPES, default='text')
    title = models.CharField('Titre', max_length=200, blank=True)
    subtitle = models.CharField('Sous-titre', max_length=300, blank=True)
    content = models.TextField('Contenu', blank=True)
    image = models.ImageField('Image', upload_to='websites/sections/', blank=True, null=True)
    video_url = models.URLField('URL vidéo', blank=True)
    button_text = models.CharField('Texte bouton', max_length=100, blank=True)
    button_link = models.CharField('Lien bouton', max_length=300, blank=True)
    button_secondary_text = models.CharField('Texte bouton 2', max_length=100, blank=True)
    button_secondary_link = models.CharField('Lien bouton 2', max_length=300, blank=True)
    bg_color = models.CharField('Couleur fond', max_length=50, blank=True)
    text_color = models.CharField('Couleur texte', max_length=50, blank=True)
    order = models.PositiveIntegerField('Ordre', default=0)
    is_visible = models.BooleanField('Visible', default=True)
    extra_config = models.JSONField('Config supplémentaire', default=dict, blank=True)

    class Meta:
        verbose_name = 'Section web'
        verbose_name_plural = 'Sections web'
        ordering = ['order']

    def __str__(self):
        return f'{self.get_section_type_display()} — {self.page.title}'


# ─── Menu ─────────────────────────────────────────────────────────────────────

class WebsiteMenu(models.Model):
    MENU_POSITIONS = [
        ('header', 'En-tête'),
        ('footer', 'Pied de page'),
        ('sidebar', 'Barre latérale'),
    ]

    website = models.ForeignKey(Website, on_delete=models.CASCADE, related_name='menus')
    name = models.CharField('Nom', max_length=100)
    position = models.CharField('Position', max_length=20, choices=MENU_POSITIONS, default='header')
    is_active = models.BooleanField('Actif', default=True)

    class Meta:
        verbose_name = 'Menu'

    def __str__(self):
        return f'{self.name} — {self.website.name}'


class WebsiteMenuItem(models.Model):
    menu = models.ForeignKey(WebsiteMenu, on_delete=models.CASCADE, related_name='items')
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children')
    label = models.CharField('Libellé', max_length=100)
    page = models.ForeignKey(WebsitePage, on_delete=models.SET_NULL, null=True, blank=True)
    url = models.CharField('URL externe', max_length=300, blank=True)
    open_new_tab = models.BooleanField('Nouvel onglet', default=False)
    order = models.PositiveIntegerField('Ordre', default=0)
    is_active = models.BooleanField('Actif', default=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.label

    @property
    def link(self):
        if self.page:
            return f'/{self.page.slug}/'
        return self.url or '#'


# ─── Blog ─────────────────────────────────────────────────────────────────────

class BlogCategory(models.Model):
    website = models.ForeignKey(Website, on_delete=models.CASCADE, related_name='blog_categories')
    name = models.CharField('Nom', max_length=100)
    slug = models.SlugField('Slug')
    description = models.TextField('Description', blank=True)
    color = models.CharField('Couleur', max_length=7, default='#2563EB')

    class Meta:
        verbose_name = 'Catégorie blog'
        unique_together = ['website', 'slug']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class BlogPost(models.Model):
    STATUS_CHOICES = [('draft', 'Brouillon'), ('published', 'Publié'), ('archived', 'Archivé')]

    website = models.ForeignKey(Website, on_delete=models.CASCADE, related_name='blog_posts')
    category = models.ForeignKey(BlogCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='posts')
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    title = models.CharField('Titre', max_length=200)
    slug = models.SlugField('Slug', max_length=200)
    excerpt = models.TextField('Extrait', max_length=300, blank=True)
    content = models.TextField('Contenu')
    cover_image = models.ImageField('Image principale', upload_to='websites/blog/', blank=True, null=True)
    tags = models.CharField('Tags', max_length=300, blank=True)
    status = models.CharField('Statut', max_length=20, choices=STATUS_CHOICES, default='draft')
    # SEO
    meta_title = models.CharField('Meta title', max_length=70, blank=True)
    meta_description = models.CharField('Meta description', max_length=160, blank=True)
    is_indexable = models.BooleanField('Indexable SEO', default=True)
    reading_time = models.PositiveIntegerField('Temps lecture (min)', default=5)
    published_at = models.DateTimeField('Publié le', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Article blog'
        verbose_name_plural = 'Articles blog'
        ordering = ['-published_at', '-created_at']
        unique_together = ['website', 'slug']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)


# ─── Formulaires ──────────────────────────────────────────────────────────────

class ContactMessage(models.Model):
    """Message reçu via le formulaire de contact public."""
    STATUS_CHOICES = [
        ('new', 'Nouveau'),
        ('read', 'Lu'),
        ('replied', 'Répondu'),
        ('spam', 'Spam'),
        ('archived', 'Archivé'),
    ]

    website = models.ForeignKey(Website, on_delete=models.CASCADE, related_name='contact_messages')
    name = models.CharField('Nom', max_length=100)
    email = models.EmailField('Email')
    phone = models.CharField('Téléphone', max_length=20, blank=True)
    subject = models.CharField('Sujet', max_length=200, blank=True)
    message = models.TextField('Message')
    status = models.CharField('Statut', max_length=20, choices=STATUS_CHOICES, default='new')
    ip_address = models.GenericIPAddressField('IP', null=True, blank=True)
    honeypot = models.CharField('Honeypot (anti-spam)', max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField('Lu le', null=True, blank=True)

    class Meta:
        verbose_name = 'Message de contact'
        verbose_name_plural = 'Messages de contact'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} — {self.subject or "Message"}'

    @property
    def is_spam(self):
        return bool(self.honeypot)


class QuoteRequest(models.Model):
    """Demande de devis depuis le site web."""
    STATUS_CHOICES = [
        ('new', 'Nouveau'),
        ('processing', 'En traitement'),
        ('quoted', 'Devis envoyé'),
        ('won', 'Gagné'),
        ('lost', 'Perdu'),
        ('spam', 'Spam'),
    ]

    website = models.ForeignKey(Website, on_delete=models.CASCADE, related_name='quote_requests')
    company_name = models.CharField('Société', max_length=200, blank=True)
    name = models.CharField('Nom', max_length=100)
    email = models.EmailField('Email')
    phone = models.CharField('Téléphone', max_length=20, blank=True)
    project_type = models.CharField('Type de projet', max_length=200, blank=True)
    description = models.TextField('Description du projet')
    budget = models.CharField('Budget estimé', max_length=100, blank=True)
    deadline = models.CharField('Délai souhaité', max_length=100, blank=True)
    attachments = models.FileField('Pièce jointe', upload_to='websites/quotes/', blank=True, null=True)
    status = models.CharField('Statut', max_length=20, choices=STATUS_CHOICES, default='new')
    # Lien CRM auto-créé
    crm_prospect_id = models.PositiveIntegerField('ID Prospect CRM', null=True, blank=True)
    crm_opportunity_id = models.PositiveIntegerField('ID Opportunité CRM', null=True, blank=True)
    honeypot = models.CharField('Honeypot', max_length=100, blank=True)
    ip_address = models.GenericIPAddressField('IP', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Demande de devis'
        verbose_name_plural = 'Demandes de devis'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.company_name or self.email})'


# ─── Contenu web ──────────────────────────────────────────────────────────────

class WebsiteService(models.Model):
    website = models.ForeignKey(Website, on_delete=models.CASCADE, related_name='services')
    title = models.CharField('Titre', max_length=200)
    slug = models.SlugField(blank=True)
    icon = models.CharField('Icône Bootstrap', max_length=50, blank=True)
    description = models.TextField('Description')
    image = models.ImageField('Image', upload_to='websites/services/', blank=True, null=True)
    price = models.DecimalField('Prix indicatif', max_digits=10, decimal_places=2, null=True, blank=True)
    order = models.PositiveIntegerField('Ordre', default=0)
    is_active = models.BooleanField('Actif', default=True)

    class Meta:
        verbose_name = 'Service web'
        ordering = ['order', 'title']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)


class WebsiteTestimonial(models.Model):
    website = models.ForeignKey(Website, on_delete=models.CASCADE, related_name='testimonials')
    author_name = models.CharField('Auteur', max_length=100)
    author_role = models.CharField('Poste / Société', max_length=150, blank=True)
    author_photo = models.ImageField('Photo', upload_to='websites/testimonials/', blank=True, null=True)
    content = models.TextField('Témoignage')
    rating = models.PositiveIntegerField('Note /5', default=5)
    order = models.PositiveIntegerField('Ordre', default=0)
    is_active = models.BooleanField('Actif', default=True)

    class Meta:
        verbose_name = 'Témoignage'
        ordering = ['order', '-rating']

    def __str__(self):
        return f'{self.author_name} — {self.website.name}'


class WebsiteProject(models.Model):
    """Réalisation / portfolio."""
    website = models.ForeignKey(Website, on_delete=models.CASCADE, related_name='web_projects')
    title = models.CharField('Titre', max_length=200)
    slug = models.SlugField(blank=True)
    category = models.CharField('Catégorie', max_length=100, blank=True)
    description = models.TextField('Description')
    cover_image = models.ImageField('Image principale', upload_to='websites/projects/', blank=True, null=True)
    client_name = models.CharField('Client', max_length=100, blank=True)
    completion_date = models.DateField('Date réalisation', null=True, blank=True)
    is_featured = models.BooleanField('En vedette', default=False)
    order = models.PositiveIntegerField('Ordre', default=0)
    is_active = models.BooleanField('Actif', default=True)

    class Meta:
        verbose_name = 'Réalisation'
        ordering = ['order', '-completion_date']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)


class WebsiteFAQ(models.Model):
    website = models.ForeignKey(Website, on_delete=models.CASCADE, related_name='faqs')
    question = models.CharField('Question', max_length=300)
    answer = models.TextField('Réponse')
    category = models.CharField('Catégorie', max_length=100, blank=True)
    order = models.PositiveIntegerField('Ordre', default=0)
    is_active = models.BooleanField('Actif', default=True)

    class Meta:
        verbose_name = 'FAQ'
        ordering = ['order', 'question']

    def __str__(self):
        return self.question


# ─── Boutique intégrée au site web ────────────────────────────────────────────

class StoreCategory(models.Model):
    website = models.ForeignKey(Website, on_delete=models.CASCADE, related_name='store_categories')
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children')
    name = models.CharField('Nom', max_length=100)
    slug = models.SlugField('Slug', max_length=120)
    description = models.TextField('Description', blank=True)
    image = models.ImageField('Image', upload_to='websites/store/categories/', blank=True, null=True)
    order = models.PositiveIntegerField('Ordre', default=0)
    is_active = models.BooleanField('Active', default=True)

    class Meta:
        verbose_name = 'Catégorie boutique'
        ordering = ['order', 'name']
        unique_together = ['website', 'slug']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class StoreProduct(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Brouillon'), ('published', 'Publié'), ('archived', 'Archivé'), ('out_of_stock', 'Rupture'),
    ]

    website = models.ForeignKey(Website, on_delete=models.CASCADE, related_name='store_products')
    category = models.ForeignKey(StoreCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    erp_product = models.ForeignKey(
        'inventory.Product', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='website_listings', verbose_name='Produit ERP lié'
    )
    name = models.CharField('Nom', max_length=200)
    slug = models.SlugField('Slug', max_length=220)
    short_description = models.CharField('Description courte', max_length=300, blank=True)
    description = models.TextField('Description complète', blank=True)
    price = models.DecimalField('Prix TTC', max_digits=12, decimal_places=2, default=0)
    compare_at_price = models.DecimalField('Ancien prix (barré)', max_digits=12, decimal_places=2, null=True, blank=True)
    sku = models.CharField('SKU', max_length=100, blank=True)
    stock_quantity = models.IntegerField('Stock', default=0)
    stock_from_erp = models.BooleanField('Stock depuis ERP', default=False)
    status = models.CharField('Statut', max_length=15, choices=STATUS_CHOICES, default='draft')
    is_featured = models.BooleanField('Mise en avant', default=False)
    is_popular  = models.BooleanField('Populaire', default=False)
    available_sizes = models.JSONField('Tailles disponibles', default=list, blank=True,
                                       help_text='Ex: ["XS","S","M","L","XL","XXL"]')
    model_3d_file  = models.FileField('Modele 3D (.glb)', upload_to='websites/store/products/3d/',
                                      blank=True, null=True)
    is_customizable = models.BooleanField('Personnalisable (configurateur 3D)', default=False)
    weight_kg = models.DecimalField('Poids (kg)', max_digits=8, decimal_places=3, null=True, blank=True)
    meta_title = models.CharField('Meta title', max_length=70, blank=True)
    meta_description = models.CharField('Meta description', max_length=160, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Produit boutique'
        ordering = ['-created_at']
        unique_together = ['website', 'slug']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def is_on_sale(self):
        return self.compare_at_price and self.compare_at_price > self.price

    @property
    def in_stock(self):
        return self.stock_quantity > 0


class StoreProductImage(models.Model):
    product = models.ForeignKey(StoreProduct, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField('Image', upload_to='websites/store/products/')
    alt_text = models.CharField('Texte alternatif', max_length=200, blank=True)
    order = models.PositiveIntegerField('Ordre', default=0)

    class Meta:
        verbose_name = 'Image produit'
        ordering = ['order']

    def __str__(self):
        return f'Image de {self.product.name}'


class StoreCart(models.Model):
    website = models.ForeignKey(Website, on_delete=models.CASCADE, related_name='store_carts')
    session_key = models.CharField('Clé session', max_length=100, blank=True)
    customer_email = models.EmailField('Email client', blank=True)
    coupon_code = models.CharField('Code promo', max_length=50, blank=True)
    discount_amount = models.DecimalField('Remise', max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Panier'

    def __str__(self):
        return f'Panier {self.pk} — {self.website.name}'

    @property
    def subtotal(self):
        return sum(item.total_price for item in self.items.all())

    @property
    def total(self):
        return max(0, self.subtotal - self.discount_amount)


class StoreCartItem(models.Model):
    cart = models.ForeignKey(StoreCart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(StoreProduct, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField('Quantité', default=1)
    unit_price = models.DecimalField('Prix unitaire', max_digits=12, decimal_places=2)
    total_price = models.DecimalField('Total', max_digits=12, decimal_places=2, default=0)

    class Meta:
        verbose_name = 'Ligne panier'
        unique_together = ['cart', 'product']

    def __str__(self):
        return f'{self.product.name} x{self.quantity}'

    def save(self, *args, **kwargs):
        self.total_price = self.unit_price * self.quantity
        super().save(*args, **kwargs)


class StoreOrder(models.Model):
    STATUS_CHOICES = [
        ('checkout_started', 'Checkout démarré'), ('pending', 'En attente'),
        ('confirmed', 'Confirmée'), ('preparing', 'En préparation'),
        ('shipped', 'Expédiée'), ('delivered', 'Livrée'),
        ('cancelled', 'Annulée'), ('refunded', 'Remboursée'), ('payment_failed', 'Paiement échoué'),
    ]
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'En attente'), ('paid', 'Payé'), ('failed', 'Échoué'),
        ('refunded', 'Remboursé'), ('partially_refunded', 'Partiellement remboursé'),
    ]

    website = models.ForeignKey(Website, on_delete=models.CASCADE, related_name='store_orders')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='store_orders')
    order_number = models.CharField('N° commande', max_length=30, unique=True)
    status = models.CharField('Statut', max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_status = models.CharField('Paiement', max_length=25, choices=PAYMENT_STATUS_CHOICES, default='pending')

    # Client
    customer_name = models.CharField('Nom client', max_length=100)
    customer_email = models.EmailField('Email client')
    customer_phone = models.CharField('Téléphone', max_length=20, blank=True)

    # Adresses
    billing_address = models.TextField('Adresse facturation', blank=True)
    shipping_address = models.TextField('Adresse livraison', blank=True)

    # Montants
    subtotal = models.DecimalField('Sous-total', max_digits=12, decimal_places=2, default=0)
    tax_total = models.DecimalField('TVA', max_digits=10, decimal_places=2, default=0)
    shipping_total = models.DecimalField('Frais de port', max_digits=10, decimal_places=2, default=0)
    discount_total = models.DecimalField('Remise', max_digits=10, decimal_places=2, default=0)
    grand_total = models.DecimalField('Total TTC', max_digits=12, decimal_places=2, default=0)

    # Livraison
    shipping_method = models.CharField('Mode livraison', max_length=100, blank=True)
    tracking_number = models.CharField('N° suivi', max_length=100, blank=True)
    carrier = models.CharField('Transporteur', max_length=100, blank=True)

    # Paiement
    payment_method = models.CharField('Mode paiement', max_length=50, blank=True)
    payment_reference = models.CharField('Référence paiement', max_length=200, blank=True)
    stripe_session_id = models.CharField('Stripe Session ID', max_length=200, blank=True)
    stripe_payment_intent = models.CharField('Stripe Payment Intent', max_length=200, blank=True)

    # Lien ERP
    erp_invoice_id = models.PositiveIntegerField('ID Facture ERP', null=True, blank=True)
    erp_shipment_id = models.PositiveIntegerField('ID Expédition ERP', null=True, blank=True)

    # CRM
    crm_customer_id = models.PositiveIntegerField('ID Client CRM', null=True, blank=True)

    notes = models.TextField('Notes', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    shipped_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Commande boutique'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.order_number} — {self.customer_name}'


class StoreOrderItem(models.Model):
    order = models.ForeignKey(StoreOrder, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(StoreProduct, on_delete=models.SET_NULL, null=True, blank=True)
    product_name = models.CharField('Nom produit', max_length=200)
    sku = models.CharField('SKU', max_length=100, blank=True)
    selected_size = models.CharField('Taille choisie', max_length=10, blank=True)
    quantity = models.PositiveIntegerField('Quantité', default=1)
    unit_price = models.DecimalField('Prix unitaire', max_digits=12, decimal_places=2)
    total_price = models.DecimalField('Total', max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = 'Ligne commande boutique'

    def __str__(self):
        return f'{self.product_name} x{self.quantity}'


# ─── Domaines personnalisés ───────────────────────────────────────────────────

class WebsiteDomain(models.Model):
    DOMAIN_TYPES = [
        ('root',      'Domaine racine'),
        ('subdomain', 'Sous-domaine'),
        ('www',       'Sous-domaine www'),
        ('test',      'Domaine de test'),
        ('temporary', 'Domaine temporaire Orion'),
    ]
    TARGET_TYPES = [
        ('website',       'Site web / vitrine'),
        ('shop',          'Boutique en ligne'),
        ('client_portal', 'Portail client'),
        ('erp',           'Orion ERP'),
        ('landing_page',  'Landing page'),
        ('blog',          'Blog'),
    ]
    STATUS_CHOICES = [
        ('pending',      'À configurer'),
        ('dns_pending',  'En attente DNS'),
        ('dns_verified', 'DNS vérifié'),
        ('ssl_pending',  'SSL en attente'),
        ('active',       'Actif'),
        ('error',        'Erreur'),
        ('disabled',     'Désactivé'),
    ]
    SSL_STATUS_CHOICES = [
        ('none',    'Non configuré'),
        ('pending', 'En attente'),
        ('active',  'Actif'),
        ('expired', 'Expiré'),
        ('error',   'Erreur'),
    ]
    VERIFICATION_STATUS_CHOICES = [
        ('not_started', 'Non démarré'),
        ('pending',     'En cours'),
        ('verified',    'Vérifié'),
        ('failed',      'Échec'),
    ]

    # ── Relations ──────────────────────────────────────────────────────────────
    website = models.ForeignKey(Website, on_delete=models.CASCADE, related_name='domains')
    company = models.ForeignKey(
        'core.Company', on_delete=models.CASCADE,
        related_name='website_domains', null=True, blank=True,
        verbose_name='Entreprise',
    )
    created_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_domains', verbose_name='Créé par',
    )

    # ── Domaine ────────────────────────────────────────────────────────────────
    domain = models.CharField('Domaine', max_length=253)
    domain_type = models.CharField('Type', max_length=20, choices=DOMAIN_TYPES, default='subdomain')
    target_type = models.CharField('Cible', max_length=20, choices=TARGET_TYPES, default='website')
    full_domain = models.CharField('Domaine complet', max_length=253, blank=True, editable=False)

    # ── Statuts ────────────────────────────────────────────────────────────────
    status = models.CharField('Statut', max_length=20, choices=STATUS_CHOICES, default='pending')
    is_primary = models.BooleanField('Domaine principal', default=False)
    is_active_flag = models.BooleanField('Actif', default=True)

    # ── DNS ────────────────────────────────────────────────────────────────────
    dns_verified = models.BooleanField('DNS vérifié', default=False)
    dns_verified_at = models.DateTimeField('Vérifié le', null=True, blank=True)
    verification_status = models.CharField(
        'Statut vérification', max_length=20,
        choices=VERIFICATION_STATUS_CHOICES, default='not_started',
    )
    verification_token = models.CharField('Token de vérification', max_length=64, blank=True)
    expected_a_record  = models.CharField('IP attendue (A)', max_length=45, blank=True)
    expected_cname     = models.CharField('CNAME attendu', max_length=253, blank=True, default='sites.orion-erp.com')
    expected_txt_record = models.CharField('TXT attendu', max_length=300, blank=True)

    # ── SSL ────────────────────────────────────────────────────────────────────
    ssl_enabled    = models.BooleanField('SSL activé', default=False)
    ssl_status     = models.CharField('Statut SSL', max_length=10, choices=SSL_STATUS_CHOICES, default='none')
    ssl_issued_at  = models.DateTimeField('SSL émis le', null=True, blank=True)
    ssl_expires_at = models.DateField('Expiration SSL', null=True, blank=True)

    # ── Options ────────────────────────────────────────────────────────────────
    force_https          = models.BooleanField('Forcer HTTPS', default=True)
    redirect_www         = models.BooleanField('Rediriger www → racine', default=False)
    redirect_to_primary  = models.BooleanField('Rediriger vers domaine principal', default=False)

    # ── Diagnostic ─────────────────────────────────────────────────────────────
    last_checked_at = models.DateTimeField('Dernier check', null=True, blank=True)
    last_error      = models.TextField('Dernière erreur', blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Domaine site web'
        verbose_name_plural = 'Domaines sites web'
        unique_together = ['website', 'domain']
        ordering = ['-is_primary', 'domain']

    def __str__(self):
        return f'{self.domain} ({self.get_status_display()})'

    def save(self, *args, **kwargs):
        self.full_domain = self.domain
        if not self.company_id and self.website_id:
            try:
                self.company = self.website.company
            except Exception:
                pass
        super().save(*args, **kwargs)

    @property
    def is_active(self):
        return self.status == 'active'

    @property
    def public_url(self):
        scheme = 'https' if self.ssl_enabled or self.force_https else 'http'
        return f'{scheme}://{self.domain}'

    @property
    def dns_instructions(self):
        if self.domain_type == 'subdomain':
            parts = self.domain.split('.', 1)
            subdomain_label = parts[0] if len(parts) > 1 else self.domain
            return {
                'type': 'CNAME',
                'name': subdomain_label,
                'value': self.expected_cname or 'sites.orion-erp.com',
            }
        return {
            'type': 'A',
            'name': '@',
            'value': self.expected_a_record or '0.0.0.0',
            'alt_type': 'TXT',
            'alt_name': '_orion-verification',
            'alt_value': f'orion-verification={self.verification_token}',
        }


# ─── Médiathèque ──────────────────────────────────────────────────────────────

class WebsiteMedia(models.Model):
    MEDIA_TYPES = [
        ('image', 'Image'),
        ('video', 'Vidéo'),
        ('pdf', 'PDF'),
        ('document', 'Document'),
        ('icon', 'Icône'),
        ('logo', 'Logo'),
        ('favicon', 'Favicon'),
        ('other', 'Autre'),
    ]

    company = models.ForeignKey('core.Company', on_delete=models.CASCADE, related_name='website_media')
    website = models.ForeignKey(Website, on_delete=models.CASCADE, related_name='media_files', null=True, blank=True)
    file = models.FileField('Fichier', upload_to='websites/media/%Y/%m/')
    title = models.CharField('Titre', max_length=200, blank=True)
    alt_text = models.CharField('Texte alternatif', max_length=200, blank=True)
    caption = models.CharField('Légende', max_length=300, blank=True)
    media_type = models.CharField('Type', max_length=20, choices=MEDIA_TYPES, default='image')
    file_size = models.PositiveIntegerField('Taille fichier (octets)', default=0)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Média site web'
        verbose_name_plural = 'Médias sites web'
        ordering = ['-created_at']

    def __str__(self):
        return self.title or str(self.file)

    @property
    def url(self):
        try:
            return self.file.url
        except Exception:
            return ''

    @property
    def file_size_display(self):
        if self.file_size < 1024:
            return f'{self.file_size} o'
        elif self.file_size < 1024 * 1024:
            return f'{self.file_size // 1024} Ko'
        return f'{self.file_size // (1024 * 1024)} Mo'


# ─── Formulaires avancés ──────────────────────────────────────────────────────

class WebsiteForm(models.Model):
    FORM_TYPES = [
        ('contact', 'Contact'),
        ('quote', 'Demande de devis'),
        ('repair', 'Dépannage'),
        ('works', 'Travaux'),
        ('booking', 'Réservation'),
        ('support', 'Support'),
        ('newsletter', 'Newsletter'),
        ('application', 'Candidature'),
        ('other', 'Autre'),
    ]

    website = models.ForeignKey(Website, on_delete=models.CASCADE, related_name='advanced_forms')
    name = models.CharField('Nom interne', max_length=100)
    form_type = models.CharField('Type', max_length=20, choices=FORM_TYPES, default='contact')
    title = models.CharField('Titre affiché', max_length=200, blank=True)
    description = models.TextField('Description', blank=True)
    success_message = models.TextField('Message succès', default='Merci, votre message a été envoyé.')
    send_notification_email = models.BooleanField('Email de notification', default=True)
    notification_email = models.EmailField('Email destinataire', blank=True)
    create_crm_prospect = models.BooleanField('Créer prospect CRM', default=False)
    create_client_request = models.BooleanField('Créer demande client', default=False)
    create_support_ticket = models.BooleanField('Créer ticket support', default=False)
    is_active = models.BooleanField('Actif', default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Formulaire site web'
        verbose_name_plural = 'Formulaires sites web'

    def __str__(self):
        return f'{self.name} — {self.website.name}'


class WebsiteFormField(models.Model):
    FIELD_TYPES = [
        ('text', 'Texte'),
        ('email', 'Email'),
        ('phone', 'Téléphone'),
        ('textarea', 'Zone de texte'),
        ('select', 'Liste déroulante'),
        ('checkbox', 'Case à cocher'),
        ('radio', 'Bouton radio'),
        ('file', 'Fichier'),
        ('date', 'Date'),
        ('number', 'Nombre'),
        ('hidden', 'Champ caché'),
    ]

    form = models.ForeignKey(WebsiteForm, on_delete=models.CASCADE, related_name='fields')
    label = models.CharField('Libellé', max_length=100)
    field_type = models.CharField('Type', max_length=20, choices=FIELD_TYPES, default='text')
    placeholder = models.CharField('Placeholder', max_length=200, blank=True)
    help_text = models.CharField('Aide', max_length=300, blank=True)
    is_required = models.BooleanField('Obligatoire', default=False)
    choices = models.TextField('Choix (un par ligne)', blank=True)
    order = models.PositiveIntegerField('Ordre', default=0)

    class Meta:
        verbose_name = 'Champ formulaire'
        ordering = ['order']

    def __str__(self):
        return f'{self.label} ({self.form.name})'

    @property
    def choices_list(self):
        return [c.strip() for c in self.choices.splitlines() if c.strip()]


class WebsiteFormSubmission(models.Model):
    STATUS_CHOICES = [
        ('new', 'Nouvelle'),
        ('read', 'Lue'),
        ('processing', 'En traitement'),
        ('converted_prospect', 'Convertie en prospect'),
        ('converted_request', 'Convertie en demande'),
        ('done', 'Traitée'),
        ('archived', 'Archivée'),
    ]

    website = models.ForeignKey(Website, on_delete=models.CASCADE, related_name='form_submissions')
    form = models.ForeignKey(WebsiteForm, on_delete=models.SET_NULL, null=True, blank=True, related_name='submissions')
    name = models.CharField('Nom', max_length=100, blank=True)
    email = models.EmailField('Email', blank=True)
    phone = models.CharField('Téléphone', max_length=20, blank=True)
    subject = models.CharField('Sujet', max_length=200, blank=True)
    message = models.TextField('Message', blank=True)
    data = models.JSONField('Données brutes', default=dict)
    ip_address = models.GenericIPAddressField('IP', null=True, blank=True)
    user_agent = models.TextField('User agent', blank=True)
    status = models.CharField('Statut', max_length=25, choices=STATUS_CHOICES, default='new')
    created_prospect = models.BooleanField('Prospect créé', default=False)
    created_request = models.BooleanField('Demande créée', default=False)
    created_ticket = models.BooleanField('Ticket créé', default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Soumission formulaire'
        verbose_name_plural = 'Soumissions formulaires'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name or self.email} — {self.created_at:%d/%m/%Y}'


# ─── Analytics simple ─────────────────────────────────────────────────────────

class WebsiteAnalyticsEvent(models.Model):
    EVENT_TYPES = [
        ('page_view', 'Vue de page'),
        ('form_submission', 'Soumission formulaire'),
        ('button_click', 'Clic bouton'),
        ('product_view', 'Vue produit'),
        ('add_to_cart', 'Ajout panier'),
        ('checkout_started', 'Commande démarrée'),
        ('order_completed', 'Commande complétée'),
    ]

    website = models.ForeignKey(Website, on_delete=models.CASCADE, related_name='analytics_events')
    event_type = models.CharField('Type', max_length=25, choices=EVENT_TYPES, default='page_view')
    path = models.CharField('Chemin', max_length=500)
    referrer = models.CharField('Référent', max_length=500, blank=True)
    ip_address_hash = models.CharField('Hash IP', max_length=64, blank=True)
    user_agent = models.CharField('User agent', max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Événement analytics'
        verbose_name_plural = 'Événements analytics'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['website', 'event_type', 'created_at']),
            models.Index(fields=['website', 'path']),
        ]

    def __str__(self):
        return f'{self.get_event_type_display()} — {self.path}'


# ─── BTP Portfolio ────────────────────────────────────────────────────────────

class BTPPortfolioProject(models.Model):
    """Réalisation BTP affichée sur le site vitrine."""
    WORK_TYPES = [
        ('electricite', 'Électricité'),
        ('plomberie', 'Plomberie'),
        ('chauffage', 'Chauffage'),
        ('peinture', 'Peinture'),
        ('maconnerie', 'Maçonnerie'),
        ('menuiserie', 'Menuiserie'),
        ('isolation', 'Isolation'),
        ('toiture', 'Toiture'),
        ('revetement', 'Revêtement sol'),
        ('salle_bain', 'Salle de bain'),
        ('cuisine', 'Cuisine'),
        ('renovation', 'Rénovation complète'),
        ('extension', 'Extension'),
        ('autre', 'Autre'),
    ]

    website       = models.ForeignKey(Website, on_delete=models.CASCADE, related_name='btp_portfolio_projects')
    title         = models.CharField('Titre', max_length=200)
    slug          = models.SlugField('Slug', max_length=210, blank=True)
    description   = models.TextField('Description', blank=True)
    work_type     = models.CharField('Type de travaux', max_length=20, choices=WORK_TYPES, default='autre')
    city          = models.CharField('Ville', max_length=100, blank=True)
    before_image  = models.ImageField('Photo avant', upload_to='websites/btp/portfolio/before/', blank=True, null=True)
    after_image   = models.ImageField('Photo après', upload_to='websites/btp/portfolio/after/', blank=True, null=True)
    customer_name = models.CharField('Nom client (optionnel)', max_length=100, blank=True)
    customer_review = models.TextField('Avis client', blank=True)
    completion_date = models.DateField('Date réalisation', null=True, blank=True)
    is_featured   = models.BooleanField('En vedette', default=False)
    is_published  = models.BooleanField('Publié', default=True)
    order         = models.PositiveSmallIntegerField('Ordre', default=0)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Réalisation BTP'
        verbose_name_plural = 'Réalisations BTP'
        ordering = ['order', '-created_at']

    def __str__(self):
        return f'{self.title} ({self.get_work_type_display()})'

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title) or 'realisation'
            self.slug = f'{base}-{self.website_id}'
        super().save(*args, **kwargs)


class BTPWebsiteReview(models.Model):
    """Avis / témoignage client affiché sur le site BTP."""
    website       = models.ForeignKey(Website, on_delete=models.CASCADE, related_name='btp_reviews')
    customer_name = models.CharField('Nom', max_length=100)
    customer_city = models.CharField('Ville', max_length=100, blank=True)
    work_type     = models.CharField('Type de travaux', max_length=20,
                                     choices=BTPPortfolioProject.WORK_TYPES, blank=True)
    rating        = models.PositiveSmallIntegerField('Note /5', default=5)
    comment       = models.TextField('Témoignage')
    project       = models.ForeignKey(BTPPortfolioProject, on_delete=models.SET_NULL,
                                      null=True, blank=True, related_name='reviews',
                                      verbose_name='Réalisation liée')
    is_published  = models.BooleanField('Publié', default=True)
    order         = models.PositiveSmallIntegerField('Ordre', default=0)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Avis client BTP'
        verbose_name_plural = 'Avis clients BTP'
        ordering = ['order', '-created_at']

    def __str__(self):
        return f'{self.customer_name} — {self.rating}/5'

    @property
    def stars_range(self):
        return range(1, 6)


# ─── Demande d'accès portail client (depuis site BTP) ─────────────────────────

class BTPClientAccessRequest(models.Model):
    """Demande d'accès à l'espace client soumise depuis le site BTP."""
    STATUS_CHOICES = [
        ('new',       'Nouvelle'),
        ('processing','En cours'),
        ('granted',   'Accès accordé'),
        ('refused',   'Refusée'),
    ]

    website       = models.ForeignKey(Website, on_delete=models.CASCADE, related_name='client_access_requests')
    first_name    = models.CharField('Prénom', max_length=100)
    last_name     = models.CharField('Nom', max_length=100)
    email         = models.EmailField('Email')
    phone         = models.CharField('Téléphone', max_length=20, blank=True)
    company_name  = models.CharField('Société', max_length=200, blank=True)
    message       = models.TextField('Message', blank=True)
    reference     = models.CharField('N° devis ou facture', max_length=100, blank=True)
    status        = models.CharField('Statut', max_length=20, choices=STATUS_CHOICES, default='new')
    ip_address    = models.GenericIPAddressField('IP', null=True, blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Demande d'accès client"
        verbose_name_plural = "Demandes d'accès client"
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.first_name} {self.last_name} — {self.email}'


class BTPEmergencyRequest(models.Model):
    """Demande d'intervention urgente soumise depuis le site BTP."""
    EMERGENCY_TYPES = [
        ('electricite',     'Panne électrique'),
        ('fuite_eau',       'Fuite d\'eau'),
        ('chauffage',       'Chauffage en panne'),
        ('serrure',         'Porte / serrure'),
        ('degat_batiment',  'Dégât bâtiment'),
        ('autre',           'Autre urgence'),
    ]
    STATUS_CHOICES = [
        ('new',         'Nouvelle'),
        ('assigned',    'Assignée'),
        ('in_progress', 'En cours'),
        ('resolved',    'Résolue'),
        ('closed',      'Fermée'),
    ]

    website           = models.ForeignKey(Website, on_delete=models.CASCADE, related_name='emergency_requests')
    first_name        = models.CharField('Prénom', max_length=100)
    last_name         = models.CharField('Nom', max_length=100)
    phone             = models.CharField('Téléphone', max_length=20)
    email             = models.EmailField('Email', blank=True)
    emergency_type    = models.CharField('Type urgence', max_length=25, choices=EMERGENCY_TYPES, default='autre')
    address           = models.CharField('Adresse', max_length=300)
    city              = models.CharField('Ville', max_length=100, blank=True)
    description       = models.TextField('Description')
    wants_callback    = models.BooleanField('Rappel urgent souhaité', default=True)
    photo             = models.ImageField('Photo', upload_to='websites/btp/emergency/', blank=True, null=True)
    status            = models.CharField('Statut', max_length=20, choices=STATUS_CHOICES, default='new')
    guided_quote      = models.ForeignKey('btp.GuidedQuoteRequest', on_delete=models.SET_NULL,
                                          null=True, blank=True, related_name='emergency_requests',
                                          verbose_name='Demande guidée liée')
    ip_address        = models.GenericIPAddressField('IP', null=True, blank=True)
    created_at        = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Urgence BTP'
        verbose_name_plural = 'Urgences BTP'
        ordering = ['-created_at']

    def __str__(self):
        return f'URGENT — {self.get_emergency_type_display()} — {self.first_name} {self.last_name}'


# ─── Traductions sites web ────────────────────────────────────────────────────

LANG_CODE_FIELD = dict(max_length=5, db_index=True, verbose_name='Langue',
                        help_text='Code langue ISO 639-1 : fr, en, es, de, it, nl, pt')


class WebsitePageTranslation(models.Model):
    """Traduction d une page dans une langue donnee."""
    page             = models.ForeignKey(WebsitePage, on_delete=models.CASCADE, related_name='translations')
    language         = models.CharField(**LANG_CODE_FIELD)
    title            = models.CharField('Titre', max_length=200)
    slug             = models.SlugField('Slug', max_length=200)
    content          = models.TextField('Contenu', blank=True)
    meta_title       = models.CharField('Meta titre', max_length=200, blank=True)
    meta_description = models.TextField('Meta description', blank=True)
    meta_keywords    = models.CharField('Meta keywords', max_length=300, blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Traduction page'
        verbose_name_plural = 'Traductions pages'
        unique_together     = ['page', 'language']
        ordering            = ['page', 'language']

    def __str__(self):
        return f'{self.page.title} [{self.language}]'


class WebsiteSectionTranslation(models.Model):
    """Traduction d une section de page."""
    section     = models.ForeignKey(WebsiteSection, on_delete=models.CASCADE, related_name='translations')
    language    = models.CharField(**LANG_CODE_FIELD)
    title       = models.CharField('Titre', max_length=200, blank=True)
    subtitle    = models.CharField('Sous-titre', max_length=300, blank=True)
    content     = models.TextField('Contenu', blank=True)
    button_text = models.CharField('Texte bouton', max_length=100, blank=True)
    button_url  = models.CharField('URL bouton', max_length=300, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Traduction section'
        verbose_name_plural = 'Traductions sections'
        unique_together     = ['section', 'language']

    def __str__(self):
        return f'{self.section} [{self.language}]'


class BlogPostTranslation(models.Model):
    """Traduction d un article de blog."""
    post             = models.ForeignKey(BlogPost, on_delete=models.CASCADE, related_name='translations')
    language         = models.CharField(**LANG_CODE_FIELD)
    title            = models.CharField('Titre', max_length=200)
    slug             = models.SlugField('Slug', max_length=200)
    excerpt          = models.TextField('Resume', blank=True)
    content          = models.TextField('Contenu')
    meta_title       = models.CharField('Meta titre', max_length=200, blank=True)
    meta_description = models.TextField('Meta description', blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Traduction article'
        verbose_name_plural = 'Traductions articles'
        unique_together     = ['post', 'language']

    def __str__(self):
        return f'{self.post.title} [{self.language}]'


class ProductTranslation(models.Model):
    """Traduction d un produit boutique."""
    product           = models.ForeignKey(StoreProduct, on_delete=models.CASCADE, related_name='translations')
    language          = models.CharField(**LANG_CODE_FIELD)
    name              = models.CharField('Nom', max_length=200)
    slug              = models.SlugField('Slug', max_length=200)
    short_description = models.TextField('Description courte', blank=True)
    description       = models.TextField('Description', blank=True)
    meta_title        = models.CharField('Meta titre', max_length=200, blank=True)
    meta_description  = models.TextField('Meta description', blank=True)
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Traduction produit'
        verbose_name_plural = 'Traductions produits'
        unique_together     = ['product', 'language']

    def __str__(self):
        return f'{self.product.name} [{self.language}]'


class WebsiteMenuItemTranslation(models.Model):
    """Traduction d un element de menu site web."""
    menu_item  = models.ForeignKey(WebsiteMenuItem, on_delete=models.CASCADE, related_name='translations')
    language   = models.CharField(**LANG_CODE_FIELD)
    label      = models.CharField('Libelle', max_length=100)
    url        = models.CharField('URL', max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Traduction element menu"
        verbose_name_plural = "Traductions elements menu"
        unique_together     = ['menu_item', 'language']

    def __str__(self):
        return f'{self.menu_item.label} [{self.language}]'


# ─── Fidélité / Récompenses ───────────────────────────────────────────────────

class LoyaltyAccount(models.Model):
    """Compte de fidélité d'un client SIÈCLE."""
    TIER_CHOICES = [
        ('classic', 'Classic'),
        ('silver',  'Silver'),
        ('gold',    'Gold'),
        ('black',   'Black'),
    ]

    company         = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='loyalty_accounts')
    customer        = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='loyalty_accounts')
    customer_email  = models.EmailField('Email client')
    points_balance  = models.IntegerField('Solde de points', default=0)
    lifetime_points = models.IntegerField('Points cumulés vie', default=0)
    tier            = models.CharField('Niveau', max_length=10, choices=TIER_CHOICES, default='classic')
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Compte fidélité'
        verbose_name_plural = 'Comptes fidélité'
        unique_together     = ['company', 'customer_email']

    def __str__(self):
        return f'{self.customer_email} — {self.tier} ({self.points_balance} pts)'

    def recalculate_tier(self):
        lp = self.lifetime_points
        if lp >= 3000:
            self.tier = 'black'
        elif lp >= 1000:
            self.tier = 'gold'
        elif lp >= 500:
            self.tier = 'silver'
        else:
            self.tier = 'classic'

    def add_points(self, points, reason='', order=None):
        self.points_balance  = max(0, self.points_balance + points)
        self.lifetime_points = max(0, self.lifetime_points + points)
        self.recalculate_tier()
        self.save()
        LoyaltyTransaction.objects.create(
            company=self.company,
            loyalty_account=self,
            order=order,
            points=points,
            transaction_type='gain',
            reason=reason or 'Achat',
        )

    def use_points(self, points, reason='', order=None):
        if points > self.points_balance:
            raise ValueError('Solde insuffisant')
        self.points_balance -= points
        self.save()
        LoyaltyTransaction.objects.create(
            company=self.company,
            loyalty_account=self,
            order=order,
            points=-points,
            transaction_type='utilisation',
            reason=reason or 'Utilisation',
        )


class LoyaltyTransaction(models.Model):
    """Historique des mouvements de points."""
    TYPE_CHOICES = [
        ('gain',        'Gain'),
        ('utilisation', 'Utilisation'),
        ('ajustement',  'Ajustement'),
        ('annulation',  'Annulation'),
        ('bonus',       'Bonus'),
        ('parrainage',  'Parrainage'),
    ]

    company          = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='loyalty_transactions')
    loyalty_account  = models.ForeignKey(LoyaltyAccount, on_delete=models.CASCADE, related_name='transactions')
    order            = models.ForeignKey('StoreOrder', on_delete=models.SET_NULL, null=True, blank=True, related_name='loyalty_transactions')
    points           = models.IntegerField('Points (+ gain / − utilisation)')
    transaction_type = models.CharField('Type', max_length=15, choices=TYPE_CHOICES)
    reason           = models.CharField('Raison', max_length=200, blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Transaction fidélité'
        verbose_name_plural = 'Transactions fidélité'
        ordering            = ['-created_at']

    def __str__(self):
        sign = '+' if self.points >= 0 else ''
        return f'{self.loyalty_account.customer_email} {sign}{self.points} pts — {self.get_transaction_type_display()}'


# ─── Affiliation / Parrainage ─────────────────────────────────────────────────

class AffiliateProgram(models.Model):
    """Configuration du programme d'affiliation."""
    REWARD_TYPE_CHOICES = [
        ('points',   'Points'),
        ('discount', 'Réduction'),
        ('both',     'Points + Réduction'),
    ]

    company                 = models.OneToOneField(Company, on_delete=models.CASCADE, related_name='affiliate_program')
    name                    = models.CharField('Nom', max_length=100, default='Programme Parrainage SIÈCLE')
    is_active               = models.BooleanField('Actif', default=True)
    reward_type             = models.CharField('Type récompense', max_length=10, choices=REWARD_TYPE_CHOICES, default='points')
    referrer_reward_value   = models.DecimalField('Récompense parrain (pts)', max_digits=8, decimal_places=2, default=100)
    referred_reward_value   = models.DecimalField('Réduction filleul (%)', max_digits=5, decimal_places=2, default=10)
    created_at              = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Programme affiliation'
        verbose_name_plural = 'Programmes affiliation'

    def __str__(self):
        return f'{self.name} — {self.company.name}'


class AffiliateCode(models.Model):
    """Code d'affiliation unique par client."""

    company          = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='affiliate_codes')
    customer         = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='affiliate_codes')
    customer_email   = models.EmailField('Email client')
    code             = models.CharField('Code', max_length=20, unique=True)
    clicks           = models.PositiveIntegerField('Clics', default=0)
    signups          = models.PositiveIntegerField('Inscriptions', default=0)
    orders           = models.PositiveIntegerField('Commandes', default=0)
    total_commission = models.DecimalField('Commission totale', max_digits=10, decimal_places=2, default=0)
    is_active        = models.BooleanField('Actif', default=True)
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Code affilié'
        verbose_name_plural = 'Codes affiliés'

    def __str__(self):
        return f'{self.code} — {self.customer_email}'


class AffiliateReferral(models.Model):
    """Parrainage : relation parrain → filleul."""
    STATUS_CHOICES = [
        ('pending',   'En attente'),
        ('validated', 'Validé'),
        ('rejected',  'Refusé'),
        ('paid',      'Payé'),
        ('cancelled', 'Annulé'),
    ]

    company             = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='affiliate_referrals')
    referrer_customer   = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='referrals_sent')
    referrer_email      = models.EmailField('Email parrain')
    referred_email      = models.EmailField('Email filleul')
    affiliate_code      = models.ForeignKey(AffiliateCode, on_delete=models.SET_NULL, null=True, blank=True, related_name='referrals')
    order               = models.ForeignKey('StoreOrder', on_delete=models.SET_NULL, null=True, blank=True, related_name='affiliate_referrals')
    status              = models.CharField('Statut', max_length=12, choices=STATUS_CHOICES, default='pending')
    commission_amount   = models.DecimalField('Commission €', max_digits=8, decimal_places=2, default=0)
    points_reward       = models.IntegerField('Points parrain', default=0)
    created_at          = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Parrainage'
        verbose_name_plural = 'Parrainages'
        ordering            = ['-created_at']

    def __str__(self):
        return f'{self.referrer_email} → {self.referred_email} ({self.get_status_display()})'


# ─── Cartes cadeaux ───────────────────────────────────────────────────────────

class GiftCard(models.Model):
    """Carte cadeau avec code unique."""
    STATUS_CHOICES = [
        ('active',   'Active'),
        ('used',     'Utilisée'),
        ('partial',  'Partiellement utilisée'),
        ('expired',  'Expirée'),
        ('cancelled','Annulée'),
    ]

    company              = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='gift_cards')
    code                 = models.CharField('Code', max_length=20, unique=True)
    initial_amount       = models.DecimalField('Montant initial', max_digits=10, decimal_places=2)
    remaining_amount     = models.DecimalField('Montant restant', max_digits=10, decimal_places=2)
    currency             = models.CharField('Devise', max_length=3, default='EUR')
    status               = models.CharField('Statut', max_length=12, choices=STATUS_CHOICES, default='active')
    purchased_by         = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='purchased_gift_cards')
    purchased_by_email   = models.EmailField('Acheteur email', blank=True)
    assigned_to_email    = models.EmailField('Destinataire email', blank=True)
    expires_at           = models.DateField('Expiration', null=True, blank=True)
    created_at           = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Carte cadeau'
        verbose_name_plural = 'Cartes cadeaux'
        ordering            = ['-created_at']

    def __str__(self):
        return f'{self.code} — {self.remaining_amount}€ ({self.get_status_display()})'

    @property
    def is_valid(self):
        from django.utils import timezone
        if self.status in ('used', 'cancelled'):
            return False
        if self.expires_at and self.expires_at < timezone.now().date():
            return False
        if self.remaining_amount <= 0:
            return False
        return True


class GiftCardRedemption(models.Model):
    """Utilisation d'une carte cadeau."""

    company        = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='gift_card_redemptions')
    gift_card      = models.ForeignKey(GiftCard, on_delete=models.CASCADE, related_name='redemptions')
    customer       = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='gift_card_redemptions')
    customer_email = models.EmailField('Email client', blank=True)
    order          = models.ForeignKey('StoreOrder', on_delete=models.SET_NULL, null=True, blank=True, related_name='gift_card_redemptions')
    amount_used    = models.DecimalField('Montant utilisé', max_digits=10, decimal_places=2)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Utilisation carte cadeau'
        verbose_name_plural = 'Utilisations cartes cadeaux'
        ordering            = ['-created_at']

    def __str__(self):
        return f'{self.gift_card.code} — {self.amount_used}€ par {self.customer_email}'


# ─── Compte client SIÈCLE ─────────────────────────────────────────────────────

class SiecleCustomerToken(models.Model):
    """Token d'authentification simple pour l'espace client SIÈCLE."""
    user       = models.OneToOneField(User, on_delete=models.CASCADE, related_name='siecle_token')
    key        = models.CharField('Token', max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Token client SIÈCLE'

    def __str__(self):
        return f'{self.user.email} — {self.key[:8]}…'

    @classmethod
    def generate(cls, user):
        import secrets
        token, _ = cls.objects.get_or_create(user=user)
        token.key = secrets.token_hex(32)
        token.save()
        return token.key


class NewsletterSubscriber(models.Model):
    """Abonnés à la newsletter SIÈCLE."""
    email      = models.EmailField('E-mail', unique=True)
    active     = models.BooleanField('Actif', default=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Abonné newsletter'
        verbose_name_plural = 'Abonnés newsletter'
        ordering = ['-subscribed_at']

    def __str__(self):
        return self.email


# ──────────────────────────────────────────────────────────────────────────────
# Watch 3D Configurator models
# ──────────────────────────────────────────────────────────────────────────────

class ProductCustomizationOption(models.Model):
    """
    Defines a single customization choice for a configurable product
    (e.g. case_gold → Boîtier doré champagne, +35 €).
    """
    GROUP_CHOICES = [
        ('case',  'Boîtier'),
        ('dial',  'Cadran'),
        ('hands', 'Aiguilles'),
        ('strap', 'Bracelet'),
    ]
    company     = models.ForeignKey('core.Company', on_delete=models.CASCADE, related_name='customization_options')
    product     = models.ForeignKey(StoreProduct, on_delete=models.CASCADE, related_name='customization_options')
    group       = models.CharField('Groupe', max_length=20, choices=GROUP_CHOICES)
    code        = models.CharField('Code option', max_length=60)
    label       = models.CharField('Libellé', max_length=120)
    color       = models.CharField('Couleur hex', max_length=10, blank=True, default='#ffffff')
    material    = models.CharField('Matériau', max_length=30, blank=True)
    price_delta = models.DecimalField('Supplément (€)', max_digits=10, decimal_places=2, default=0)
    is_active   = models.BooleanField('Actif', default=True)
    sort_order  = models.PositiveIntegerField('Ordre', default=0)

    class Meta:
        verbose_name = 'Option personnalisation'
        verbose_name_plural = 'Options personnalisation'
        unique_together = ['product', 'group', 'code']
        ordering = ['group', 'sort_order', 'id']

    def __str__(self):
        return f'{self.product.name} / {self.get_group_display()} / {self.label}'


class ProductCustomizationConfiguration(models.Model):
    """
    Stores a complete watch configuration chosen by a customer.
    Used as a pre-cart save and for reporting.
    """
    company               = models.ForeignKey('core.Company', on_delete=models.CASCADE, related_name='watch_configurations')
    product               = models.ForeignKey(StoreProduct, on_delete=models.CASCADE, related_name='saved_configurations')
    customer              = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='watch_configurations')
    configuration_json    = models.JSONField('Configuration (codes)', default=dict)
    configuration_labels_json = models.JSONField('Configuration (labels)', default=dict)
    base_price            = models.DecimalField('Prix de base', max_digits=10, decimal_places=2, default=0)
    options_price         = models.DecimalField('Prix options', max_digits=10, decimal_places=2, default=0)
    final_price           = models.DecimalField('Prix final', max_digits=10, decimal_places=2, default=0)
    preview_image         = models.ImageField('Aperçu', upload_to='configurator/previews/', null=True, blank=True)
    created_at            = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Configuration montre'
        verbose_name_plural = 'Configurations montres'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.product.name} — {self.final_price} € ({self.created_at.strftime("%d/%m/%Y")})'


class WebOrderLineCustomization(models.Model):
    """
    Links a StoreOrderItem to its full watch customization details.
    Stored separately to keep StoreOrderItem lean.
    """
    order_line                = models.OneToOneField('StoreOrderItem', on_delete=models.CASCADE, related_name='watch_customization')
    configuration_json        = models.JSONField('Configuration (codes)', default=dict)
    configuration_labels_json = models.JSONField('Configuration (labels)', default=dict)
    base_price                = models.DecimalField('Prix de base', max_digits=10, decimal_places=2, default=0)
    options_price             = models.DecimalField('Prix options', max_digits=10, decimal_places=2, default=0)
    final_price               = models.DecimalField('Prix final', max_digits=10, decimal_places=2, default=0)

    class Meta:
        verbose_name = 'Personnalisation ligne commande'
        verbose_name_plural = 'Personnalisations lignes commande'

    def __str__(self):
        return f'Personnalisation ligne #{self.order_line_id}'

    def config_summary(self):
        labels = self.configuration_labels_json or {}
        return ', '.join(f'{k}: {v}' for k, v in labels.items())

# -- Import modeles SIECLE avances --
from .siecle_advanced import (
    LoyaltyMission, CustomerMissionProgress, CustomerBadge,
    StoreCompleteLook, StoreCompleteLookItem,
    StorePremiumPack, StorePremiumPackItem,
    StoreProductDrop, StoreProductDropItem,
    CommunityPost, SavedWatchConfiguration, AbandonedCart,
    CustomerStyleProfile, StyleIdentityResult, BeautyQuizResult,
    ProductVideo, CustomerShadeProfile,
)

# ─── Import modèles gestion domaines ──────────────────────────────────────────
from .models_domains import (
    DomainDNSRecord,
    DomainRedirect,
    DomainConnectionLog,
    CloudflareAccount,
)
