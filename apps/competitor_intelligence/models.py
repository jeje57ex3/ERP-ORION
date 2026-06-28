"""
apps/competitor_intelligence/models.py — Modèles analyse concurrentielle Orion ERP
Données légales uniquement : saisie manuelle, CSV, APIs autorisées.
"""
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator


class Competitor(models.Model):
    """Concurrent suivi par une entreprise."""

    company = models.ForeignKey(
        'core.Company', on_delete=models.CASCADE,
        related_name='competitors', verbose_name='Entreprise',
    )
    name        = models.CharField('Nom', max_length=200)
    website_url = models.URLField('Site web', blank=True)
    industry    = models.CharField('Secteur', max_length=100, blank=True)
    country     = models.CharField('Pays', max_length=100, default='France')
    description = models.TextField('Description', blank=True)
    logo        = models.ImageField('Logo', upload_to='competitors/logos/', blank=True, null=True)
    is_active   = models.BooleanField('Actif', default=True)
    created_by  = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='competitors_created', verbose_name='Créé par',
    )
    created_at  = models.DateTimeField('Créé le', auto_now_add=True)
    updated_at  = models.DateTimeField('Mis à jour le', auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Concurrent'
        verbose_name_plural = 'Concurrents'
        unique_together = [('company', 'name')]

    def __str__(self):
        return self.name

    @property
    def active_products_count(self):
        return self.products.filter(is_active=True).count()

    @property
    def unread_alerts_count(self):
        return self.alerts.filter(is_read=False).count()


class CompetitorSite(models.Model):
    """Site web d'un concurrent (un concurrent peut avoir plusieurs sites)."""

    SITE_TYPE_CHOICES = [
        ('main_site',     'Site principal'),
        ('shop',          'Boutique'),
        ('product_page',  'Page produit'),
        ('category_page', 'Page catégorie'),
        ('blog',          'Blog'),
        ('landing_page',  'Landing page'),
    ]

    SCAN_FREQUENCY_CHOICES = [
        ('manual',  'Manuel uniquement'),
        ('daily',   'Quotidien'),
        ('weekly',  'Hebdomadaire'),
        ('monthly', 'Mensuel'),
    ]

    STATUS_CHOICES = [
        ('active',     'Actif'),
        ('inactive',   'Inactif'),
        ('error',      'Erreur'),
        ('restricted', 'Accès restreint'),
    ]

    ROBOTS_POLICY_CHOICES = [
        ('respect',  'Respecter robots.txt (recommandé)'),
        ('manual',   'Saisie manuelle uniquement'),
        ('api_only', 'API officielle uniquement'),
    ]

    competitor      = models.ForeignKey(Competitor, on_delete=models.CASCADE, related_name='sites', verbose_name='Concurrent')
    site_url        = models.URLField('URL du site')
    site_type       = models.CharField('Type', max_length=20, choices=SITE_TYPE_CHOICES, default='main_site')
    tracking_enabled= models.BooleanField('Suivi activé', default=True)
    scan_frequency  = models.CharField('Fréquence scan', max_length=10, choices=SCAN_FREQUENCY_CHOICES, default='manual')
    last_scan_at    = models.DateTimeField('Dernier scan', null=True, blank=True)
    status          = models.CharField('Statut', max_length=20, choices=STATUS_CHOICES, default='active')
    robots_policy   = models.CharField('Politique robots', max_length=20, choices=ROBOTS_POLICY_CHOICES, default='respect')
    notes           = models.TextField('Notes', blank=True)
    created_at      = models.DateTimeField('Créé le', auto_now_add=True)

    class Meta:
        ordering = ['site_url']
        verbose_name = 'Site concurrent'
        verbose_name_plural = 'Sites concurrents'

    def __str__(self):
        return f"{self.competitor.name} — {self.site_url}"


class CompetitorProduct(models.Model):
    """Produit ou service d'un concurrent."""

    AVAILABILITY_CHOICES = [
        ('in_stock',     'En stock'),
        ('out_of_stock', 'Rupture de stock'),
        ('preorder',     'Précommande'),
        ('unknown',      'Inconnu'),
    ]

    company     = models.ForeignKey(
        'core.Company', on_delete=models.CASCADE,
        related_name='competitor_products', verbose_name='Notre entreprise',
    )
    competitor  = models.ForeignKey(Competitor, on_delete=models.CASCADE, related_name='products', verbose_name='Concurrent')
    site        = models.ForeignKey(CompetitorSite, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Site')
    external_id = models.CharField('ID externe', max_length=200, blank=True)
    name        = models.CharField('Nom produit', max_length=500)
    brand       = models.CharField('Marque', max_length=200, blank=True)
    category    = models.CharField('Catégorie', max_length=200, blank=True)
    product_url = models.URLField('URL produit', blank=True)
    image_url   = models.URLField('URL image', blank=True)
    description = models.TextField('Description', blank=True)

    price           = models.DecimalField('Prix', max_digits=12, decimal_places=2, null=True, blank=True)
    currency        = models.CharField('Devise', max_length=3, default='EUR')
    old_price       = models.DecimalField('Ancien prix', max_digits=12, decimal_places=2, null=True, blank=True)
    discount_percent= models.DecimalField('Remise %', max_digits=5, decimal_places=2, null=True, blank=True)

    availability    = models.CharField('Disponibilité', max_length=20, choices=AVAILABILITY_CHOICES, default='unknown')
    rating          = models.DecimalField('Note', max_digits=3, decimal_places=2, null=True, blank=True,
                                          validators=[MinValueValidator(0), MaxValueValidator(5)])
    review_count    = models.IntegerField('Nombre d\'avis', default=0)

    detected_at     = models.DateTimeField('Détecté le', auto_now_add=True)
    last_checked_at = models.DateTimeField('Vérifié le', null=True, blank=True)
    is_active       = models.BooleanField('Actif', default=True)

    class Meta:
        ordering = ['category', 'name']
        verbose_name = 'Produit concurrent'
        verbose_name_plural = 'Produits concurrents'

    def __str__(self):
        return f"{self.competitor.name} — {self.name}"

    @property
    def price_display(self):
        if not self.price:
            return '—'
        return f'{self.price:.2f} {self.currency}'

    @property
    def has_promotion(self):
        return bool(self.old_price and self.discount_percent)


class CompetitorPriceHistory(models.Model):
    """Historique des prix d'un produit concurrent."""

    company            = models.ForeignKey(
        'core.Company', on_delete=models.CASCADE,
        related_name='competitor_price_history', verbose_name='Entreprise',
    )
    competitor_product = models.ForeignKey(
        CompetitorProduct, on_delete=models.CASCADE,
        related_name='price_history', verbose_name='Produit',
    )
    price              = models.DecimalField('Prix', max_digits=12, decimal_places=2)
    old_price          = models.DecimalField('Ancien prix', max_digits=12, decimal_places=2, null=True, blank=True)
    discount_percent   = models.DecimalField('Remise %', max_digits=5, decimal_places=2, null=True, blank=True)
    currency           = models.CharField('Devise', max_length=3, default='EUR')
    availability       = models.CharField('Disponibilité', max_length=20, default='unknown')
    checked_at         = models.DateTimeField('Vérifié le', auto_now_add=True)

    class Meta:
        ordering = ['-checked_at']
        verbose_name = 'Historique prix concurrent'
        verbose_name_plural = 'Historiques prix concurrents'

    def __str__(self):
        return f"{self.competitor_product.name} — {self.price} {self.currency} ({self.checked_at:%d/%m/%Y})"


class CompetitorAdvantage(models.Model):
    """Avantage concurrentiel identifié chez un concurrent."""

    ADVANTAGE_TYPE_CHOICES = [
        ('delivery',         'Livraison'),
        ('price',            'Prix'),
        ('quality',          'Qualité'),
        ('brand',            'Marque'),
        ('loyalty',          'Fidélité'),
        ('return_policy',    'Retours'),
        ('payment_options',  'Paiement'),
        ('product_range',    'Gamme produits'),
        ('customer_service', 'Service client'),
        ('social_proof',     'Preuve sociale'),
        ('seo',              'Référencement'),
        ('design',           'Design / UX'),
        ('technology',       'Technologie'),
        ('other',            'Autre'),
    ]

    company            = models.ForeignKey('core.Company', on_delete=models.CASCADE, related_name='competitor_advantages')
    competitor         = models.ForeignKey(Competitor, on_delete=models.CASCADE, related_name='advantages')
    title              = models.CharField('Titre', max_length=300)
    description        = models.TextField('Description')
    advantage_type     = models.CharField('Type', max_length=30, choices=ADVANTAGE_TYPE_CHOICES, default='other')
    score              = models.IntegerField('Impact (1-10)', default=5,
                                             validators=[MinValueValidator(1), MaxValueValidator(10)])
    detected_manually  = models.BooleanField('Saisi manuellement', default=True)
    source_url         = models.URLField('Source URL', blank=True)
    created_at         = models.DateTimeField('Créé le', auto_now_add=True)
    created_by         = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='advantages_created',
    )

    class Meta:
        ordering = ['-score', '-created_at']
        verbose_name = 'Avantage concurrent'
        verbose_name_plural = 'Avantages concurrents'

    def __str__(self):
        return f"{self.competitor.name} — {self.title}"


class CompetitorTrafficEstimate(models.Model):
    """
    Estimation du trafic d'un site concurrent.
    IMPORTANT: Toujours afficher comme 'estimé', jamais comme données réelles.
    """

    SOURCE_TYPE_CHOICES = [
        ('manual',    'Saisie manuelle'),
        ('csv',       'Import CSV'),
        ('api',       'API externe autorisée'),
        ('analytics', 'Outil analytics autorisé'),
        ('internal',  'Estimation interne'),
    ]

    company                    = models.ForeignKey('core.Company', on_delete=models.CASCADE, related_name='traffic_estimates')
    competitor                 = models.ForeignKey(Competitor, on_delete=models.CASCADE, related_name='traffic_estimates')
    site                       = models.ForeignKey(CompetitorSite, on_delete=models.SET_NULL, null=True, blank=True)
    estimated_monthly_visitors = models.BigIntegerField('Visiteurs mensuels estimés', null=True, blank=True)
    estimated_daily_visitors   = models.BigIntegerField('Visiteurs journaliers estimés', null=True, blank=True)
    traffic_source             = models.CharField('Source trafic', max_length=100, blank=True)
    confidence_score           = models.IntegerField('Confiance (1-10)', default=5,
                                                      validators=[MinValueValidator(1), MaxValueValidator(10)])
    source_type                = models.CharField('Type de source', max_length=20, choices=SOURCE_TYPE_CHOICES, default='manual')
    measured_at                = models.DateTimeField('Mesuré le', auto_now_add=True)

    class Meta:
        ordering = ['-measured_at']
        verbose_name = 'Estimation trafic concurrent'
        verbose_name_plural = 'Estimations trafic concurrents'

    def __str__(self):
        return f"{self.competitor.name} — ~{self.estimated_monthly_visitors or 0:,} visiteurs/mois (estimé)"


class CompetitorComparison(models.Model):
    """Comparaison multi-concurrents créée par l'utilisateur."""

    company     = models.ForeignKey('core.Company', on_delete=models.CASCADE, related_name='competitor_comparisons')
    name        = models.CharField('Nom de la comparaison', max_length=300)
    competitors = models.ManyToManyField(Competitor, related_name='comparisons', verbose_name='Concurrents comparés')
    our_company = models.ForeignKey(
        'core.Company', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='own_comparisons', verbose_name='Notre entreprise dans la comparaison',
    )
    category    = models.CharField('Catégorie / segment', max_length=200, blank=True)
    created_by  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at  = models.DateTimeField('Créé le', auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Comparaison concurrentielle'
        verbose_name_plural = 'Comparaisons concurrentielles'

    def __str__(self):
        return self.name


class CompetitorAlert(models.Model):
    """Alerte automatique générée lors d'un changement détecté."""

    ALERT_TYPE_CHOICES = [
        ('price_drop',           'Baisse de prix'),
        ('price_increase',       'Hausse de prix'),
        ('new_product',          'Nouveau produit'),
        ('product_unavailable',  'Produit indisponible'),
        ('new_promotion',        'Nouvelle promotion'),
        ('traffic_change',       'Changement de trafic estimé'),
        ('new_advantage',        'Nouvel avantage détecté'),
        ('scan_failed',          'Scan échoué'),
    ]

    SEVERITY_CHOICES = [
        ('low',      'Faible'),
        ('medium',   'Modérée'),
        ('high',     'Haute'),
        ('critical', 'Critique'),
    ]

    company    = models.ForeignKey('core.Company', on_delete=models.CASCADE, related_name='competitor_alerts')
    competitor = models.ForeignKey(Competitor, on_delete=models.CASCADE, related_name='alerts')
    alert_type = models.CharField('Type', max_length=30, choices=ALERT_TYPE_CHOICES)
    title      = models.CharField('Titre', max_length=300)
    message    = models.TextField('Message')
    severity   = models.CharField('Sévérité', max_length=10, choices=SEVERITY_CHOICES, default='medium')
    is_read    = models.BooleanField('Lu', default=False)
    created_at = models.DateTimeField('Créé le', auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Alerte concurrentielle'
        verbose_name_plural = 'Alertes concurrentielles'

    def __str__(self):
        return f"[{self.get_severity_display()}] {self.title}"

    @property
    def severity_color(self):
        return {
            'low':      'secondary',
            'medium':   'warning',
            'high':     'danger',
            'critical': 'dark',
        }.get(self.severity, 'secondary')

    @property
    def severity_icon(self):
        return {
            'low':      'bi-info-circle',
            'medium':   'bi-exclamation-circle',
            'high':     'bi-exclamation-triangle',
            'critical': 'bi-exclamation-octagon',
        }.get(self.severity, 'bi-bell')
