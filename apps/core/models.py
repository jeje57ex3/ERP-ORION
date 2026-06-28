"""
apps/core/models.py — Modèles fondamentaux ERP
Entreprises, configuration, audit, connecteurs, multi-base
"""
from django.db import models
from django.conf import settings
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.urls import reverse


# ─── Choix secteur ────────────────────────────────────────────────────────────
SECTOR_CHOICES = [
    ('btp', 'BTP / Construction'),
    ('ecommerce', 'E-commerce'),
    ('commerce', 'Commerce / Négoce'),
    ('production', 'Production / Industrie'),
    ('audio', 'Audio / Audiovisuel'),
    ('services', 'Services'),
    ('other', 'Autre'),
]

SECTOR_COLORS = {
    'btp': '#F59E0B',
    'ecommerce': '#7C3AED',
    'commerce': '#2563EB',
    'production': '#16A34A',
    'audio': '#DB2777',
    'services': '#0891B2',
    'other': '#6B7280',
}


class Company(models.Model):
    """Entreprise / société dans l'ERP multi-tenant."""

    name = models.CharField('Nom', max_length=200)
    slug = models.SlugField('Slug', unique=True, blank=True)
    sector = models.CharField('Secteur', max_length=50, choices=SECTOR_CHOICES, default='other')
    logo = models.ImageField('Logo', upload_to='companies/logos/', blank=True, null=True)
    favicon = models.ImageField('Favicon', upload_to='companies/favicons/', blank=True, null=True)

    # Coordonnées
    email = models.EmailField('Email', blank=True)
    phone = models.CharField('Téléphone', max_length=20, blank=True)
    address = models.TextField('Adresse', blank=True)
    city = models.CharField('Ville', max_length=100, blank=True)
    zip_code = models.CharField('Code postal', max_length=10, blank=True)
    country = models.CharField('Pays', max_length=100, default='France')

    # Identifiants légaux
    siret = models.CharField('SIRET', max_length=14, blank=True)
    siren = models.CharField('SIREN', max_length=9, blank=True)
    vat_number = models.CharField('N° TVA intracommunautaire', max_length=20, blank=True)
    rcs = models.CharField('RCS', max_length=100, blank=True)
    capital = models.DecimalField('Capital social', max_digits=12, decimal_places=2, null=True, blank=True)
    legal_form = models.CharField('Forme juridique', max_length=50, blank=True)

    # Branding
    primary_color = models.CharField('Couleur primaire', max_length=7, default='#2563EB')
    secondary_color = models.CharField('Couleur secondaire', max_length=7, default='#0F172A')
    accent_color = models.CharField('Couleur accent', max_length=7, default='#38BDF8')

    # Paramètres
    currency = models.CharField('Devise', max_length=3, default='EUR')
    timezone = models.CharField('Fuseau horaire', max_length=50, default='Europe/Paris')
    date_format = models.CharField('Format date', max_length=20, default='%d/%m/%Y')
    invoice_prefix = models.CharField('Préfixe facture', max_length=10, default='FAC')
    quote_prefix = models.CharField('Préfixe devis', max_length=10, default='DEV')
    order_prefix = models.CharField('Préfixe commande', max_length=10, default='CMD')
    default_vat_rate = models.DecimalField('Taux TVA défaut', max_digits=5, decimal_places=2, default=20.00)

    # Bancaire
    bank_name = models.CharField('Banque', max_length=100, blank=True)
    iban = models.CharField('IBAN', max_length=34, blank=True)
    bic = models.CharField('BIC / SWIFT', max_length=11, blank=True)

    # Web
    website_url = models.URLField('Site web', blank=True)

    # ── Informations légales supplémentaires ──────────────────────────────────
    legal_name = models.CharField('Raison sociale', max_length=300, blank=True)

    # ── Statut entreprise ─────────────────────────────────────────────────────
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('suspended', 'Suspendue'),
        ('archived', 'Archivée'),
        ('deleting', 'En suppression'),
        ('deleted', 'Supprimée'),
    ]
    status = models.CharField('Statut', max_length=20, choices=STATUS_CHOICES, default='active')
    is_active = models.BooleanField('Active', default=True)

    # ── Base de données dédiée ────────────────────────────────────────────────
    database_name = models.CharField('Nom base de données', max_length=100, blank=True)
    database_host = models.CharField('Hôte base', max_length=200, blank=True, default='127.0.0.1')
    database_user = models.CharField('Utilisateur base', max_length=100, blank=True, default='root')
    database_password = models.CharField('Mot de passe base', max_length=200, blank=True)
    database_port = models.PositiveIntegerField('Port base', default=3306)
    database_created = models.BooleanField('Base créée', default=False)
    database_created_at = models.DateTimeField('Base créée le', null=True, blank=True)
    database_archived = models.BooleanField('Base archivée', default=False)
    database_archived_at = models.DateTimeField('Base archivée le', null=True, blank=True)
    database_deleted = models.BooleanField('Base supprimée', default=False)
    database_deleted_at = models.DateTimeField('Base supprimée le', null=True, blank=True)

    created_at = models.DateTimeField('Créée le', auto_now_add=True)
    updated_at = models.DateTimeField('Modifiée le', auto_now=True)

    class Meta:
        verbose_name = 'Entreprise'
        verbose_name_plural = 'Entreprises'
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('core:company_detail', kwargs={'pk': self.pk})

    @property
    def sector_color(self):
        return SECTOR_COLORS.get(self.sector, '#6B7280')

    @property
    def sector_label(self):
        return dict(SECTOR_CHOICES).get(self.sector, 'Autre')

    @property
    def full_address(self):
        parts = [self.address, self.zip_code, self.city, self.country]
        return ', '.join(p for p in parts if p)

    @property
    def db_alias(self):
        if self.database_name:
            return f'company_{self.pk}'
        return 'default'

    @property
    def status_color(self):
        return {
            'active': 'success', 'suspended': 'warning',
            'archived': 'secondary', 'deleting': 'danger', 'deleted': 'dark',
        }.get(self.status, 'secondary')


