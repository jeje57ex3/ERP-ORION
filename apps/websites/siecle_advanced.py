"""
apps/websites/siecle_advanced.py
Modèles avancés SIÈCLE : missions, badges, looks, packs, drops, communauté, profils.
Importés dans models.py via `from .siecle_advanced import *`
"""
from django.db import models


# ── Missions fidélité ──────────────────────────────────────────────────────────

class LoyaltyMission(models.Model):
    MISSION_TYPES = [
        ('create_account',       'Créer un compte'),
        ('first_order',          'Première commande'),
        ('share_affiliate',      'Partager lien affilié'),
        ('validated_review',     'Avis produit validé'),
        ('birthday',             'Anniversaire'),
        ('order_three_universes','Commander 3 univers'),
        ('complete_identity',    "Compléter l'identité SIÈCLE"),
        ('upload_community',     'Poster un look communauté'),
    ]
    company         = models.ForeignKey('core.Company', on_delete=models.CASCADE, related_name='loyalty_missions')
    title           = models.CharField('Titre', max_length=200)
    description     = models.TextField('Description', blank=True)
    mission_type    = models.CharField('Type', max_length=50, choices=MISSION_TYPES)
    points_reward   = models.PositiveIntegerField('Points offerts', default=0)
    is_active       = models.BooleanField('Actif', default=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label      = 'websites'
        verbose_name   = 'Mission fidélité'
        ordering       = ['points_reward']

    def __str__(self):
        return f'{self.title} (+{self.points_reward} pts)'


class CustomerMissionProgress(models.Model):
    customer        = models.ForeignKey('crm.Customer', on_delete=models.CASCADE, related_name='mission_progresses')
    mission         = models.ForeignKey(LoyaltyMission, on_delete=models.CASCADE)
    completed_at    = models.DateTimeField(null=True, blank=True)
    points_awarded  = models.PositiveIntegerField(default=0)

    class Meta:
        app_label    = 'websites'
        unique_together = [('customer', 'mission')]
        verbose_name = 'Progression mission'


# ── Badges client ──────────────────────────────────────────────────────────────

class CustomerBadge(models.Model):
    BADGE_TYPES = [
        ('client_signature', 'Client Signature'),
        ('client_gold',      'Client Gold'),
        ('client_black',     'Client Black'),
        ('ambassadeur',      'Ambassadeur SIÈCLE'),
        ('collectionneur',   'Collectionneur'),
        ('early_access',     'Early Access'),
        ('beauty_insider',   'Beauty Insider'),
        ('watch_creator',    'Watch Creator'),
        ('style_architect',  'Style Architect'),
    ]
    company     = models.ForeignKey('core.Company', on_delete=models.CASCADE, related_name='customer_badges')
    customer    = models.ForeignKey('crm.Customer', on_delete=models.CASCADE, related_name='badges')
    badge_type  = models.CharField('Type', max_length=50, choices=BADGE_TYPES)
    label       = models.CharField('Label', max_length=100)
    description = models.TextField('Description', blank=True)
    earned_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label      = 'websites'
        verbose_name   = 'Badge client'
        unique_together = [('customer', 'badge_type')]

    def __str__(self):
        return f'{self.customer} — {self.label}'


# ── Looks complets ─────────────────────────────────────────────────────────────

class StoreCompleteLook(models.Model):
    website    = models.ForeignKey('websites.Website', on_delete=models.CASCADE, related_name='complete_looks')
    company    = models.ForeignKey('core.Company', on_delete=models.CASCADE)
    name       = models.CharField('Nom', max_length=200)
    description= models.TextField('Description', blank=True)
    style      = models.CharField('Style', max_length=50, blank=True)
    is_active  = models.BooleanField('Actif', default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label    = 'websites'
        verbose_name = 'Look complet'

    def __str__(self):
        return self.name

    def total_price(self):
        return sum(item.product.price or 0 for item in self.look_items.all())


class StoreCompleteLookItem(models.Model):
    look       = models.ForeignKey(StoreCompleteLook, on_delete=models.CASCADE, related_name='look_items')
    product    = models.ForeignKey('websites.StoreProduct', on_delete=models.CASCADE)
    category   = models.CharField('Catégorie', max_length=50)  # vetement | montre | maquillage
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        app_label  = 'websites'
        ordering   = ['sort_order']


# ── Packs premium ──────────────────────────────────────────────────────────────

class StorePremiumPack(models.Model):
    website      = models.ForeignKey('websites.Website', on_delete=models.CASCADE, related_name='premium_packs')
    company      = models.ForeignKey('core.Company', on_delete=models.CASCADE)
    name         = models.CharField('Nom', max_length=200)
    description  = models.TextField('Description', blank=True)
    pack_price   = models.DecimalField('Prix pack', max_digits=10, decimal_places=2)
    normal_price = models.DecimalField('Prix normal', max_digits=10, decimal_places=2, default=0)
    bonus_points = models.PositiveIntegerField('Points bonus', default=0)
    is_active    = models.BooleanField('Actif', default=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label    = 'websites'
        verbose_name = 'Pack premium'

    def __str__(self):
        return f'{self.name} — {self.pack_price} €'


class StorePremiumPackItem(models.Model):
    pack       = models.ForeignKey(StorePremiumPack, on_delete=models.CASCADE, related_name='pack_items')
    product    = models.ForeignKey('websites.StoreProduct', on_delete=models.CASCADE)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        app_label = 'websites'
        ordering  = ['sort_order']


# ── Drops / précommandes ───────────────────────────────────────────────────────

class StoreProductDrop(models.Model):
    STATUS_CHOICES = [
        ('upcoming',  'À venir'),
        ('active',    'Actif'),
        ('ended',     'Terminé'),
        ('cancelled', 'Annulé'),
    ]
    website                = models.ForeignKey('websites.Website', on_delete=models.CASCADE, related_name='product_drops')
    company                = models.ForeignKey('core.Company', on_delete=models.CASCADE)
    name                   = models.CharField('Nom', max_length=200)
    slug                   = models.SlugField(unique=True)
    description            = models.TextField('Description', blank=True)
    start_at               = models.DateTimeField('Début')
    end_at                 = models.DateTimeField('Fin', null=True, blank=True)
    is_private             = models.BooleanField('Privé', default=False)
    access_code            = models.CharField('Code accès', max_length=50, blank=True)
    minimum_loyalty_tier   = models.CharField('Niveau min.', max_length=20, blank=True)  # silver|gold|black
    status                 = models.CharField('Statut', max_length=20, choices=STATUS_CHOICES, default='upcoming')
    created_at             = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label    = 'websites'
        verbose_name = 'Drop produit'
        ordering     = ['-start_at']

    def __str__(self):
        return self.name


class StoreProductDropItem(models.Model):
    drop               = models.ForeignKey(StoreProductDrop, on_delete=models.CASCADE, related_name='drop_items')
    product            = models.ForeignKey('websites.StoreProduct', on_delete=models.CASCADE)
    quantity_available = models.PositiveIntegerField('Qté disponible', default=0)
    quantity_sold      = models.PositiveIntegerField('Qté vendue', default=0)
    is_preorder        = models.BooleanField('Précommande', default=False)

    class Meta:
        app_label = 'websites'


# ── Communauté ─────────────────────────────────────────────────────────────────

class CommunityPost(models.Model):
    STATUS_CHOICES = [
        ('pending',   'En attente'),
        ('published', 'Publié'),
        ('rejected',  'Refusé'),
        ('archived',  'Archivé'),
    ]
    website       = models.ForeignKey('websites.Website', on_delete=models.CASCADE, related_name='community_posts')
    company       = models.ForeignKey('core.Company', on_delete=models.CASCADE)
    customer      = models.ForeignKey('crm.Customer', on_delete=models.SET_NULL, null=True, blank=True)
    customer_name = models.CharField('Nom affiché', max_length=100, blank=True)
    image         = models.ImageField('Image', upload_to='community/posts/', null=True, blank=True)
    caption       = models.TextField('Légende', blank=True)
    universe_tag  = models.CharField('Univers', max_length=20, blank=True)  # vetements|montres|maquillage
    status        = models.CharField('Statut', max_length=20, choices=STATUS_CHOICES, default='pending')
    likes_count   = models.PositiveIntegerField('Likes', default=0)
    is_featured   = models.BooleanField('Mis en avant', default=False)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label    = 'websites'
        verbose_name = 'Post communauté'
        ordering     = ['-created_at']

    def __str__(self):
        return f'Post #{self.pk} — {self.customer_name or "Anonyme"} ({self.get_status_display()})'


# ── Configuration montre sauvegardée ──────────────────────────────────────────

class SavedWatchConfiguration(models.Model):
    website                   = models.ForeignKey('websites.Website', on_delete=models.CASCADE, related_name='saved_watch_configs')
    company                   = models.ForeignKey('core.Company', on_delete=models.CASCADE)
    customer                  = models.ForeignKey('crm.Customer', on_delete=models.CASCADE, related_name='saved_watches')
    product                   = models.ForeignKey('websites.StoreProduct', on_delete=models.SET_NULL, null=True)
    name                      = models.CharField('Nom de la config', max_length=200, blank=True)
    configuration_json        = models.JSONField('Configuration', default=dict)
    configuration_labels_json = models.JSONField('Labels', default=dict)
    final_price               = models.DecimalField('Prix final', max_digits=10, decimal_places=2, default=0)
    preview_image             = models.ImageField('Aperçu', upload_to='watches/saved/', null=True, blank=True)
    created_at                = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label    = 'websites'
        verbose_name = 'Config montre sauvegardée'
        ordering     = ['-created_at']

    def __str__(self):
        return f'{self.customer} — {self.name or "Config montre"}'


# ── Panier abandonné ───────────────────────────────────────────────────────────

class AbandonedCart(models.Model):
    STATUS_CHOICES = [
        ('active',    'Actif'),
        ('reminded',  'Relancé'),
        ('recovered', 'Récupéré'),
        ('expired',   'Expiré'),
    ]
    website          = models.ForeignKey('websites.Website', on_delete=models.CASCADE, related_name='abandoned_carts')
    company          = models.ForeignKey('core.Company', on_delete=models.CASCADE)
    customer         = models.ForeignKey('crm.Customer', on_delete=models.SET_NULL, null=True, blank=True)
    email            = models.EmailField()
    cart_json        = models.JSONField('Contenu panier', default=list)
    total            = models.DecimalField('Total', max_digits=10, decimal_places=2, default=0)
    status           = models.CharField('Statut', max_length=20, choices=STATUS_CHOICES, default='active')
    last_activity_at = models.DateTimeField('Dernière activité')
    recovered_order  = models.ForeignKey('websites.StoreOrder', on_delete=models.SET_NULL, null=True, blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label    = 'websites'
        verbose_name = 'Panier abandonné'
        ordering     = ['-last_activity_at']


# ── Profil style client ────────────────────────────────────────────────────────

class CustomerStyleProfile(models.Model):
    SKIN_TONES = [
        ('very_light','Très claire'), ('light','Claire'), ('medium','Medium'),
        ('tan','Mate'), ('dark','Foncée'), ('very_dark','Très foncée'),
    ]
    UNDERTONES   = [('cool','Froid'), ('neutral','Neutre'), ('warm','Chaud')]
    FIT_CHOICES  = [('slim','Ajusté'), ('regular','Normal'), ('oversized','Oversize')]

    customer        = models.OneToOneField('crm.Customer', on_delete=models.CASCADE, related_name='style_profile')
    favorite_universe = models.CharField('Univers préféré', max_length=50, blank=True)
    clothing_size   = models.CharField('Taille vêtement', max_length=10, blank=True)
    fit_preference  = models.CharField('Coupe préférée', max_length=20, choices=FIT_CHOICES, blank=True)
    body_type       = models.CharField('Morphologie', max_length=50, blank=True)
    skin_type       = models.CharField('Type de peau', max_length=50, blank=True)
    skin_tone       = models.CharField('Carnation', max_length=20, choices=SKIN_TONES, blank=True)
    beauty_undertone= models.CharField('Sous-ton', max_length=10, choices=UNDERTONES, blank=True)
    style_identity  = models.CharField('Identité SIÈCLE', max_length=50, blank=True)
    favorite_colors = models.JSONField('Couleurs préférées', default=list)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        app_label    = 'websites'
        verbose_name = 'Profil style client'

    def __str__(self):
        return f'Profil — {self.customer}'


# ── Quiz identité SIÈCLE ───────────────────────────────────────────────────────

class StyleIdentityResult(models.Model):
    IDENTITIES = [
        ('minimal',   'Minimal'),
        ('nuit',      'Nuit'),
        ('signature', 'Signature'),
        ('urbain',    'Urbain'),
        ('elegance',  'Élégance'),
        ('audace',    'Audace'),
    ]
    website      = models.ForeignKey('websites.Website', on_delete=models.CASCADE, related_name='identity_results')
    customer     = models.ForeignKey('crm.Customer', on_delete=models.SET_NULL, null=True, blank=True)
    session_key  = models.CharField(max_length=100, blank=True)
    identity     = models.CharField('Identité', max_length=20, choices=IDENTITIES)
    quiz_answers = models.JSONField('Réponses', default=dict)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label    = 'websites'
        verbose_name = "Résultat quiz identité"
        ordering     = ['-created_at']


# ── Quiz beauté ────────────────────────────────────────────────────────────────

class BeautyQuizResult(models.Model):
    website               = models.ForeignKey('websites.Website', on_delete=models.CASCADE, related_name='beauty_quiz_results')
    customer              = models.ForeignKey('crm.Customer', on_delete=models.SET_NULL, null=True, blank=True)
    quiz_answers          = models.JSONField('Réponses', default=dict)
    recommended_products  = models.JSONField('Produits recommandés', default=list)
    created_at            = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label    = 'websites'
        verbose_name = 'Résultat quiz beauté'


# ── Vidéos produit ─────────────────────────────────────────────────────────────

class ProductVideo(models.Model):
    VIDEO_TYPES = [
        ('matiere',     'Matière'),
        ('porte',       'Porté'),
        ('details',     'Détails'),
        ('3d',          '3D'),
        ('fabrication', 'Fabrication'),
    ]
    product    = models.ForeignKey('websites.StoreProduct', on_delete=models.CASCADE, related_name='videos')
    title      = models.CharField('Titre', max_length=200, blank=True)
    video_file = models.FileField('Vidéo', upload_to='products/videos/', null=True, blank=True)
    thumbnail  = models.ImageField('Miniature', upload_to='products/video_thumbs/', null=True, blank=True)
    video_type = models.CharField('Type', max_length=20, choices=VIDEO_TYPES)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        app_label  = 'websites'
        verbose_name = 'Vidéo produit'
        ordering   = ['sort_order']


# ── Profil carnation (shade) ───────────────────────────────────────────────────

class CustomerShadeProfile(models.Model):
    customer     = models.OneToOneField('crm.Customer', on_delete=models.CASCADE, related_name='shade_profile')
    skin_tone    = models.CharField(max_length=20, blank=True)
    undertone    = models.CharField(max_length=10, blank=True)
    finish_pref  = models.CharField(max_length=20, blank=True)  # naturel|lumineux|mat
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label    = 'websites'
        verbose_name = 'Profil carnation'