class CompanySettings(models.Model):
    """Paramètres étendus par entreprise."""
    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name='settings')
    # Numérotation — séquences gérées atomiquement par core/numbering.py
    next_invoice_number = models.PositiveIntegerField(default=1)
    next_quote_number = models.PositiveIntegerField(default=1)
    next_order_number = models.PositiveIntegerField(default=1)
    next_purchase_order_number = models.PositiveIntegerField(default=1)
    next_project_number = models.PositiveIntegerField(default=1)
    next_ticket_number = models.PositiveIntegerField(default=1)
    next_expense_report_number = models.PositiveIntegerField(default=1)
    next_delivery_number = models.PositiveIntegerField(default=1)
    next_return_number = models.PositiveIntegerField(default=1)
    next_credit_note_number = models.PositiveIntegerField(default=1)
    next_journal_entry_number = models.PositiveIntegerField(default=1)
    # Paiement
    payment_terms_days = models.PositiveIntegerField('Délai paiement (jours)', default=30)
    late_payment_rate = models.DecimalField('Taux pénalité retard', max_digits=5, decimal_places=2, default=10.00)
    # Mentions légales
    invoice_footer = models.TextField('Pied de facture', blank=True)
    quote_validity_days = models.PositiveIntegerField('Validité devis (jours)', default=30)

    class Meta:
        verbose_name = 'Paramètres entreprise'
        verbose_name_plural = 'Paramètres entreprises'

    def __str__(self):
        return f'Paramètres — {self.company.name}'


class AuditLog(models.Model):
    """Journal d'audit des actions importantes."""
    ACTION_CHOICES = [
        ('create', 'Création'),
        ('update', 'Modification'),
        ('delete', 'Suppression'),
        ('login', 'Connexion'),
        ('logout', 'Déconnexion'),
        ('view', 'Consultation'),
        ('export', 'Export'),
        ('import', 'Import'),
        ('validate', 'Validation'),
        ('reject', 'Rejet'),
        ('payment', 'Paiement'),
        ('download', 'Téléchargement'),
        ('upload', 'Upload'),
        ('permission_change', 'Changement permission'),
        ('db_create', 'Création base'),
        ('db_delete', 'Suppression base'),
        ('db_backup', 'Sauvegarde base'),
        ('other', 'Autre'),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Utilisateur')
    company = models.ForeignKey(Company, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Entreprise')
    action = models.CharField('Action', max_length=20, choices=ACTION_CHOICES)
    module = models.CharField('Module', max_length=50, blank=True)
    model_name = models.CharField('Modèle', max_length=100, blank=True)
    object_id = models.CharField('ID objet', max_length=50, blank=True)
    object_repr = models.CharField('Description objet', max_length=200, blank=True)
    old_values = models.JSONField('Anciennes valeurs', null=True, blank=True)
    new_values = models.JSONField('Nouvelles valeurs', null=True, blank=True)
    description = models.TextField('Description', blank=True)
    ip_address = models.GenericIPAddressField('Adresse IP', null=True, blank=True)
    user_agent = models.CharField('User Agent', max_length=500, blank=True)
    created_at = models.DateTimeField('Date', auto_now_add=True)

    class Meta:
        verbose_name = 'Journal d\'audit'
        verbose_name_plural = 'Journal d\'audit'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'created_at'], name='audit_comp_cre_idx'),
            models.Index(fields=['user', 'action'], name='audit_usr_act_idx'),
            models.Index(fields=['model_name', 'object_id'], name='audit_mod_obj_idx'),
        ]

    def __str__(self):
        return f'{self.get_action_display()} — {self.object_repr} — {self.created_at:%d/%m/%Y %H:%M}'


class Connector(models.Model):
    """Connecteurs vers services externes (Shopify, Stripe, etc.)."""
    CONNECTOR_TYPES = [
        ('shopify', 'Shopify'),
        ('woocommerce', 'WooCommerce'),
        ('prestashop', 'PrestaShop'),
        ('magento', 'Magento'),
        ('stripe', 'Stripe'),
        ('paypal', 'PayPal'),
        ('alma', 'Alma'),
        ('klarna', 'Klarna'),
        ('colissimo', 'Colissimo'),
        ('chronopost', 'Chronopost'),
        ('dhl', 'DHL'),
        ('bank', 'Banque'),
        ('ocr', 'OCR Factures'),
        ('esign', 'Signature électronique'),
        ('google_analytics', 'Google Analytics'),
        ('meta_pixel', 'Meta Pixel'),
        ('other', 'Autre'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='connectors')
    connector_type = models.CharField('Type', max_length=30, choices=CONNECTOR_TYPES)
    name = models.CharField('Nom', max_length=100)
    api_url = models.URLField('URL API', blank=True)
    api_key = models.TextField('Clé API (chiffrée)', blank=True)
    api_secret = models.TextField('Secret API (chiffré)', blank=True)
    extra_config = models.JSONField('Configuration supplémentaire', default=dict, blank=True)
    is_active = models.BooleanField('Actif', default=False)
    last_sync = models.DateTimeField('Dernière sync', null=True, blank=True)
    sync_log = models.TextField('Log de sync', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Connecteur'
        verbose_name_plural = 'Connecteurs'
        unique_together = ['company', 'connector_type']

    def __str__(self):
        return f'{self.get_connector_type_display()} — {self.company.name}'


class CompanyDatabase(models.Model):
    """Configuration et état de la base de données dédiée à une entreprise."""

    STATUS_CHOICES = [
        ('to_create', 'À créer'),
        ('created', 'Créée'),
        ('migration_pending', 'Migration en attente'),
        ('active', 'Active'),
        ('archived', 'Archivée'),
        ('error', 'Erreur'),
        ('deleted', 'Supprimée'),
    ]
    ENGINE_CHOICES = [
        ('django.db.backends.mysql', 'MySQL / MariaDB'),
        ('django.db.backends.postgresql', 'PostgreSQL'),
        ('django.db.backends.sqlite3', 'SQLite'),
    ]

    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name='company_database')
    database_alias = models.CharField('Alias Django', max_length=100, unique=True)
    database_name = models.CharField('Nom base', max_length=100)
    database_engine = models.CharField('Moteur', max_length=100, choices=ENGINE_CHOICES, default='django.db.backends.mysql')
    host = models.CharField('Hôte', max_length=200, default='127.0.0.1')
    port = models.PositiveIntegerField('Port', default=3306)
    user = models.CharField('Utilisateur', max_length=100, default='root')
    password_encrypted = models.TextField('Mot de passe (chiffré)', blank=True)
    status = models.CharField('Statut', max_length=30, choices=STATUS_CHOICES, default='to_create')
    is_active = models.BooleanField('Active', default=False)
    created_at = models.DateTimeField('Créée le', auto_now_add=True)
    last_migration_at = models.DateTimeField('Dernière migration', null=True, blank=True)
    last_backup_at = models.DateTimeField('Dernière sauvegarde', null=True, blank=True)
    last_error = models.TextField('Dernière erreur', blank=True)
    size_mb = models.FloatField('Taille estimée (Mo)', default=0)

    class Meta:
        verbose_name = 'Base de données entreprise'
        verbose_name_plural = 'Bases de données entreprises'

    def __str__(self):
        return f'{self.database_name} ({self.get_status_display()})'

    @property
    def status_color(self):
        return {
            'to_create': 'secondary', 'created': 'info', 'migration_pending': 'warning',
            'active': 'success', 'archived': 'secondary', 'error': 'danger', 'deleted': 'dark',
        }.get(self.status, 'secondary')


class CompanyAccess(models.Model):
    """Accès étendu d'un utilisateur à une entreprise (avec droits DB)."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='extended_company_accesses')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='extended_accesses')
    role = models.CharField('Rôle', max_length=30, choices=[
        ('viewer', 'Lecteur'),
        ('user', 'Utilisateur'),
        ('manager', 'Responsable'),
        ('admin', 'Administrateur'),
        ('owner', 'Propriétaire'),
    ], default='user')
    is_active = models.BooleanField('Actif', default=True)
    is_default_company = models.BooleanField('Entreprise par défaut', default=False)
    can_manage_company = models.BooleanField('Peut gérer l\'entreprise', default=False)
    can_delete_company_database = models.BooleanField('Peut supprimer la base', default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Accès entreprise (étendu)'
        verbose_name_plural = 'Accès entreprises (étendus)'
        unique_together = ['user', 'company']

    def __str__(self):
        return f'{self.user.username} → {self.company.name} ({self.role})'


class Notification(models.Model):
    """Notifications internes utilisateurs."""
    LEVEL_CHOICES = [
        ('info', 'Information'),
        ('success', 'Succès'),
        ('warning', 'Avertissement'),
        ('danger', 'Alerte'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='core_notifications')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name='core_notifications')
    title = models.CharField('Titre', max_length=200)
    message = models.TextField('Message')
    level = models.CharField('Niveau', max_length=10, choices=LEVEL_CHOICES, default='info')
    link = models.CharField('Lien', max_length=300, blank=True)
    is_read = models.BooleanField('Lu', default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Notification'
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class SavedView(models.Model):
    """Vue sauvegardée par un utilisateur pour un module donné."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='saved_views',
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='saved_views',
    )
    module = models.CharField('Module', max_length=50)
    name = models.CharField('Nom de la vue', max_length=100)
    filters_json = models.JSONField('Filtres', default=dict, blank=True)
    columns_json = models.JSONField('Colonnes', default=list, blank=True)
    sort_json = models.JSONField('Tri', default=dict, blank=True)
    is_default = models.BooleanField('Par défaut', default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Vue sauvegardée'
        verbose_name_plural = 'Vues sauvegardées'
        unique_together = [('user', 'company', 'module', 'name')]
        ordering = ['module', 'name']

    def __str__(self):
        return f'{self.module} — {self.name}'

    def save(self, *args, **kwargs):
        if self.is_default:
            SavedView.objects.filter(
                user=self.user,
                company=self.company,
                module=self.module,
                is_default=True,
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class UserPreference(models.Model):
    """Préférences UI par utilisateur."""
    THEME_CHOICES = [
        ('light', 'Clair'),
        ('dark', 'Sombre'),
        ('system', 'Système'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='preference',
    )
    theme = models.CharField('Thème', max_length=10, choices=THEME_CHOICES, default='light')
    compact_mode = models.BooleanField('Mode compact', default=False)
    sidebar_collapsed = models.BooleanField('Sidebar réduite', default=False)
    default_dashboard = models.CharField('Dashboard par défaut', max_length=50, blank=True)
    items_per_page = models.PositiveIntegerField('Éléments par page', default=25)
    language = models.CharField('Langue', max_length=10, default='fr')
    email_notifications = models.BooleanField('Notif. email', default=True)
    erp_notifications = models.BooleanField('Notif. ERP', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Préférences utilisateur'
        verbose_name_plural = 'Préférences utilisateurs'

    def __str__(self):
        return f'Préférences de {self.user.username}'

    @classmethod
    def get_for_user(cls, user):
        pref, _ = cls.objects.get_or_create(user=user)
        return pref
